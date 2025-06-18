# MCP Migration Guide

This guide helps you migrate from older MCP implementations to the new simplified Microsoft-style MCP integration.

## Table of Contents

1. [Migration Overview](#migration-overview)
2. [From Legacy Wrapper Mode](#from-legacy-wrapper-mode)
3. [From Legacy Direct Mode](#from-legacy-direct-mode)
4. [Configuration Changes](#configuration-changes)
5. [Code Updates](#code-updates)
6. [Testing Migration](#testing-migration)
7. [Rollback Plan](#rollback-plan)

## Migration Overview

### What's Changed

The Teal Agents platform has simplified MCP integration to align with Microsoft's official Semantic Kernel MCP pattern:

**Before (Legacy):**
- Multiple integration modes (wrapper, direct, enhanced)
- Complex configuration with `integration_mode` and `plugin_name`
- Mixed function calling patterns

**After (Simplified):**
- Single simplified integration mode (default)
- Clean configuration using server names as plugin names
- Consistent Microsoft-style function calling

### Benefits of Migration

1. **Better LLM Reliability** - Tools designed specifically for LLM consumption
2. **Cleaner Interface** - Direct function names vs generic wrappers
3. **Microsoft Alignment** - Follows official Semantic Kernel MCP pattern
4. **Simpler Configuration** - Less configuration complexity
5. **Future-Proof** - Aligned with Microsoft's roadmap

### Compatibility

- **Backward Compatible** - Legacy modes still supported for transition
- **Gradual Migration** - Migrate agents one at a time
- **Mixed Deployments** - Run old and new configurations side by side

## From Legacy Wrapper Mode

### Configuration Migration

**Before (Legacy Wrapper):**
```yaml
spec:
  mcp_servers:
    - name: filesystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      integration_mode: wrapper
      timeout: 30
```

**After (Simplified):**
```yaml
spec:
  mcp_servers:
    - name: FileSystem  # Name becomes plugin name
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      timeout: 30  # integration_mode removed - simplified by default
```

### System Prompt Updates

**Before (Legacy Wrapper):**
```yaml
system_prompt: |
  You have access to filesystem tools via call_mcp_tool():
  - call_mcp_tool('filesystem', 'list_directory', '{"path": "/workspace"}')
  - call_mcp_tool('filesystem', 'read_file', '{"path": "README.md"}')
  - call_mcp_tool('filesystem', 'write_file', '{"path": "output.txt", "content": "Hello"}')
  
  Use list_mcp_tools() to discover available tools.
```

**After (Simplified):**
```yaml
system_prompt: |
  You have access to filesystem tools:
  - FileSystem.list_directory(path) - List directory contents
  - FileSystem.read_file(path) - Read file contents
  - FileSystem.write_file(path, content) - Write to file
  
  Call these functions directly with the appropriate parameters.
```

### Agent Behavior Changes

**Before (Legacy Wrapper):**
```python
# Agent would call generic MCP functions
result = await call_mcp_tool('filesystem', 'list_directory', '{"path": "/workspace"}')
content = await call_mcp_tool('filesystem', 'read_file', '{"path": "README.md"}')
```

**After (Simplified):**
```python
# Agent calls direct functions
result = await FileSystem.list_directory(path="/workspace")
content = await FileSystem.read_file(path="README.md")
```

## From Legacy Direct Mode

### Configuration Migration

**Before (Legacy Direct):**
```yaml
spec:
  mcp_servers:
    - name: filesystem_server
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      integration_mode: direct
      plugin_name: FileSystem
      timeout: 30
```

**After (Simplified):**
```yaml
spec:
  mcp_servers:
    - name: FileSystem  # Use plugin_name as the server name
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      timeout: 30  # Remove integration_mode and plugin_name
```

### Minimal Changes Required

Legacy direct mode is very similar to simplified mode. The main changes:

1. **Server Naming** - Use the desired plugin name as the server name
2. **Remove Fields** - Remove `integration_mode` and `plugin_name` fields
3. **Function Calls** - Function calling pattern remains the same

## Configuration Changes

### Environment Variables

No changes required for environment variables:

```bash
# These remain the same
export TA_SERVICE_CONFIG="path/to/config.yaml"
export TA_API_KEY="your-openai-api-key"
export GITHUB_TOKEN="your-github-token"
```

### Multiple MCP Servers

**Before (Legacy Mixed):**
```yaml
spec:
  mcp_servers:
    - name: fs_wrapper
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
      integration_mode: wrapper
      
    - name: fs_direct
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      integration_mode: direct
      plugin_name: FileSystem
      
    - name: github_server
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      integration_mode: direct
      plugin_name: GitHub
```

**After (Simplified):**
```yaml
spec:
  mcp_servers:
    - name: TempFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
      
    - name: WorkspaceFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
      
    - name: GitHub
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

### Global vs Agent-Specific Servers

**Before (Legacy):**
```yaml
spec:
  # Global servers required explicit modes
  mcp_servers:
    - name: shared_fs
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/shared"]
      integration_mode: direct
      plugin_name: SharedFS

  agents:
    - name: agent1
      mcp_servers:
        - name: private_fs
          command: npx
          args: ["@modelcontextprotocol/server-filesystem", "/private"]
          integration_mode: direct
          plugin_name: PrivateFS
```

**After (Simplified):**
```yaml
spec:
  # Global servers use simplified configuration
  mcp_servers:
    - name: SharedFileSystem
      command: npx
      args: ["@modelcontextprotocol/server-filesystem", "/shared"]

  agents:
    - name: agent1
      mcp_servers:
        - name: PrivateFileSystem
          command: npx
          args: ["@modelcontextprotocol/server-filesystem", "/private"]
```

## Code Updates

### Custom Plugin Migration

If you have custom code that interacts with MCP:

**Before (Legacy):**
```python
from sk_agents.mcp_integration import EnhancedMCPPluginFactory

# Legacy factory usage
plugin = EnhancedMCPPluginFactory.create_from_config(mcp_configs)
await plugin.initialize()
result = await plugin.call_mcp_tool('filesystem', 'list_directory', '{"path": "/"}')
```

**After (Simplified):**
```python
from sk_agents.mcp_integration import SimplifiedMCPIntegration
from semantic_kernel.kernel import Kernel

# Simplified integration usage
kernel = Kernel()
await SimplifiedMCPIntegration.add_mcp_tools_to_kernel(kernel, mcp_configs)
# Tools are now available as kernel functions
```

### Custom Types Migration

**Before (Legacy):**
```python
# custom_types.py
from pydantic import BaseModel

class MCPToolRequest(BaseModel):
    server_name: str
    tool_name: str
    arguments: str

class MCPToolResponse(BaseModel):
    success: bool
    content: str
    error: str = None
```

**After (Simplified):**
```python
# custom_types.py - Simplified integration handles this internally
# No custom MCP types needed in most cases
from pydantic import BaseModel

class AgentRequest(BaseModel):
    message: str

class AgentResponse(BaseModel):
    response: str
    tools_used: list[str] = []
```

## Testing Migration

### Migration Testing Strategy

1. **Backup Current Configuration**
   ```bash
   cp config.yaml config.yaml.backup
   ```

2. **Create Test Configuration**
   ```bash
   cp config.yaml config-simplified.yaml
   # Edit config-simplified.yaml with new format
   ```

3. **Test in Development**
   ```bash
   export TA_SERVICE_CONFIG="config-simplified.yaml"
   uv run -- fastapi run src/sk_agents/app.py
   ```

4. **Run Validation Tests**
   ```bash
   uv run python test_final_mcp_validation.py
   ```

### Test Scenarios

#### Functional Testing
```bash
# Test basic MCP functionality
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files in the current directory"}'

# Test tool discovery
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What tools do you have available?"}'

# Test complex operations
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Read the README file and summarize it"}'
```

#### Performance Testing
```bash
# Compare response times
time curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files and read package.json"}'
```

#### Error Handling Testing
```bash
# Test invalid file access
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Read /nonexistent/file.txt"}'

# Test server connection issues
# Stop MCP server and test error handling
```

### Validation Checklist

- [ ] All MCP servers connect successfully
- [ ] Tool discovery returns expected tools
- [ ] Function calls work with new naming
- [ ] Error handling works properly
- [ ] Performance is similar or better
- [ ] System prompts are accurate
- [ ] Agent behavior is consistent

## Rollback Plan

### Quick Rollback

If issues arise, you can quickly rollback:

```bash
# 1. Stop the agent
pkill -f "fastapi run"

# 2. Restore backup configuration
cp config.yaml.backup config.yaml

# 3. Restart with original configuration
export TA_SERVICE_CONFIG="config.yaml"
uv run -- fastapi run src/sk_agents/app.py
```

### Gradual Rollback

For production environments:

1. **Update Load Balancer** - Route traffic back to legacy instances
2. **Scale Down New Instances** - Reduce new deployment replicas
3. **Scale Up Legacy Instances** - Increase legacy deployment replicas
4. **Monitor** - Ensure traffic is handled properly
5. **Investigate** - Debug issues with new configuration

### Rollback Testing

```bash
# Test rollback configuration
export TA_SERVICE_CONFIG="config.yaml.backup"
uv run python test_final_mcp_validation.py

# Verify legacy functionality
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test legacy MCP functionality"}'
```

## Migration Steps Summary

### Phase 1: Preparation
1. **Backup Current Configuration**
2. **Review Legacy Configuration**
3. **Plan New Configuration Structure**
4. **Set Up Test Environment**

### Phase 2: Configuration Migration
1. **Update MCP Server Definitions**
2. **Simplify Server Names**
3. **Remove Legacy Fields**
4. **Update System Prompts**

### Phase 3: Testing
1. **Functional Testing**
2. **Performance Testing**
3. **Error Handling Testing**
4. **User Acceptance Testing**

### Phase 4: Deployment
1. **Deploy to Staging**
2. **Run Integration Tests**
3. **Deploy to Production**
4. **Monitor and Validate**

### Phase 5: Cleanup
1. **Remove Legacy Configurations**
2. **Update Documentation**
3. **Train Team on New Patterns**
4. **Monitor Long-term Stability**

## Best Practices for Migration

1. **Migrate Gradually** - Don't migrate all agents at once
2. **Test Thoroughly** - Use comprehensive test scenarios
3. **Monitor Closely** - Watch for performance or behavior changes
4. **Document Changes** - Keep clear records of what was changed
5. **Train Team** - Ensure team understands new patterns
6. **Plan Rollback** - Always have a rollback plan ready

This migration guide provides a comprehensive path from legacy MCP implementations to the new simplified approach while maintaining system stability and reliability.