# API Agent with MCP Server

This example demonstrates how to create an agent that can make HTTP API calls and display API responses using a custom MCP server.

## Features

- **Custom MCP Server**: Python-based MCP server for HTTP API calls
- **Multiple Request Types**: GET, POST, and health check requests
- **Response Formatting**: Pretty-printed JSON and detailed response information
- **Error Handling**: Graceful error handling with helpful error messages
- **Authentication Support**: Custom headers for API authentication
- **Both Integration Modes**: Wrapper and direct MCP integration

## Files

- `mcp_api_server.py` - Custom MCP server for API calls
- `config.yaml` - Agent configuration with MCP server setup
- `test_api_server.py` - Test script to verify functionality
- `README.md` - This documentation

## Prerequisites

### 1. Python Dependencies
```bash
# Install required packages
pip install aiohttp
# or using uv
uv add aiohttp
```

### 2. Set Environment Variables
```bash
export TA_API_KEY="your-openai-api-key"
export TA_SERVICE_CONFIG="examples/mcp-api-agent/config.yaml"
```

## Available API Tools

The custom MCP server provides three main tools:

### 1. `get_api_response`
Make GET requests to any API endpoint.

**Parameters:**
- `url` (required): The API endpoint URL
- `headers` (optional): Custom headers as key-value pairs

**Example:**
```json
{
  "url": "https://api.github.com/users/octocat",
  "headers": {
    "Accept": "application/json",
    "User-Agent": "MyAgent/1.0"
  }
}
```

### 2. `post_api_request`
Make POST requests with JSON data.

**Parameters:**
- `url` (required): The API endpoint URL
- `data` (required): JSON data to send in request body
- `headers` (optional): Custom headers as key-value pairs

**Example:**
```json
{
  "url": "https://jsonplaceholder.typicode.com/posts",
  "data": {
    "title": "My Post",
    "body": "This is the post content",
    "userId": 1
  },
  "headers": {
    "Content-Type": "application/json"
  }
}
```

### 3. `api_health_check`
Check if an API is accessible and get basic information.

**Parameters:**
- `url` (required): The API base URL to check

**Example:**
```json
{
  "url": "https://api.github.com"
}
```

## Configuration

The agent supports both wrapper and direct integration modes:

### Wrapper Mode (Generic)
```yaml
mcp_servers:
  - name: api_server
    command: python
    args: ["examples/mcp-api-agent/mcp_api_server.py"]
    integration_mode: wrapper
    timeout: 45
```

**Usage in Agent:**
```python
# Call via generic MCP function
result = await call_mcp_tool('api_server', 'get_api_response', {
  "url": "https://api.example.com/data",
  "headers": {"Authorization": "Bearer token"}
})
```

### Direct Mode (with Base URL)
```yaml
mcp_servers:
  - name: jsonplaceholder_api
    command: python
    args: ["examples/mcp-api-agent/mcp_api_server.py", "https://jsonplaceholder.typicode.com"]
    integration_mode: direct
    plugin_name: JsonAPI
    timeout: 30
```

**Usage in Agent:**
```python
# Call via direct function
result = await JsonAPI.get_api_response(url="/posts/1", headers={})
result = await JsonAPI.post_api_request(url="/posts", data={"title": "Test"})
```

## Running the Agent

### 1. Test the MCP Server
```bash
cd src/sk-agents
uv run python examples/mcp-api-agent/test_api_server.py
```

Expected output:
```
🎉 ALL API MCP TESTS PASSED!
✅ Custom API MCP server is working correctly!
```

### 2. Start the Agent
```bash
cd src/sk-agents
uv run -- fastapi run src/sk_agents/app.py
```

### 3. Access the Agent
- **OpenAPI Docs**: http://localhost:8000/ApiAgent/0.1/docs
- **REST API**: http://localhost:8000/ApiAgent/0.1/invoke

## Example Interactions

### Example 1: Get GitHub User Info
**User Input:**
```json
{
  "input": "Get information about the GitHub user 'octocat'"
}
```

**Agent Response:**
```
I'll get information about the GitHub user 'octocat' for you.

API GET Request Result:
URL: https://api.github.com/users/octocat
Status: 200 OK
Headers: {'content-type': 'application/json', 'server': 'GitHub.com'}

Response Body:
{
  "login": "octocat",
  "id": 1,
  "name": "The Octocat",
  "company": "GitHub",
  "blog": "https://github.blog",
  "public_repos": 8,
  "followers": 3500,
  "following": 9
}

This shows the public profile information for the GitHub user 'octocat', including their name, company, number of repositories, and follower count.
```

### Example 2: Create a Test Post
**User Input:**
```json
{
  "input": "Create a test post on JSONPlaceholder with title 'My Test' and some content"
}
```

**Agent Response:**
```
I'll create a test post on the JSONPlaceholder API for you.

API POST Request Result:
URL: https://jsonplaceholder.typicode.com/posts
Status: 201 Created
Request Body:
{
  "title": "My Test",
  "body": "This is test content created via the API agent",
  "userId": 1
}

Response Body:
{
  "id": 101,
  "title": "My Test",
  "body": "This is test content created via the API agent",
  "userId": 1
}

The post was successfully created! The API returned a 201 Created status and assigned ID 101 to the new post.
```

### Example 3: API Health Check
**User Input:**
```json
{
  "input": "Check if the GitHub API is working"
}
```

**Agent Response:**
```
I'll check the health of the GitHub API for you.

API Health Check Result:
URL: https://api.github.com
Status: 200
Health: ✅ Healthy
Server: GitHub.com
Content-Type: application/json
Response Time: < 10s

The GitHub API is working perfectly! It responded with a healthy 200 status code.
```

## Custom API Authentication

To use APIs that require authentication, you can modify the MCP server or pass authentication headers:

### Method 1: Pass Headers in Request
```python
result = await call_mcp_tool('api_server', 'get_api_response', {
  "url": "https://api.example.com/protected-data",
  "headers": {
    "Authorization": "Bearer your-api-token",
    "X-API-Key": "your-api-key"
  }
})
```

### Method 2: Modify MCP Server with Default Headers
Edit `mcp_api_server.py` and add default headers:

```python
# In the main() function
default_headers = {
    "Authorization": "Bearer your-token",
    "User-Agent": "YourApp/1.0"
}

server = MCPAPIServer(base_url=base_url, default_headers=default_headers)
```

## Advanced Configuration

### Multiple API Endpoints
```yaml
mcp_servers:
  # Generic API server
  - name: api_server
    command: python
    args: ["examples/mcp-api-agent/mcp_api_server.py"]
    integration_mode: wrapper
    
  # JSONPlaceholder specific
  - name: jsonplaceholder
    command: python
    args: ["examples/mcp-api-agent/mcp_api_server.py", "https://jsonplaceholder.typicode.com"]
    integration_mode: direct
    plugin_name: JsonAPI
    
  # GitHub API specific  
  - name: github_api
    command: python
    args: ["examples/mcp-api-agent/mcp_api_server.py", "https://api.github.com"]
    integration_mode: direct
    plugin_name: GitHubAPI
```

### Environment Variables for API Keys
```yaml
mcp_servers:
  - name: authenticated_api
    command: python
    args: ["examples/mcp-api-agent/mcp_api_server.py"]
    env:
      API_TOKEN: "${MY_API_TOKEN}"
      API_BASE_URL: "${API_BASE_URL}"
    integration_mode: wrapper
```

## Troubleshooting

### Common Issues

#### 1. Connection Timeout
```
Error making GET request: timeout
```
**Solution:** Increase timeout in config or check network connectivity

#### 2. Authentication Errors
```
Status: 401 Unauthorized
```
**Solution:** Check API key/token and headers

#### 3. Invalid JSON Response
```
Error parsing JSON response
```
**Solution:** The MCP server handles this gracefully and shows raw text

#### 4. MCP Server Not Starting
```
Failed to connect to MCP server
```
**Solution:** Ensure Python dependencies are installed and script is executable

### Debug Mode
Enable debug logging in the MCP server:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Testing Individual Tools
```bash
# Test the MCP server manually
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python examples/mcp-api-agent/mcp_api_server.py
```

## Extensions

### Adding New API Tools
Edit `mcp_api_server.py` and add new tools to the `list_tools` method:

```python
{
    "name": "delete_api_request",
    "description": "Make a DELETE request to an API endpoint",
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "headers": {"type": "object"}
        },
        "required": ["url"]
    }
}
```

Then implement the handler in `call_tool` method.

### Adding Response Caching
Implement caching for frequently accessed APIs:

```python
import time
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_get_request(url, headers_tuple):
    # Convert headers back from tuple and make request
    pass
```

### Adding Rate Limiting
Implement rate limiting for API calls:

```python
import asyncio
from collections import defaultdict

class RateLimiter:
    def __init__(self, calls_per_minute=60):
        self.calls_per_minute = calls_per_minute
        self.calls = defaultdict(list)
    
    async def wait_if_needed(self, api_url):
        # Implement rate limiting logic
        pass
```

## Related Examples

- `examples/mcp-yaml-config-agent/` - YAML MCP configuration
- `examples/mcp-real-filesystem-agent/` - Filesystem MCP integration
- See `test_api_server.py` for comprehensive testing examples

This API agent provides a powerful foundation for integrating external APIs into your Teal Agents workflows!