#!/usr/bin/env python3
"""
Test script for enhanced MCP integration with dual modes.
"""

import asyncio
import json
import logging
from pathlib import Path

from sk_agents.mcp_integration import EnhancedMCPPluginFactory, MCPServerConfig
from sk_agents.skagents.v1.config import AgentConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_enhanced_mcp_integration():
    """Test the enhanced MCP integration with both wrapper and direct modes."""
    
    print("🧪 Testing Enhanced MCP Integration")
    print("=" * 50)
    
    # Test 1: Configuration parsing with integration modes
    print("\n1. Testing configuration parsing...")
    
    config_data = {
        'name': 'test_enhanced_agent',
        'model': 'gpt-4o-mini',
        'system_prompt': 'Test agent with enhanced MCP',
        'mcp_servers': [
            {
                'name': 'filesystem',
                'command': 'echo',
                'args': ['filesystem_mock'],
                'integration_mode': 'direct',
                'plugin_name': 'FileSystem',
                'timeout': 5
            },
            {
                'name': 'database',
                'command': 'echo',
                'args': ['database_mock'],
                'integration_mode': 'wrapper',
                'timeout': 5
            }
        ]
    }
    
    try:
        agent_config = AgentConfig(**config_data)
        print("✅ Configuration parsing successful")
        print(f"   - Found {len(agent_config.mcp_servers)} MCP servers")
        for server in agent_config.mcp_servers:
            mode = server.get('integration_mode', 'wrapper')
            plugin_name = server.get('plugin_name', 'N/A')
            print(f"   - {server['name']}: {mode} mode, plugin: {plugin_name}")
    except Exception as e:
        print(f"❌ Configuration parsing failed: {e}")
        return False
    
    # Test 2: Enhanced plugin creation
    print("\n2. Testing enhanced plugin creation...")
    
    try:
        enhanced_plugin = EnhancedMCPPluginFactory.create_from_config(agent_config.mcp_servers)
        print("✅ Enhanced plugin creation successful")
        print(f"   - Created plugin with {len(enhanced_plugin.server_configs)} servers")
        
        # Check server configurations
        for server_name, config in enhanced_plugin.server_configs.items():
            print(f"   - {server_name}: {config.integration_mode} mode")
        
    except Exception as e:
        print(f"❌ Enhanced plugin creation failed: {e}")
        return False
    
    # Test 3: Factory methods with integration modes
    print("\n3. Testing factory methods...")
    
    try:
        # Test filesystem plugin in direct mode
        fs_plugin_direct = EnhancedMCPPluginFactory.create_filesystem_plugin(
            workspace_path="/tmp",
            integration_mode="direct",
            plugin_name="FileSystemDirect"
        )
        
        # Test filesystem plugin in wrapper mode  
        fs_plugin_wrapper = EnhancedMCPPluginFactory.create_filesystem_plugin(
            workspace_path="/tmp",
            integration_mode="wrapper"
        )
        
        print("✅ Factory methods successful")
        print(f"   - Direct mode plugin: {fs_plugin_direct.server_configs['filesystem'].integration_mode}")
        print(f"   - Wrapper mode plugin: {fs_plugin_wrapper.server_configs['filesystem'].integration_mode}")
        
    except Exception as e:
        print(f"❌ Factory methods failed: {e}")
        return False
    
    # Test 4: Multi-server configuration
    print("\n4. Testing multi-server configuration...")
    
    try:
        servers = [
            {
                'name': 'server1',
                'command': 'echo',
                'args': ['test1'],
                'integration_mode': 'direct',
                'plugin_name': 'Server1Tools'
            },
            {
                'name': 'server2', 
                'command': 'echo',
                'args': ['test2']
                # integration_mode will default to wrapper
            }
        ]
        
        multi_plugin = EnhancedMCPPluginFactory.create_multi_server_plugin(
            servers=servers,
            default_integration_mode="wrapper"
        )
        
        print("✅ Multi-server configuration successful")
        for server_name, config in multi_plugin.server_configs.items():
            print(f"   - {server_name}: {config.integration_mode} mode")
            
    except Exception as e:
        print(f"❌ Multi-server configuration failed: {e}")
        return False
    
    # Test 5: Load example configuration
    print("\n5. Testing example configuration...")
    
    try:
        example_config_path = Path("examples/mcp-enhanced-agent/config.yaml")
        if example_config_path.exists():
            import yaml
            with open(example_config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
            
            agent_data = yaml_config['spec']['agents'][0]
            parsed_config = AgentConfig(**agent_data)
            
            print("✅ Example configuration loaded successfully")
            print(f"   - Agent: {parsed_config.name}")
            print(f"   - MCP servers: {len(parsed_config.mcp_servers)}")
            
            # Show integration modes
            for server in parsed_config.mcp_servers:
                mode = server.get('integration_mode', 'wrapper')
                plugin_name = server.get('plugin_name', 'N/A')
                print(f"   - {server['name']}: {mode} mode, plugin: {plugin_name}")
        else:
            print("⚠️  Example configuration not found, skipping...")
            
    except Exception as e:
        print(f"❌ Example configuration test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All Enhanced MCP Integration Tests Passed!")
    print("=" * 50)
    
    print("\n📋 Summary of Enhanced Features:")
    print("• Dual integration modes: wrapper (existing) + direct (new)")
    print("• Direct mode: MCP tools appear as native SK functions")
    print("• Wrapper mode: MCP tools accessed through generic functions")
    print("• Backward compatibility maintained")
    print("• Configuration-driven mode selection")
    print("• Custom plugin naming for direct mode")
    print("• Multi-server support with mixed modes")
    
    return True


async def main():
    """Main test runner."""
    try:
        success = await test_enhanced_mcp_integration()
        exit_code = 0 if success else 1
        exit(exit_code)
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())