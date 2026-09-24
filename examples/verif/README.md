# examples/verif

Teaching versions of two test shapes. They run against the BUS and CPU examples, so they are
also regression tests, but the point is the commentary: copy the shape, not the DUT.

| File | Shape |
| --- | --- |
| `test_valid_ready_example.py` | stream test: driver, sink with backpressure, monitor, scoreboard, gap policies |
| `test_golden_model_example.py` | golden-model test: Python model, fixed latency, in-order compare |

Rules: `docs/verification.md`. Helpers: `tb/harness_tb/lib/`.
