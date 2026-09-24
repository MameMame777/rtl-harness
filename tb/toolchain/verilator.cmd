#!perl
# WA#2 (Windows-native cocotb + Verilator). cocotb's runner resolves the simulator with
# shutil.which("verilator") and then runs `perl <that path>`. On MSYS2 ucrt64 the only PATHEXT
# match is verilator.bat, a cmd batch file perl cannot parse. harness_tb.site.prepend_path puts
# this directory first on PATH so shutil.which returns THIS file instead; run as
# `perl verilator.cmd` it execs the real verilator_bin.exe (on PATH in ucrt64/bin) with
# VERILATOR_ROOT already exported.
#
# The .cmd extension exists only so shutil.which matches it; the body is perl, not batch.
exec("verilator_bin.exe", @ARGV);
die "rtl-harness verilator wrapper: failed to exec verilator_bin.exe (is ucrt64/bin on PATH?): $!\n";
