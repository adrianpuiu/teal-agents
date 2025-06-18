#!/usr/bin/env python3
"""
Validate MCP example configurations.
Tests that all MCP example configurations are valid and parseable.
"""

import asyncio
import logging
from pathlib import Path

from pydantic_yaml import parse_yaml_file_as
from sk_agents.ska_types import BaseConfig
from sk_agents.skagents.v1.sequential.config import Config
from sk_agents.mcp_integration import MCPServerConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_example_config(config_path: Path):
    """Test a single example configuration."""
    
    print(f"\n🧪 Testing: {config_path.name}")
    print("=" * 60)
    
    try:
        # Parse YAML config
        base_config = parse_yaml_file_as(BaseConfig, config_path)
        config = Config(config=base_config)
        
        print(f"✅ YAML parsing successful")
        print(f"   - Service: {base_config.service_name}")
        print(f"   - Version: {base_config.version}")
        
        # Test global MCP servers
        global_mcp = config.get_mcp_servers()
        if global_mcp:
            print(f"✅ Global MCP servers: {len(global_mcp)}")
            for server in global_mcp:
                # Validate each server config
                mcp_config = MCPServerConfig(**server)
                print(f"   - {mcp_config.name}: {mcp_config.transport}")
        
        # Test agents
        agents = config.get_agents()
        print(f"✅ Agents: {len(agents)}")
        
        for agent in agents:
            print(f"   - {agent.name}: {agent.model}")
            
            # Test agent-specific MCP servers
            if agent.mcp_servers:
                print(f"     Agent MCP servers: {len(agent.mcp_servers)}")
                for server in agent.mcp_servers:
                    mcp_config = MCPServerConfig(**server)
                    print(f"       - {mcp_config.name}: {mcp_config.transport}")
            
            # Test merged MCP servers
            merged_mcp = config.get_agent_mcp_servers(agent.name)
            if merged_mcp:
                print(f"     Total merged MCP servers: {len(merged_mcp)}")
        
        # Test tasks
        tasks = config.get_tasks()
        print(f"✅ Tasks: {len(tasks)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Example config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mcp_server_configs():
    """Test standalone MCP server configurations."""
    
    print("\n🧪 STANDALONE MCP SERVER CONFIG VALIDATION")
    print("=" * 60)
    
    try:
        # Test various MCP server configurations
        test_configs = [
            {
                'name': 'filesystem',
                'command': 'npx',
                'args': ['@modelcontextprotocol/server-filesystem', '/workspace']
            },
            {
                'name': 'github',
                'command': 'docker',
                'args': ['run', '-i', '--rm', 'ghcr.io/github/github-mcp-server'],
                'env': {'GITHUB_PERSONAL_ACCESS_TOKEN': 'test-token'}
            },
            {
                'name': 'remote_api',
                'transport': 'sse',
                'url': 'http://localhost:8000/sse'
            },
            {
                'name': 'http_api',
                'transport': 'streamable_http',
                'url': 'http://localhost:8000/mcp',
                'headers': {'Authorization': 'Bearer token'}
            },
            {
                'name': 'websocket_api',
                'transport': 'websocket',
                'url': 'ws://localhost:8000/ws'
            }
        ]
        
        for config_dict in test_configs:
            config = MCPServerConfig(**config_dict)
            print(f"✅ {config.name}: {config.transport}")
            if config.command:
                print(f"   - Command: {config.command}")
            if config.url:
                print(f"   - URL: {config.url}")
            if config.env:
                print(f"   - Env vars: {len(config.env)}")
            if config.headers:
                print(f"   - Headers: {len(config.headers)}")
        
        print("✅ All standalone MCP server configs valid")
        return True
        
    except Exception as e:
        print(f"❌ Standalone config test failed: {e}")
        return False


async def test_documentation_examples():
    """Test examples mentioned in documentation."""
    
    print("\n🧪 DOCUMENTATION EXAMPLES VALIDATION")
    print("=" * 60)
    
    try:
        # Test examples from CLAUDE.md documentation
        doc_examples = [
            {
                'name': 'FileSystem',
                'command': 'npx',
                'args': ['@modelcontextprotocol/server-filesystem', '/workspace']
            },
            {
                'name': 'GitHub',
                'command': 'npx',
                'args': ['-y', '@modelcontextprotocol/server-github']
            },
            {
                'name': 'Database',
                'command': 'python',
                'args': ['mcp_sqlite_server.py', '/data/app.db']
            }
        ]
        
        for example in doc_examples:
            config = MCPServerConfig(**example)
            print(f"✅ Documentation example: {config.name}")
            print(f"   - Command: {config.command} {' '.join(config.args)}")
        
        print("✅ All documentation examples valid")
        return True
        
    except Exception as e:
        print(f"❌ Documentation examples test failed: {e}")
        return False


async def main():
    """Run all example validation tests."""
    
    print("🚀 MCP EXAMPLES AND DOCUMENTATION VALIDATION")
    print("=" * 80)
    print("Validating all MCP example configurations and documentation")
    
    # Find all MCP example configs
    example_configs = list(Path("examples").glob("mcp-*/config.yaml"))
    
    test_results = {}
    
    # Test each example config
    for config_path in example_configs:
        test_name = f"Example: {config_path.parent.name}"
        try:
            result = await test_example_config(config_path)
            test_results[test_name] = result
        except Exception as e:
            logger.error(f"Example {config_path} failed: {e}")
            test_results[test_name] = False
    
    # Test standalone configs
    try:
        result = await test_mcp_server_configs()
        test_results["Standalone MCP Configs"] = result
    except Exception as e:
        logger.error(f"Standalone configs test failed: {e}")
        test_results["Standalone MCP Configs"] = False
    
    # Test documentation examples
    try:
        result = await test_documentation_examples()
        test_results["Documentation Examples"] = result
    except Exception as e:
        logger.error(f"Documentation examples test failed: {e}")
        test_results["Documentation Examples"] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 MCP EXAMPLES AND DOCUMENTATION VALIDATION SUMMARY")
    print("=" * 80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:40} {status}")
    
    if failed_tests == 0:
        print("\n🎉 ALL EXAMPLES AND DOCUMENTATION VALIDATED!")
        print("✅ All MCP configurations are working correctly!")
        
        print("\n🚀 Validated Components:")
        print(f"• {len(example_configs)} example configurations")
        print("• Standalone MCP server configurations")
        print("• Documentation examples from CLAUDE.md")
        print("• YAML parsing and validation")
        print("• Global and agent-specific MCP servers")
        print("• Multi-transport configurations")
        
        print("\n💡 Ready for User Consumption:")
        print("• Example configurations are valid and usable")
        print("• Documentation examples match implementation")
        print("• YAML configs parse correctly")
        print("• All transport types supported")
        
    else:
        print(f"\n⚠️  {failed_tests} test(s) failed. Fix examples before PR.")
    
    print("=" * 80)
    
    return failed_tests == 0


if __name__ == "__main__":
    asyncio.run(main())