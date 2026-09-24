"""harness_tb: the cocotb + Verilator test harness shared by every project.

Imported by test_<block>.py files in the simulation interpreter (pytest host process and, for
the `lib` helpers, inside the Verilated executable's embedded Python). Vendored from the
author's MIPI2HDMI verification environment (see THIRD-PARTY-NOTICES.md) and generalised for
use as a submodule: the consumer project root is discovered through harness.toml.
"""
