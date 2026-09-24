"""rtl-harness: shared AI-agent harness for RTL design.

The package is deliberately standard-library only. Simulation (cocotb) runs in a separate
interpreter driven through ``rtl_harness.sim``; the MCP server in ``mcp/server.py`` is the only
place that imports the ``mcp`` SDK.
"""

__version__ = "0.1.0"
