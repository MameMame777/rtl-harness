# Processor domain rules

Scope: pipelines, hazard handling, register files, decoders, ALUs. Read this before writing a
block in this domain; copy the closest example.

| Example | Shows |
| --- | --- |
| `examples/cpu/pipelined_alu.sv` | a valid bit that travels with the data, stage-prefixed registers, `unique case` decode |
| `examples/cpu/hazard_unit.sv` | a purely combinational block with defaults first, forwarding priority, x0 handling |
| `examples/cpu/test_pipelined_alu.py` | golden-model comparison with a fixed latency, bubbles in the input stream |
| `examples/cpu/test_hazard_unit.py` | directed plus random cases against a Python model, no clock needed |

## Pipeline rules

| Rule | Why | Enforced by |
| --- | --- | --- |
| Every stage register carries a `<stage>_valid` bit; data registers load only when the incoming valid is high | bubbles cost nothing and X never propagates into a valid result | review, `examples/cpu/pipelined_alu.sv` |
| Stage registers are named `<stage>_<signal>` (`s1_a`, `s2_result`, `ex_rd`, `mem_rd`) | the stage a value belongs to is visible in every expression | review |
| Combinational decode is `unique case` with a `default` | exactly one item matches; no latch, no X on an unknown opcode | `unique-case` (warning), Verible `case-missing-default` (error) |
| A combinational block assigns every output a default first | no latch, no path left unassigned | Verilator `LATCH` (error), `examples/cpu/hazard_unit.sv` |
| Widths derive from parameters (`$clog2(WIDTH)` for shift amounts, `WIDTH'(...)` for casts) | a WIDTH change never leaves a hidden 32 | Verilator `WIDTH*` (error) |

## Hazards and forwarding

- Forwarding priority: the newest result wins (EX over MEM over WB).
- Register x0 is never forwarded and never written.
- A load in EX whose destination is read in ID stalls for one cycle; forwarding cannot help
  because the data does not exist yet.
- Flushes and stalls are explicit control signals, never inferred from data.

## State machines and control

Same three-process form as the BUS domain (`docs/bus.md`): state register, next-state
`always_comb` with `unique case` and `default`, output `always_comb`. Encode with a typed
enum; never compare raw bit patterns.

## Testing a processor block

Keep a Python golden model next to the test (`examples/cpu/test_pipelined_alu.py`): drive
random operands, record the expected results in order, compare what comes out after the
fixed latency. Test the latency itself once. For combinational blocks drive the inputs, wait
one `Timer` step, and compare (`examples/cpu/test_hazard_unit.py`).
