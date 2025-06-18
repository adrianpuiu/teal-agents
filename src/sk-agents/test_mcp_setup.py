#!/usr/bin/env python3
"""Test MCP setup for file listing agent"""

import asyncio
import os
from sk_agents.mcp_integration import SimplifiedMCPClient, MCPServerConfig

async def test_mcp_setup():
    print("🧪 Testing MCP Filesystem Setup")
    print("=" * 40)
    
    # Get current working directory
    current_dir = os.getcwd()
    print(f"📁 Testing directory: {current_dir}")
    
    # Configure MCP server for current directory
    config = MCPServerConfig(
        name='filesystem',
        command='npx',
        args=['@modelcontextprotocol/server-filesystem', current_dir],
        timeout=30.0
    )
    
    try:
        # Test MCP connection
        client = SimplifiedMCPClient(config)
        await client.initialize()
        print("✅ MCP filesystem server connected successfully")
        
        # List available tools
        tools_response = await client.list_tools()
        tools = tools_response.tools if hasattr(tools_response, 'tools') else []
        print(f"✅ Found {len(tools)} available tools:")
        
        for tool in tools[:5]:  # Show first 5 tools
            print(f"   - {tool.name}: {tool.description[:60]}...")
        
        # Test listing current directory
        if any(tool.name == 'list_directory' for tool in tools):
            print(f"\n📋 Testing list_directory for: {current_dir}")
            result = await client.call_tool('list_directory', {'path': current_dir})
            
            if result and isinstance(result, list):
                print(f"✅ Found {len(result)} items in directory:")
                for item in result[:10]:  # Show first 10 items
                    print(f"   - {item}")
                if len(result) > 10:
                    print(f"   ... and {len(result) - 10} more items")
            else:
                print("⚠️ Unexpected result format")
        
        await client.cleanup()
        print("\n🎉 MCP setup test completed successfully!")
        print("✅ Ready to run the file listing agent")
        
    except Exception as e:
        print(f"❌ MCP setup test failed: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Ensure Node.js is installed: node --version")
        print("2. Install MCP server: npm install -g @modelcontextprotocol/server-filesystem")
        print("3. Check current directory permissions")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_mcp_setup())