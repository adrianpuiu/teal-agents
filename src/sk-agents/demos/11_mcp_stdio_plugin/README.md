# MCP Stdio Plugin Demo

This demo showcases how to define, load, and use a remote plugin that communicates over standard input/output (stdio) using the MCP (Meta-Cognitive Plugins) protocol.

## Components

1.  **`mcp_stdio_server.py`**:
    *   A simple Python script that defines a Semantic Kernel plugin (`EchoPlugin`) with one function (`echo_input`).
    *   It uses `semantic_kernel.connectors.mcp.as_mcp_server` to expose this kernel as an MCP server that communicates over stdio.
    *   When run, it waits for MCP requests on stdin and sends MCP responses to stdout.

2.  **`remote_plugins_mcp_demo.yaml`**:
    *   A YAML configuration file that defines the "EchoMCP" remote plugin.
    *   It specifies `mcp_plugin_type: "stdio"` and provides the command (`python`) and arguments (`src/sk-agents/demos/11_mcp_stdio_plugin/mcp_stdio_server.py`) to launch the `mcp_stdio_server.py`.

3.  **`main.py`**:
    *   The main script that demonstrates loading and invoking the "EchoMCP" plugin.
    *   It sets up the necessary application configuration (`AppConfig`) to point to `remote_plugins_mcp_demo.yaml`.
    *   It uses `KernelBuilder` to create a Semantic Kernel instance, loading the "EchoMCP" plugin as a remote plugin.
    *   It then invokes the `echo_input` function of the "EchoMCP" plugin and prints the result.
    *   The script also includes basic logic to attempt to shut down the MCP plugin process upon completion.

## Prerequisites

Ensure you have the necessary package installed with MCP support:

```bash
pip install semantic-kernel[mcp]
# You might also need anyio if not installed as a dependency of semantic-kernel[mcp]
pip install anyio httpx pydantic pydantic-yaml ska-utils
```
(Ensure `ska-utils` and other dependencies of `sk-agents` are also installed, typically by installing `sk-agents` itself.)

## How to Run

1.  Navigate to the root directory of the `sk-agents` project.
2.  Run the `main.py` script for this demo:

    ```bash
    python src/sk-agents/demos/11_mcp_stdio_plugin/main.py
    ```

You should see output indicating:
*   The MCP server starting (from `mcp_stdio_server.py`'s print statements, which will be interleaved if the subprocess output is not fully captured/redirected by the MCP client, or visible via the MCP client's logging).
*   The `main.py` script building the kernel.
*   The `main.py` script invoking the `EchoMCP.echo_input` function.
*   The MCP server receiving the call and sending a response (again, server prints).
*   The final echoed result printed by `main.py`.
*   Attempts to shut down the MCP plugin.

The `mcp_stdio_server.py` script will be launched as a subprocess by the `MCPStdioPlugin` when the plugin is loaded by the `RemotePluginLoader`.
```
