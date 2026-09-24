# rtl-harness: rules for AI agents writing RTL

This file is the index. Read the domain page before writing, copy the closest example, run the
tools. Domain pages: docs/bus.md, docs/cpu.md, docs/verification.md. Tool contract: docs/tool-schema.md.

## Workflow

1. Read docs/<domain>.md for the block and open the closest file in examples/.
2. Write the RTL under the project's rtl/: one module per file, file name = module name.
3. Call run_lint on the files you touched. Fix every error. Treat a warning as a finding.
4. Write or update tb/test_<block>.py (docs/verification.md), then call run_sim.
5. Only if run_sim fails: call get_waveform for a few signals around first_failure.sim_time.
   Fix the RTL (or the test when the expectation was wrong) and re-run.

## Rules for every file

| Rule | Why | Example |
| --- | --- | --- |
| First line: `` `timescale 1ns / 1ps `` | one time base for every simulation | examples/bus/skid_buffer.sv |
| Module name = file name, `lower_snake_case` | tools find a module by its file | examples/cpu/hazard_unit.sv |
| Parameters `ALL_CAPS` with a type: `parameter int WIDTH = 32` | readable instantiations, no implicit 32-bit | examples/bus/axi4lite_regs.sv |
| Signals `lower_snake_case`; enum types `*_t`; states `PREFIX_NAME` | one vocabulary across projects | examples/bus/axi4lite_regs.sv |
| Reset: synchronous, active-low `rst_n`; `always_ff @(posedge clk)` then `if (!rst_n)` | matches AXI `aresetn`; no async reset trees | examples/bus/skid_buffer.sv |
| Reset every register with `'0` (or a named constant) | no X after reset | examples/cpu/pipelined_alu.sv |
| `always_ff` for registers, `always_comb` for logic; never `always @*` or `always @(posedge clk)` | the tools check intent | all examples |
| Non-blocking `<=` in `always_ff`, blocking `=` in `always_comb` | no races | all examples |
| Every `if` / `else` / `for` body in `begin` ... `end` | edits cannot silently change scope | all examples |
| `case` has a `default`; combinational decode is `unique case` | no latch, no X on unknown input | examples/cpu/pipelined_alu.sv |
| A combinational block assigns every output a default first | no latch | examples/cpu/hazard_unit.sv |
| Widths derive from parameters: `$clog2`, `WIDTH'(...)` casts; no hidden 32-bit | a WIDTH change is complete | examples/cpu/pipelined_alu.sv |
| Three-process state machines with a typed enum | state, transitions and outputs stay separate | examples/bus/axi4lite_regs.sv |
| Line length 100, 4-space indent, no tabs, no trailing spaces; run the formatter | one style, tiny diffs | run_lint fix=true |
| Comments say what the block guarantees, in English ASCII | the next reader may be a tool | all examples |
| No `TODO` / `FIXME`; no placeholder logic | finished code only; open a ticket instead | rtl-harness ticket new |

## Domains

- BUS (valid/ready, AXI4-Stream, AXI4-Lite): docs/bus.md. valid never depends on ready; ready is registered.
- Processor (pipelines, hazards, decode): docs/cpu.md. A valid bit travels with every stage.
- Verification (cocotb tests, helpers, reading failures): docs/verification.md.

## Tools (MCP)

- run_lint(files, fix): formatter + Verible + Verilator + custom checks. Call after every edit.
- run_sim(block, waves): builds and runs tb/test_<block>.py; returns a summary only.
- get_waveform(waveform_path, signals, t_start, t_end): a few signals, a narrow window, after a failure.
- list_design(files): modules, parameters, ports, instances, before writing a test or wiring a block.

## Never

- Add `verilator lint_off`, `verilog_lint: waive`, or a waiver file entry to pass a check.
- Weaken or delete a check in a test to make it pass; edit RTL from a test.
- Use `always @*`, asynchronous resets, or `#delay` in RTL.
- Submit RTL without a test, or a test without a `timeout_time`.
- Write absolute paths, credentials, or company-internal names into any file.
- Pass a path outside the project to a tool.

## When you cannot comply

If a rule cannot be met, a rule contradicts the specification, a tool answers `status: error`,
or you found a bug you did not fix: run `rtl-harness ticket new --kind <bug|deviation|rule|tool>
--domain <bus|cpu|verif> --title "..." --attach-last` to draft a ticket, and ask the human to
submit it. Do not submit it yourself.
