import asyncio
from typing import Annotated

import anyio
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.connectors.mcp import as_mcp_server

class EchoPlugin:
    """
    A simple plugin that echoes back the input.
    """
    @kernel_function(name="echo_input", description="Echoes back the input string.")
    def echo(self, input_str: Annotated[str, "The string to echo."]) -> str:
        print(f"MCP Server: Received call to echo_input with '{input_str}'")
        response = f"MCP Echo: {input_str}"
        print(f"MCP Server: Sending response '{response}'")
        return response

async def main():
    # Create a kernel
    kernel = Kernel()

    # Add the EchoPlugin
    kernel.add_plugin(EchoPlugin(), plugin_name="EchoPlugin")
    print("MCP Server: EchoPlugin added to kernel.")

    # Expose the kernel as an MCP server over stdio
    stdio_server = as_mcp_server(kernel, name="StdioEchoServer", version="1.0")
    print("MCP Server: Kernel exposed as MCP server. Waiting for requests...")

    # Handle stdin requests
    # For some reason, mypy complains about stdio_server not being a callable,
    # but it works.
    await anyio.run(stdio_server) # type: ignore


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("MCP Server: Shutting down...")
    except Exception as e:
        print(f"MCP Server: An error occurred: {e}")
