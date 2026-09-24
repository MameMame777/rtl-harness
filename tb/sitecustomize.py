"""Runs at interpreter start-up inside the cocotb SIMULATION process (the Verilated exe with
embedded Python), found through the PYTHONPATH cocotb's runner exports (tb/ is on it because
harness_tb.site.prepend_path puts it on sys.path in the host).

WA#8 (Windows): an extension module's (.pyd) dependent DLLs are resolved from the executable's
directory + AddDllDirectory dirs + System32, never from PATH. The Verilated exe lives in the
build dir, so ucrt64's runtime DLLs are invisible and even `import binascii` fails with "DLL
load failed". os.add_dll_directory registers them; the dirs arrive in COCOTB_DLL_DIRS.
"""

import os

for _d in os.environ.get("COCOTB_DLL_DIRS", "").split(os.pathsep):
    if _d and os.path.isdir(_d) and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(_d)
        except OSError:
            pass
