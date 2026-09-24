"""harness.toml: the consumer project's settings (the only hand-written configuration)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

from . import __version__, paths
from ._safety import safe_glob
from .errors import ConfigError

SCHEMA = 1


@dataclass
class Config:
    root: Path
    raw: dict = field(repr=False)
    # [design]
    sources: list[str]
    includes: list[str]
    defines: list[str]
    exclude: list[str]
    top: str
    # [domains]
    domains: list[str]
    # [lint]
    waiver: str | None
    severity_overrides: dict[str, str]
    # [sim]
    tests: list[str]
    manifest: str | None
    engine: str
    build_dir: str
    # [sync]
    sync_tools: list[str]
    extra_instructions: str
    # [tickets]
    tickets_dir: str
    tickets_github: str
    escalate_repo: str
    redact: list[str]

    @property
    def runtime(self) -> Path:
        return paths.runtime_dir(self.root)

    @property
    def is_self(self) -> bool:
        return self.root.resolve() == paths.harness_root().resolve()


def _as_list(v, what: str) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return list(v)
    raise ConfigError(f"{what} must be a string or a list of strings")


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def satisfies(version: str, spec: str) -> bool:
    """Minimal PEP 440-style check for specs like '>=0.1,<1'."""
    have = _version_tuple(version)
    for clause in [c.strip() for c in spec.split(",") if c.strip()]:
        m = re.fullmatch(r"(>=|<=|==|>|<|!=)\s*([0-9][0-9.]*)", clause)
        if not m:
            raise ConfigError(f"unsupported version clause: {clause!r}")
        op, want = m.group(1), _version_tuple(m.group(2))
        pad = max(len(have), len(want))
        a, b = have + (0,) * (pad - len(have)), want + (0,) * (pad - len(want))
        ok = {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b, "!=": a != b}[op]
        if not ok:
            return False
    return True


def load_config(root: Path | None = None) -> Config:
    root = (root or paths.consumer_root()).resolve()
    cfg_path = root / paths.CONFIG_NAME
    try:
        raw = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{cfg_path} not found") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{cfg_path}: {exc}") from None

    h = raw.get("harness", {})
    if h.get("schema", SCHEMA) != SCHEMA:
        raise ConfigError(f"{cfg_path}: unsupported schema {h.get('schema')} (this harness reads {SCHEMA})")
    req = h.get("require")
    if req and not satisfies(__version__, str(req)):
        raise ConfigError(f"{cfg_path} requires harness {req}, but this harness is {__version__}")

    d, l, s, y, t = (raw.get(k, {}) for k in ("design", "lint", "sim", "sync", "tickets"))
    domains = _as_list(raw.get("domains", {}).get("active", []), "[domains].active")
    for dom in domains:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", dom):
            raise ConfigError(f"[domains].active: invalid domain name {dom!r}")
    return Config(
        root=root,
        raw=raw,
        sources=_as_list(d.get("sources", ["rtl/**/*.sv"]), "[design].sources"),
        includes=_as_list(d.get("includes", []), "[design].includes"),
        defines=_as_list(d.get("defines", []), "[design].defines"),
        exclude=_as_list(d.get("exclude", []), "[design].exclude"),
        top=str(d.get("top", "") or ""),
        domains=domains,
        waiver=(str(l["waiver"]) if l.get("waiver") else None),
        severity_overrides={str(k): str(v) for k, v in dict(l.get("severity_overrides", {})).items()},
        tests=_as_list(s.get("tests", ["tb/**/test_*.py"]), "[sim].tests"),
        manifest=(str(s["manifest"]) if s.get("manifest") else None),
        engine=str(s.get("engine", "verilator")),
        build_dir=str(s.get("build_dir", ".harness/build")),
        sync_tools=_as_list(y.get("tools", ["claude", "copilot"]), "[sync].tools"),
        extra_instructions=str(y.get("extra_instructions", "") or ""),
        tickets_dir=str(t.get("dir", "tickets")),
        tickets_github=str(t.get("github", "auto")),
        escalate_repo=str(t.get("escalate_repo", "") or ""),
        redact=_as_list(t.get("redact", []), "[tickets].redact"),
    )


def design_files(cfg: Config) -> list[Path]:
    return safe_glob(cfg.root, cfg.sources, cfg.exclude)


def test_files(cfg: Config) -> dict[str, Path]:
    """block name -> test_<block>.py, from [sim].tests."""
    out: dict[str, Path] = {}
    for p in safe_glob(cfg.root, cfg.tests, [], suffixes=(".py",)):
        if p.name.startswith("test_"):
            out.setdefault(p.stem[len("test_"):], p)
    return out
