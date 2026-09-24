"""rtl-harness ticket: record a problem found in a project.

Two layers: a markdown file in <consumer>/<tickets_dir>/ (always, works offline) and, when the
project has a GitHub remote, a mirrored issue. Harness-related kinds (deviation / rule / tool)
can be escalated to the harness repository after redaction and an explicit confirmation.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path

from . import __version__, paths
from ._proc import run
from ._safety import check_name, clean_env, within
from .config import Config, load_config
from .errors import HarnessError, ToolMissing
from .provision import github_remote

KINDS = ("bug", "deviation", "rule", "tool")
DOMAINS = ("bus", "cpu", "verif")
MODELS = ("claude", "copilot", "codex", "qwen", "other")
TEMPLATES = paths.harness_root() / "scripts" / "ticket" / "templates"

# Applied to every ticket body (harness.toml [tickets].redact adds more).
DEFAULT_REDACT = [
    r"[A-Za-z]:\\(?:[^\\\s\"'<>|]+\\)*[^\\\s\"'<>|]*",   # Windows absolute paths
    r"/(?:home|Users)/[^\s\"'<>|]+",                        # Unix home directories
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",      # e-mail addresses
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",                         # IP addresses
]


def redact(text: str, extra: list[str] | None = None) -> str:
    for pat in DEFAULT_REDACT + list(extra or []):
        try:
            text = re.sub(pat, "<redacted>", text)
        except re.error as exc:
            raise HarnessError(f"[tickets].redact pattern {pat!r}: {exc}") from None
    return text


# --- storage ---------------------------------------------------------------------------------

def tickets_dir(cfg: Config) -> Path:
    d = within(cfg.root, cfg.tickets_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict = {"path": path}
    if text.startswith("---"):
        head, _, body = text[3:].partition("\n---")
        for line in head.splitlines():
            k, sep, v = line.partition(":")
            if sep:
                meta[k.strip()] = v.strip()
        meta["body"] = body.lstrip("\n")
    else:
        meta["body"] = text
    return meta


def _write(path: Path, meta: dict, body: str) -> None:
    keys = ("id", "kind", "domain", "model", "title", "status", "created", "harness_version", "issue", "escalated_to")
    head = "\n".join(f"{k}: {meta.get(k, '') or ''}" for k in keys)
    path.write_text(f"---\n{head}\n---\n\n{body.rstrip()}\n", encoding="utf-8", newline="\n")


def list_tickets(cfg: Config) -> list[dict]:
    out = []
    for p in sorted(tickets_dir(cfg).glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        m = _parse(p)
        if m.get("id"):
            out.append(m)
    return out


def _next_id(cfg: Config) -> str:
    today = _dt.date.today().strftime("%Y%m%d")
    n = sum(1 for t in list_tickets(cfg) if str(t.get("id", "")).startswith(today))
    return f"{today}-{n + 1:03d}"


def _slug(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return s[:40] or "ticket"


def _find(cfg: Config, ticket_id: str) -> dict:
    check_name(ticket_id, "ticket id")
    for t in list_tickets(cfg):
        if t.get("id") == ticket_id:
            return t
    raise HarnessError(f"ticket {ticket_id} not found in {cfg.tickets_dir}/")


# --- context ---------------------------------------------------------------------------------

def harness_version(cfg: Config) -> str:
    if cfg.is_self:
        return __version__
    r = run(["git", "-C", str(paths.harness_root()), "describe", "--tags", "--always"], cwd=cfg.root, env=clean_env(), timeout_s=30)
    return r.stdout.strip() if r.ok and r.stdout.strip() else __version__


def _last(cfg: Config, name: str) -> dict | None:
    p = cfg.runtime / "last" / f"{name}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summarise_last(cfg: Config) -> tuple[str, str, list[str]]:
    lint = _last(cfg, "lint")
    sim = _last(cfg, "sim")
    files: list[str] = []
    lint_txt = "(no run_lint result in .harness/last)"
    if lint:
        files = list(lint.get("source", {}).get("files", []))[:20]
        errs = lint.get("lint", {}).get("errors", [])[:10]
        lines = [f"status={lint.get('status')} counts={json.dumps(lint.get('lint', {}).get('counts'))}"]
        lines += [f"- {e['file']}:{e['line']}: {e['severity']} [{e['tool']}/{e['rule']}] {e['message']}" for e in errs]
        if len(lint.get("lint", {}).get("errors", [])) > 10:
            lines.append(f"- ... {len(lint['lint']['errors']) - 10} more")
        lint_txt = "\n".join(lines)
    sim_txt = "(no run_sim result in .harness/last)"
    if sim:
        ff = sim.get("first_failure") or {}
        sim_txt = f"block={sim.get('source', {}).get('block')} status={sim.get('status')} passed={sim.get('passed')} failed={sim.get('failed')}"
        if ff:
            sim_txt += f"\nfirst failure: {ff.get('test')}: {ff.get('message')} @ {ff.get('sim_time')}"
    return lint_txt, sim_txt, files


# --- GitHub ----------------------------------------------------------------------------------

def _gh() -> Path:
    exe = shutil.which("gh")
    if not exe:
        raise ToolMissing("gh (GitHub CLI) is not installed or not on PATH")
    return Path(exe)


def _gh_issue_create(cfg: Config, repo: str | None, title: str, body_file: Path, labels: list[str]) -> str:
    gh = _gh()
    base = [str(gh), "issue", "create", "--title", title, "--body-file", str(body_file)]
    if repo:
        base += ["--repo", repo]
    r = run([*base, "--label", ",".join(labels)], cwd=cfg.root, env=clean_env(), timeout_s=120)
    if not r.ok and "label" in (r.stderr or "").lower():
        r = run(base, cwd=cfg.root, env=clean_env(), timeout_s=120)  # labels not created yet: file without them
    if not r.ok:
        raise HarnessError(f"gh issue create failed: {(r.stderr or r.stdout).strip()[:400]}")
    url = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return url


# --- commands --------------------------------------------------------------------------------

def new(cfg: Config, *, kind: str, domain: str, title: str, model: str | None = None,
        attach_last: bool = False, files: list[str] | None = None, notes: str = "",
        submit: bool | None = None) -> dict:
    if kind not in KINDS:
        raise HarnessError(f"kind must be one of {KINDS}")
    if domain not in DOMAINS:
        raise HarnessError(f"domain must be one of {DOMAINS}")
    if model and model not in MODELS:
        raise HarnessError(f"model must be one of {MODELS}")
    title = title.strip()
    if not title:
        raise HarnessError("title is required")
    ticket_id = _next_id(cfg)
    lint_txt, sim_txt, last_files = ("", "", [])
    if attach_last:
        lint_txt, sim_txt, last_files = _summarise_last(cfg)
    rtl_files = [within(cfg.root, f).relative_to(cfg.root).as_posix() for f in (files or [])] or last_files
    template = TEMPLATES / f"{kind}.md"
    body = template.read_text(encoding="utf-8") if template.is_file() else "### Notes\n\n{{notes}}\n"
    env_txt = f"{platform.system()} {platform.release()}, python {sys.version.split()[0]}"
    fills = {
        "id": ticket_id, "kind": kind, "domain": domain, "model": model or "", "title": title,
        "project": cfg.root.name, "harness_version": harness_version(cfg), "date": _dt.date.today().isoformat(),
        "env": env_txt, "last_lint": lint_txt or "(not attached: use --attach-last)",
        "last_sim": sim_txt or "(not attached: use --attach-last)",
        "rtl_files": "\n".join(f"- {f}" for f in rtl_files) or "- (none)", "notes": notes or "(fill in)",
    }
    for k, v in fills.items():
        body = body.replace("{{" + k + "}}", v)
    body = redact(body, cfg.redact)
    meta = {"id": ticket_id, "kind": kind, "domain": domain, "model": model or "", "title": title,
            "status": "open", "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "harness_version": fills["harness_version"], "issue": "", "escalated_to": ""}
    path = tickets_dir(cfg) / f"{ticket_id}-{_slug(title)}.md"
    _write(path, meta, body)

    remote = github_remote(cfg.root)
    if submit is None:
        submit = cfg.tickets_github == "true" or (cfg.tickets_github == "auto" and remote is not None)
    submitted_url = None
    note = ""
    if submit:
        if not remote:
            note = "no GitHub remote: recorded locally only"
        else:
            try:
                labels = [f"kind:{kind}", f"domain:{domain}", "harness"] + ([f"model:{model}"] if model else [])
                submitted_url = _gh_issue_create(cfg, None, f"[{kind}] {title}", path, labels)
                meta["issue"] = submitted_url
                _write(path, meta, body)
            except HarnessError as exc:
                note = f"recorded locally; GitHub issue not created ({exc})"
    return {"id": ticket_id, "path": path.relative_to(cfg.root).as_posix(), "issue": submitted_url, "note": note}


def close(cfg: Config, ticket_id: str, comment: str = "") -> dict:
    t = _find(cfg, ticket_id)
    t["status"] = "closed"
    _write(t["path"], t, t["body"])
    closed_issue = False
    if t.get("issue"):
        r = run([str(_gh()), "issue", "close", t["issue"], *(["--comment", comment] if comment else [])], cwd=cfg.root, env=clean_env(), timeout_s=120)
        closed_issue = r.ok
    return {"id": ticket_id, "status": "closed", "issue_closed": closed_issue}


def escalate(cfg: Config, ticket_id: str, *, yes: bool = False) -> dict:
    t = _find(cfg, ticket_id)
    if t.get("kind") not in ("deviation", "rule", "tool"):
        raise HarnessError("only deviation / rule / tool tickets are escalated to the harness (bugs stay in the project)")
    repo = cfg.escalate_repo
    if not repo or "<" in repo:
        raise HarnessError("harness.toml [tickets].escalate_repo is not set")
    body = redact(t["body"], cfg.redact)
    body = (f"Escalated from project `{cfg.root.name}` ticket `{ticket_id}` (harness {t.get('harness_version', '?')}).\n\n" + body)
    preview = body if len(body) < 4000 else body[:4000] + "\n... (truncated preview)"
    if not yes:
        return {"id": ticket_id, "repo": repo, "submitted": False, "preview": preview,
                "note": "re-run with --yes to create the issue in the harness repository"}
    tmp = cfg.runtime / "escalate.md"
    tmp.write_text(body, encoding="utf-8", newline="\n")
    labels = [f"kind:{t['kind']}", f"domain:{t.get('domain', 'verif')}", "harness"] + ([f"model:{t['model']}"] if t.get("model") else [])
    url = _gh_issue_create(cfg, repo, f"[{t['kind']}] {t['title']}", tmp, labels)
    t["escalated_to"] = url
    _write(t["path"], t, t["body"])
    return {"id": ticket_id, "repo": repo, "submitted": True, "url": url}


# --- CLI wiring ------------------------------------------------------------------------------

def add_arguments(parser) -> None:
    sub = parser.add_subparsers(dest="ticket_cmd", required=True)
    s = sub.add_parser("new", help="record a new ticket")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--domain", required=True, choices=DOMAINS)
    s.add_argument("--title", required=True)
    s.add_argument("--model", choices=MODELS)
    s.add_argument("--attach-last", action="store_true", help="include the latest run_lint / run_sim summaries")
    s.add_argument("--files", nargs="*", help="RTL files involved (project-relative)")
    s.add_argument("--notes", default="")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--submit", action="store_true", help="also create a GitHub issue in this project")
    g.add_argument("--no-submit", action="store_true", help="record locally only")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("list", help="list tickets")
    s.add_argument("--all", action="store_true", help="include closed tickets")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("close", help="close a ticket (and its issue)")
    s.add_argument("id")
    s.add_argument("--comment", default="")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("escalate", help="copy a deviation / rule / tool ticket to the harness repository")
    s.add_argument("id")
    s.add_argument("--yes", action="store_true", help="actually create the issue (otherwise preview only)")
    s.add_argument("--json", action="store_true")


def cli(args) -> int:
    cfg = load_config()
    if args.ticket_cmd == "new":
        submit = True if args.submit else (False if args.no_submit else None)
        r = new(cfg, kind=args.kind, domain=args.domain, title=args.title, model=args.model,
                attach_last=args.attach_last, files=args.files, notes=args.notes, submit=submit)
        print(json.dumps(r, indent=2, ensure_ascii=False) if args.json else f"ticket {r['id']}: {r['path']}" + (f"\n  issue: {r['issue']}" if r["issue"] else "") + (f"\n  note: {r['note']}" if r["note"] else ""))
        return 0
    if args.ticket_cmd == "list":
        rows = [t for t in list_tickets(cfg) if args.all or t.get("status") != "closed"]
        if args.json:
            print(json.dumps([{k: v for k, v in t.items() if k not in ("path", "body")} for t in rows], indent=2, ensure_ascii=False))
        else:
            for t in rows:
                print(f"{t['id']}  {t.get('status', ''):6s} {t.get('kind', ''):9s} {t.get('domain', ''):5s} {t.get('title', '')}" + (f"  {t['issue']}" if t.get("issue") else ""))
            if not rows:
                print("no open tickets")
        return 0
    if args.ticket_cmd == "close":
        r = close(cfg, args.id, args.comment)
        print(json.dumps(r, indent=2) if args.json else f"ticket {r['id']} closed" + (" (issue closed)" if r["issue_closed"] else ""))
        return 0
    if args.ticket_cmd == "escalate":
        r = escalate(cfg, args.id, yes=args.yes)
        if args.json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        elif r["submitted"]:
            print(f"escalated {r['id']} -> {r['url']}")
        else:
            print(r["preview"])
            print(f"\n[{r['note']}]")
        return 0
    return 2


def _unused():  # keep os imported for platforms without symlink support in tests
    return os.name
