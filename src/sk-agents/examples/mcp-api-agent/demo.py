#!/usr/bin/env python3
"""
Demo script showing API MCP server responses.
"""

import asyncio
import json
from pathlib import Path

from sk_agents.mcp_integration import EnhancedMCPPluginFactory, MCPServerConfig


async def demo_api_calls():
    """Demonstrate API calls through MCP server."""
    
    print("🚀 API MCP Server Demo")
    print("=" * 50)
    print("Showing what the agent can do with API calls")
    
    current_dir = Path.cwd()
    server_script = current_dir / "examples/mcp-api-agent/mcp_api_server.py"
    
    config = MCPServerConfig(
        name="api_demo",
        command="python", 
        args=[str(server_script)],
        integration_mode="wrapper",
        timeout=30
    )
    
    plugin = EnhancedMCPPluginFactory.create_from_config([config.model_dump()])
    
    try:
        await plugin.initialize()
        
        print("\n📡 Demo 1: GET Request (GitHub API)")
        print("-" * 40)
        
        result = await plugin.call_mcp_tool(
            server_name="api_demo",
            tool_name="get_api_response", 
            arguments=json.dumps({
                "url": "https://api.github.com/users/octocat",
                "headers": {"Accept": "application/json"}
            })
        )
        
        result_data = json.loads(result)
        if result_data.get("success"):
            content = result_data.get('content', '')
            # Show just the key parts
            lines = content.split('\n')
            for line in lines[:10]:  # First 10 lines
                print(line)
            print("...")
            
        print("\n📮 Demo 2: POST Request (JSONPlaceholder)")
        print("-" * 40)
        
        result = await plugin.call_mcp_tool(
            server_name="api_demo",
            tool_name="post_api_request",
            arguments=json.dumps({
                "url": "https://jsonplaceholder.typicode.com/posts",
                "data": {
                    "title": "Demo Post from MCP Agent",
                    "body": "This post was created through an MCP API server!",
                    "userId": 1
                }
            })
        )
        
        result_data = json.loads(result)
        if result_data.get("success"):
            content = result_data.get('content', '')
            lines = content.split('\n')
            for line in lines[:15]:  # First 15 lines
                print(line)
            print("...")
        
        print("\n🏥 Demo 3: Health Check")
        print("-" * 40)
        
        result = await plugin.call_mcp_tool(
            server_name="api_demo",
            tool_name="api_health_check",
            arguments=json.dumps({"url": "https://api.github.com"})
        )
        
        result_data = json.loads(result)
        if result_data.get("success"):
            content = result_data.get('content', '')
            print(content)
        
        print("\n" + "=" * 50)
        print("🎯 What users can ask the agent:")
        print("• 'Get information about GitHub user octocat'")
        print("• 'Create a test post on JSONPlaceholder'") 
        print("• 'Check if the GitHub API is working'")
        print("• 'Make a POST request to create a new user'")
        print("• 'Get the weather data from OpenWeatherMap API'")
        
        print("\n✨ The agent will:")
        print("• Make the actual HTTP request")
        print("• Show request details (URL, headers, body)")
        print("• Display the full response")
        print("• Explain what the response means")
        print("• Handle errors gracefully")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
    finally:
        await plugin.cleanup()


if __name__ == "__main__":
    asyncio.run(demo_api_calls())