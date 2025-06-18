# Microsoft-Style Simplified MCP Integration

This example demonstrates the **simplified MCP integration** that aligns with Microsoft's official Semantic Kernel MCP approach.

## Key Features

### ✅ **Simplified Integration (Default)**
- Direct tool registration as Semantic Kernel functions
- Tools callable as `GitHub.search_repositories()`, `FileSystem.read_file()`
- Better LLM function calling reliability
- Follows Microsoft's official pattern

### 🔧 **Backward Compatibility**
- Legacy wrapper mode still available with `integration_mode: wrapper`
- Existing configurations continue to work
- Automatic fallback for complex scenarios

## Configuration

### Simplified Mode (Default)
```yaml
mcp_servers:
  - name: GitHub
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
  
  - name: FileSystem
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
```

### Legacy Mode (Backward Compatibility)
```yaml
mcp_servers:
  - name: legacy_server
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
    integration_mode: wrapper  # Explicitly request legacy mode
```

## Tool Access Patterns

### Simplified Mode Tools
```python
# Direct function calls - better for LLMs
await GitHub.search_repositories(query="semantic-kernel")
await FileSystem.read_file(path="README.md")
await GitHub.create_repository(name="test-repo", description="Test repository")
```

### Legacy Mode Tools
```python
# Generic wrapper functions - backward compatibility
await call_mcp_tool("legacy_server", "list_directory", '{"path": "/tmp"}')
await list_mcp_tools()
```

## Benefits

1. **Better LLM Reliability**: Tools designed specifically for LLM consumption
2. **Cleaner Interface**: Direct function names vs generic wrappers
3. **Microsoft Alignment**: Follows official Semantic Kernel MCP pattern
4. **Backward Compatible**: Existing configs continue to work
5. **Automatic Fallback**: Falls back to legacy mode if simplified fails

## Migration Guide

### From Legacy Wrapper Mode to Simplified

**Before (Legacy Wrapper)**:
```yaml
mcp_servers:
  - name: filesystem
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    integration_mode: wrapper
```

**After (Simplified)**:
```yaml
mcp_servers:
  - name: FileSystem  # Name becomes plugin name
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/workspace"]
    # No integration_mode needed - simplified by default
```

**System Prompt Update**:
```diff
- You have access to filesystem tools via call_mcp_tool()
+ You have access to filesystem tools:
+ - FileSystem.list_directory(path) - List directory contents
+ - FileSystem.read_file(path) - Read file contents
+ - FileSystem.write_file(path, content) - Write to file
```

The simplified approach provides cleaner function names that LLMs can call more reliably.

## Testing

```bash
# Test the simplified MCP agent
export TA_SERVICE_CONFIG="examples/mcp-simplified-agent/config.yaml"
export TA_API_KEY="your-openai-api-key"

uv run -- fastapi run src/sk_agents/app.py

# Test requests
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files in the current directory"}'

curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for semantic-kernel repositories on GitHub"}'
```

## Implementation Details

The simplified integration:
1. Creates individual MCP clients per server
2. Registers tools directly as Semantic Kernel functions
3. Uses server name as plugin name
4. Maintains connection lifecycle automatically
5. Falls back to legacy mode if needed

This approach provides better developer experience and improved LLM function calling reliability while maintaining full backward compatibility.