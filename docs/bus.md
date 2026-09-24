# BUS domain rules

Scope: valid/ready streams, AXI4-Stream, AXI4-Lite slaves and masters. Read this before
writing a block in this domain; copy the closest example.

| Example | Shows |
| --- | --- |
| `examples/bus/skid_buffer.sv` | registered ready, no beat lost or duplicated under backpressure |
| `examples/bus/axi4lite_regs.sv` | three-process FSMs with typed enums, SLVERR for bad accesses, byte strobes |
| `examples/bus/test_skid_buffer.py` | stream test with gaps and backpressure (ValidReadySource / Sink / Monitor) |
| `examples/bus/test_axi4lite_regs.py` | protocol helpers written in the test, order-independent AW/W |

## valid / ready (five rules)

| Rule | Why | Enforced by |
| --- | --- | --- |
| `valid` never depends on `ready` | a source that waits for ready and a sink that waits for valid deadlock | `valid-depends-on-ready` (error) |
| Once `valid` is high, keep `valid` and the payload stable until the beat is accepted (`valid && ready` at a rising edge) | the sink may sample at any cycle | test: Monitor sees each beat once |
| `ready` comes from a register where possible; never chain `ready` combinationally through several blocks | long ready paths limit clock frequency | `combinational-ready-path` (warning); use `skid_buffer` |
| Payload changes only together with `valid` | a monitor must be able to sample data at the handshake | review |
| Reset leaves `valid` low and `ready` in a defined state | no phantom beat after reset | `'0` resets in always_ff |

Naming: `<prefix>_valid`, `<prefix>_ready`, `<prefix>_data` (plus `_last`, `_user` for
AXI4-Stream: `<prefix>_tvalid`, `<prefix>_tready`, `<prefix>_tdata`, ...). Upstream ports use
`s_`, downstream ports `m_`.

## AXI4-Lite slaves

- Address and data beats of a write may arrive in either order; accept each once, respond
  when both are there (`examples/bus/axi4lite_regs.sv`, `aw_pending` / `w_pending`).
- Every response is one of `OKAY` (`2'b00`) or `SLVERR` (`2'b10`). An access that is out of
  range or unaligned answers `SLVERR`; it never hangs the bus.
- Honour `wstrb` byte by byte.
- `bvalid` / `rvalid`, once high, stay high until `bready` / `rready`.
- The register index width is `$clog2(NUM_REGS)`; the byte offset is `$clog2(DATA_WIDTH/8)`.

## State machines

Three processes and a typed enum: the state register (`always_ff`), the next-state logic
(`always_comb`, `unique case` with a `default`), and the output logic (`always_comb`). Name
the type `<name>_state_t` and the states `<PREFIX>_<NAME>` (`WR_IDLE`, `WR_RESP`).

## Testing a bus block

Use `harness_tb.lib.valid_ready` (`ValidReadySource`, `ValidReadySink`, `ValidReadyMonitor`)
or `harness_tb.lib.axis` for AXI4-Stream. Run every stream test twice: continuous, and with
gaps plus backpressure (`GapPolicy("adversarial")` on the source, `GapPolicy("burst")` on the
sink). The scoreboard compares the accepted-beat sequence, which must not depend on timing.
