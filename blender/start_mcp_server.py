"""Start the Blender MCP socket server and keep Blender open.

Usage (portable Blender on this machine):

    & 'D:\\AstraForge\\runtime\\blender\\blender-5.0.1-windows-x64\\blender.exe' `
      --python G:\\stageforge\\blender\\start_mcp_server.py

Does exactly what the sidebar button "Connect to MCP server" does:
enables the installed `blender_mcp` addon, turns on the per-session
auto-start flag and starts the server on 127.0.0.1:9876. Idempotent —
a second start reports "already in use" and does nothing.

The GUI window stays open; closing it stops the server.
"""

import bpy

# 1) enable the addon installed by `uvx mcp-for-blender install-addon`
try:
    bpy.ops.preferences.addon_enable(module="blender_mcp")
    print("ADDON ENABLED")
except Exception as exc:  # noqa: BLE001 — surfaced verbatim for the caller
    print(f"ADDON ENABLE FAILED: {exc}")

# 2) make sure this session auto-starts the socket server
try:
    bpy.context.scene.blendermcp_auto_start_server = True
    print("AUTO_START=True")
except Exception as exc:  # noqa: BLE001
    print(f"AUTO_START set failed: {exc}")

# 3) belt & braces: start the server directly (idempotent if already up)
try:
    bpy.ops.blendermcp.start_server()
    print("SERVER START REQUESTED")
except Exception as exc:  # noqa: BLE001
    print(f"start_server: {exc}")
