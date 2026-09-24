"""The enforced rules: Verible / Verilator configuration files, the severity map, and the
custom (Python) checks under rules/common/checks and rules/<domain>/checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import tomllib

from . import paths
from .config import Config
from .errors import ConfigError

COMMON = paths.harness_root() / "rules" / "common"
SEVERITIES = ("error", "warning")


def domain_dir(domain: str) -> Path:
    return paths.harness_root() / "rules" / domain


def verible_rules_file() -> Path:
    return COMMON / "verible-lint.rules"


def verible_format_flags() -> Path:
    return COMMON / "verible-format.flags"


def verilator_flags() -> list[str]:
    out = []
    for line in (COMMON / "verilator-lint.flags").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.extend(line.split())
    return out


def waiver_files(cfg: Config) -> list[Path]:
    files = [COMMON / "waivers.verible"]
    if cfg.waiver:
        from ._safety import within

        files.append(within(cfg.root, cfg.waiver))
    return [f for f in files if f.is_file()]


def _load_rules_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from None


def rules_version() -> str:
    return str(_load_rules_toml(COMMON / "rules.toml").get("meta", {}).get("version", "0"))


def load_severities(cfg: Config) -> dict[str, dict[str, str]]:
    """tool -> {rule (or 'PREFIX*' or 'default') -> severity}. Common first, then the active
    domains, then the consumer's overrides (which may only raise a severity)."""
    merged: dict[str, dict[str, str]] = {"verible": {}, "verilator": {}, "custom": {}}
    layers = [COMMON / "rules.toml"] + [domain_dir(d) / "rules.toml" for d in cfg.domains]
    for layer in layers:
        for tool, table in _load_rules_toml(layer).get("severity", {}).items():
            merged.setdefault(tool, {}).update({str(k): str(v) for k, v in table.items()})
    for key, sev in cfg.severity_overrides.items():
        if sev not in SEVERITIES:
            raise ConfigError(f"[lint].severity_overrides: {key} = {sev!r} (use error|warning)")
        tool, _, rule = key.partition(":")
        if not rule:
            raise ConfigError(f"[lint].severity_overrides: keys look like 'verible:line-length', got {key!r}")
        table = merged.setdefault(tool, {})
        current = severity_for(merged, tool, rule)
        if sev == "error" or current == sev:
            table[rule] = sev
        else:
            raise ConfigError(f"[lint].severity_overrides may only raise severities: {key} is {current}")
    return merged


def severity_for(sev_map: dict[str, dict[str, str]], tool: str, rule: str) -> str:
    table = sev_map.get(tool, {})
    if rule in table:
        return table[rule]
    best = None
    for key, sev in table.items():
        if key.endswith("*") and rule.startswith(key[:-1]) and (best is None or len(key) > len(best[0])):
            best = (key, sev)
    if best:
        return best[1]
    return table.get("default", "warning")


def load_checks(cfg: Config) -> list[ModuleType]:
    """Custom checks: rules/common/checks/*.py plus rules/<domain>/checks/*.py for each active
    domain. A check module exposes RULE (str) and check(path, text) -> list[dict]."""
    dirs = [COMMON / "checks"] + [domain_dir(d) / "checks" for d in cfg.domains]
    mods: list[ModuleType] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            if f.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(f"rtl_harness_check_{d.parent.name}_{f.stem}", f)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "RULE") or not callable(getattr(mod, "check", None)):
                raise ConfigError(f"{f}: a check module needs RULE and check(path, text)")
            mods.append(mod)
    return mods
