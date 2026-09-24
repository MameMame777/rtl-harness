# Tool contract (JSON)

The four tools the harness exposes to an AI agent through MCP (`mcp/server.py`). The same
functions back the CLI (`rtl-harness lint|sim|wave|design`), pre-commit and CI, so every entry
point returns exactly these shapes. `list_design` and `get_waveform` are shaped after RTLScope
(`rtlscope dump-ports`, `rtlscope-mcp`) so the Python implementations can later be replaced by
that tool without changing the contract.

Conventions

- Paths are project-relative with forward slashes. Inputs may be relative or absolute but
  must resolve inside the consumer project (anything else is refused).
- `status` is always present. Failures of the *design* are `"fail"`; failures of the *tool*
  come back as `{"status": "error", "error": "<message>"}` (never an exception to the agent).
- Nothing is truncated silently: when output is cut, `clipped` says how much was dropped.
- Every answer carries a `source` object saying what was examined.
- Not-yet-implemented tools answer `{"status": "unimplemented", "phase": "P5", ...}` with the
  keys of the final shape present.

## run_lint

```jsonc
// in
{ "files": ["rtl/skid_buffer.sv"],   // optional; default: every file in harness.toml [design].sources
  "fix": false }                     // true rewrites files with the formatter
// out
{ "status": "pass|fail",             // fail = at least one error, or a file needs formatting and fix=false
  "formatter": { "changed": ["rtl/skid_buffer.sv"], "fixed": false },
  "lint": {
    "errors": [ { "file": "rtl/skid_buffer.sv", "line": 12, "col": 5,
                  "rule": "always-comb", "message": "Use 'always_comb' instead of 'always @*'.",
                  "severity": "error|warning", "tool": "verible|verilator|custom" } ],
    "counts": { "error": 1, "warning": 0 } },
  "lint_off_added": [ { "file": "rtl/x.sv", "line": 40, "text": "// verilator lint_off WIDTH" } ],
  "source": { "rules_version": "0.1.0", "files": ["rtl/skid_buffer.sv"], "duration_s": 0.8 } }
```

Severity comes from `rules/common/rules.toml` (plus `rules/<domain>/rules.toml` for the active
domains); a consumer may only raise it. `lint_off_added` lists suppressions added relative to
`HEAD` (working tree + untracked files); CI blocks them unless a domain owner labels the PR.

## run_sim

```jsonc
// in
{ "block": "skid_buffer",            // name of test_<block>.py found through harness.toml [sim].tests
  "waves": false,                    // true also writes a VCD (see waveform_path)
  "timeout_s": 600 }
// out
{ "status": "pass|fail|timeout|build_error",
  "passed": 3, "failed": 1,
  "first_failure": { "test": "backpressure", "message": "CHECK FAILED: beat 4 (got 7, expected 8)",
                     "sim_time": { "value": 1235.0, "unit": "ns" } },   // null when nothing failed
  "tests": [ { "test": "backpressure", "status": "fail", "time_s": 0.4, "sim_time": { "value": 1235.0, "unit": "ns" } } ],
  "log_path": ".harness/logs/skid_buffer_20260924_120000.log",
  "waveform_path": ".harness/build/skid_buffer_waves/dump.vcd",         // null unless waves=true
  "duration_s": 17.2,
  "source": { "block": "skid_buffer", "test_file": "tb/bus/test_skid_buffer.py",
              "engine": "verilator", "seed": 1, "waves": false, "returncode": 1 } }
```

Only the summary is returned. The full log stays on disk; the agent asks `get_waveform` for the
signals and the time range around `first_failure.sim_time`.

## get_waveform

```jsonc
// in
{ "waveform_path": ".harness/build/skid_buffer_waves/dump.vcd",   // must be under .harness/
  "signals": ["skid_buffer.s_valid", "skid_buffer.s_ready", "skid_buffer.m_data"],
  "t_start": 1200000, "t_end": 1300000,                            // in time_unit; t_end null = end of dump
  "max_changes": 200 }                                            // per signal
// out
{ "status": "pass",
  "signals": [ { "name": "skid_buffer.m_data", "width": 32,
                 "changes": [ [1200000, "0x0000001a"], [1210000, "0x0000001b"] ] } ],
  "clipped": 0,                        // total value changes dropped because of max_changes
  "time_unit": "ps",
  "t_start": 1200000, "t_end": 1300000,
  "missing": ["skid_buffer.m_dta"],    // requested names not present in the dump
  "source": { "waveform_path": ".harness/build/skid_buffer_waves/dump.vcd" } }
```

Values: multi-bit signals as `"0x..."` hex strings, single bits as `"0"`, `"1"`, `"x"`, `"z"`.
`changes[0]` is the value at `t_start`.

## list_design

```jsonc
// in
{ "files": ["rtl/skid_buffer.sv"],    // optional; default: harness.toml [design].sources
  "top": "skid_buffer" }              // optional
// out
{ "status": "pass",
  "top": "skid_buffer",
  "modules": [ { "name": "skid_buffer", "file": "rtl/skid_buffer.sv", "line": 4,
                 "params": [ { "name": "WIDTH", "local": false, "default": "32" } ],
                 "ports":  [ { "name": "clk", "dir": "input", "width": 1, "packed": null },
                             { "name": "s_data", "dir": "input", "width": 32, "packed": "[WIDTH-1:0]" } ],
                 "instances": [ { "name": "u_fifo", "module": "sync_fifo" } ] } ],
  "source": { "tool": "verilator-xml|regex|rtlscope", "files": ["rtl/skid_buffer.sv"] } }
```

## Error shape (any tool)

```json
{ "status": "error", "error": "path is outside the project: ../x.sv" }
```
