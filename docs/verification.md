# Verification rules

Scope: cocotb tests (`tb/` in a consumer project), the shared helpers in `tb/harness_tb/lib`,
and how to read a failure. Read this before writing a test; copy the closest example.

| Example | Shows |
| --- | --- |
| `examples/verif/test_valid_ready_example.py` | the anatomy of a stream test: driver, monitor, scoreboard, gaps |
| `examples/verif/test_golden_model_example.py` | golden-model comparison with a fixed pipeline latency |
| `tb/smoke/test_smoke_counter.py` | the smallest complete test |

## The two-process model

pytest runs `def test_<block>()` in the host process; that function calls
`harness_tb.runner_support.build_and_test(...)`, which builds the DUT with Verilator and
starts the simulation. The `@cocotb.test()` coroutines in the same file run inside the
Verilated executable (embedded Python). Consequences:

- coroutine names must NOT start with `test_` (pytest would try to run them without a DUT);
- the file is imported twice; keep module-level code to constants and imports;
- one block = one `test_<block>.py`; the block name is what `run_sim` takes.

```python
def test_my_block():
    from harness_tb.runner_support import build_and_test
    build_and_test(block="my_block", sources=["rtl/my_block.sv"], toplevel="my_block",
                   test_dir=Path(__file__).parent, parameters={"WIDTH": 8})
```

`sources` are relative to the consumer project root.

## Rules

| Rule | Why | Enforced by |
| --- | --- | --- |
| Bring-up through `harness_tb.lib.clkreset.bringup` (100 MHz, synchronous active-low `rst_n`) | every test starts the same way | review |
| Drive clocks with `cocotb.clock.Clock`, never with a `Timer` polling loop | a stalled polling loop takes hours to hit a timeout | review |
| Sample right after `await RisingEdge(clk)`; write new values in the same step | that is the value the edge sampled; the write is seen by the next edge | helpers in `harness_tb.lib` |
| Check with `check` / `check_eq` / `Scoreboard`; a failing check raises `CHECK FAILED: ...` | one grep-able token in every log | `harness_tb.lib.scoreboard` |
| Every `@cocotb.test()` has `timeout_time` | a hang becomes a failure, not a stuck CI | review |
| Stream tests run continuous AND with gaps plus backpressure | handshake bugs hide under continuous valid | `GapPolicy` |
| The seed is pinned (`COCOTB_SEED=1`, set by the harness) | a flaky test means a phase-fragile drive, not bad luck | `runner_support` |
| Never weaken or delete a check to go green; never edit RTL from a test file | the check is the specification | review |
| Tests are code: only reviewed tests run in CI and through `run_sim` | `run_sim` executes the Python in the test file | CODEOWNERS |

## Reading a failure

`run_sim` returns only a summary: `status`, `passed` / `failed`, and `first_failure` with the
test name, the `CHECK FAILED` message and `sim_time`. Then:

1. Re-run with `waves=true` to get `waveform_path`.
2. Call `get_waveform` for the handful of signals involved (clock, valid/ready, the data)
   over a window of a few hundred ns around `first_failure.sim_time`.
3. Fix the RTL, or the test if the expectation was wrong, and re-run.

The full log stays at `log_path`; read it only when the summary is not enough.
