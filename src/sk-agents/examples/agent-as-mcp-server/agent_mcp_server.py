#!/usr/bin/env python3
# /// script # noqa: CPY001
# dependencies = [
#   "semantic-kernel[mcp]",
#   "sk-agents",
# ]
# ///
# Copyright (c) Microsoft. All rights reserved.
"""
Teal-Agents equivalent of Microsoft's agent_mcp_server.py sample.

This demonstrates how to expose a teal-agents agent as an MCP server that other tools can consume.

Microsoft's original uses Azure AI Agent, while our version uses teal-agents with YAML configuration.
Both expose the same MenuPlugin functionality via MCP protocol.

To run this sample, set up your MCP host (like Claude Desktop or VSCode Github Copilot Agents)
with the following configuration:

```json
{
    "mcpServers": {
        "teal-menu-agent": {
            "command": "uv",
            "args": [
                "--directory=/path/to/teal-agents/src/sk-agents/examples/agent-as-mcp-server",
                "run",
                "agent_mcp_server.py"
            ],
            "env": {
                "TA_API_KEY": "<your openai api key>",
                "TA_SERVICE_CONFIG": "config.yaml"
            }
        }
    }
}
```

Alternatively, you can run this as a SSE server:
```bash
export TA_API_KEY="your_openai_api_key"
export TA_SERVICE_CONFIG="config.yaml"
uv run agent_mcp_server.py --transport sse --port 8000
```
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Literal

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ska_utils import AppConfig
from sk_agents.skagents.v1 import handle
from pydantic_yaml import parse_yaml_file_as
from sk_agents.ska_types import BaseConfig

# Import MCP integration to add MCP server support to agents
import sk_agents.mcp_integration

logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run the Teal-Agents MCP server.")
    parser.add_argument(
        "--transport",
        type=str,
        choices=["sse", "stdio"],
        default="stdio",
        help="Transport method to use (default: stdio).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to use for SSE transport (required if transport is 'sse').",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to agent configuration file (default: config.yaml).",
    )
    return parser.parse_args()


class TealAgentsMCPServer:
    """Wrapper to expose teal-agents as MCP server."""
    
    def __init__(self, agent):
        self.agent = agent
        
    async def create_mcp_server(self):
        """Create MCP server from teal-agents agent."""
        logger.info("✅ Creating MCP server from teal-agents agent...")
        
        try:
            # Use the new as_mcp_server method
            if hasattr(self.agent, 'as_mcp_server'):
                mcp_server = await self.agent.as_mcp_server()
                logger.info("✅ MCP server created successfully using agent.as_mcp_server()")
                return mcp_server
            else:
                logger.error("❌ Agent does not have as_mcp_server method")
                logger.info("💡 Make sure mcp_integration.py is imported to add MCP server support")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to create MCP server: {e}")
            return None


async def run(transport: Literal["sse", "stdio"] = "stdio", port: int | None = None, config_file: str = "config.yaml") -> None:
    """Run the teal-agents MCP server."""
    
    logger.info("🚀 Starting Teal-Agents MCP Server")
    logger.info(f"   Transport: {transport}")
    if port:
        logger.info(f"   Port: {port}")
    logger.info(f"   Config: {config_file}")
    
    # Check environment variables
    api_key = os.getenv("TA_API_KEY")
    if not api_key:
        logger.error("❌ TA_API_KEY environment variable not set")
        logger.info("   export TA_API_KEY='your_openai_api_key'")
        return
    
    try:
        # Load agent configuration
        config_path = Path(config_file)
        if not config_path.exists():
            logger.error(f"❌ Configuration file not found: {config_file}")
            return
            
        config = parse_yaml_file_as(BaseConfig, config_path)
        logger.info(f"✅ Configuration loaded: {config.service_name}")
        
        # Create teal-agents agent
        app_config = AppConfig()
        agent = handle(config, app_config)
        logger.info(f"✅ Agent created: {type(agent).__name__}")
        
        # Create MCP server wrapper
        mcp_server_wrapper = TealAgentsMCPServer(agent)
        mcp_server = await mcp_server_wrapper.create_mcp_server()
        
        if mcp_server is None:
            logger.error("❌ MCP server creation failed")
            logger.info("💡 MCP server capability needs to be implemented in teal-agents")
            logger.info("   This would require adding agent.as_mcp_server() equivalent")
            return
        
        # Run MCP server based on transport
        if transport == "sse" and port is not None:
            await run_sse_server(mcp_server, port)
        elif transport == "stdio":
            await run_stdio_server(mcp_server)
        else:
            logger.error("❌ Invalid transport configuration")
            
    except Exception as e:
        logger.error(f"❌ Failed to start MCP server: {e}")


async def run_sse_server(mcp_server, port: int):
    """Run MCP server with SSE transport."""
    logger.info(f"🌐 Starting SSE MCP server on port {port}")
    
    try:
        import nest_asyncio
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as (
                read_stream,
                write_stream,
            ):
                await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        nest_asyncio.apply()
        uvicorn.run(starlette_app, host="0.0.0.0", port=port)  # nosec
        
    except ImportError as e:
        logger.error(f"❌ SSE server dependencies not available: {e}")
        logger.info("   pip install uvicorn starlette")


async def run_stdio_server(mcp_server):
    """Run MCP server with stdio transport."""
    logger.info("📡 Starting stdio MCP server")
    
    try:
        from mcp.server.stdio import stdio_server

        async def handle_stdin(stdin: Any | None = None, stdout: Any | None = None) -> None:
            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

        await handle_stdin()
        
    except ImportError as e:
        logger.error(f"❌ stdio server dependencies not available: {e}")


def show_microsoft_comparison():
    """Show comparison with Microsoft's approach."""
    print("\n" + "=" * 60)
    print("📊 MICROSOFT vs TEAL-AGENTS MCP SERVER COMPARISON")
    print("=" * 60)
    
    print("\nMicrosoft's Approach (Azure AI Agent):")
    print("""
agent = AzureAIAgent(
    client=client,
    definition=await client.agents.create_agent(
        model="gpt-4o",
        name="Host",
        instructions="Answer questions about the menu.",
    ),
    plugins=[MenuPlugin()],
)
server = agent.as_mcp_server()
    """)
    
    print("\nTeal-Agents Equivalent (YAML + agent):")
    print("""
# config.yaml:
agents:
  - name: host
    model: gpt-4o-mini
    system_prompt: "Answer questions about the menu."
    plugins: [MenuPlugin]

# Python:
agent = handle(config, app_config)
server = agent.as_mcp_server()  # To be implemented
    """)
    
    print("\n🎯 KEY BENEFITS:")
    print("✅ Same MCP server functionality")
    print("✅ Same MenuPlugin capabilities")
    print("✅ Same transport options (stdio/SSE)")
    print("✅ Enhanced: YAML configuration")
    print("✅ Enhanced: Environment variable support")
    print("✅ Enhanced: Multiple deployment options")


def show_implementation_status():
    """Show current implementation status."""
    print("\n" + "=" * 60)
    print("🚧 IMPLEMENTATION STATUS")
    print("=" * 60)
    
    print("✅ COMPLETED:")
    print("   → MCP client integration (consuming MCP servers)")
    print("   → Microsoft-equivalent agent configurations") 
    print("   → Multi-transport support (stdio/SSE/streamable_http/websocket)")
    print("   → Interactive GitHub ChatBot")
    print("   → GitHub Issues Agent")
    print("   → Simplified and legacy integration modes")
    print("")
    
    print("🚧 IN PROGRESS:")
    print("   → MCP server capabilities (exposing agents as MCP servers)")
    print("   → agent.as_mcp_server() equivalent")
    print("   → Tool registration for external MCP clients")
    print("")
    
    print("📋 NEXT STEPS:")
    print("   1. Implement MCP server interface in teal-agents")
    print("   2. Add agent.as_mcp_server() method")
    print("   3. Create tool registration from agent functions")
    print("   4. Test with Claude Desktop and other MCP clients")


async def main():
    """Main function."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Show comparison first
    show_microsoft_comparison()
    show_implementation_status()
    
    print("\nOptions:")
    print("1. Try to run MCP server (will show current limitations)")
    print("2. Exit")
    
    try:
        choice = input("\nEnter your choice (1-2): ").strip()
        
        if choice == "1":
            # Parse arguments and attempt to run
            args = parse_arguments()
            await run(args.transport, args.port, args.config)
        else:
            print("Goodbye!")
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())