#!/usr/bin/env python3
"""
Custom MCP server for API calls.
Provides tools to make HTTP requests and show API responses.
"""

import json
import sys
import asyncio
import aiohttp
from typing import Any, Dict
from urllib.parse import urljoin, urlparse


class MCPAPIServer:
    """MCP server that provides API calling capabilities."""
    
    def __init__(self, base_url: str = None, default_headers: Dict[str, str] = None):
        self.base_url = base_url
        self.default_headers = default_headers or {}
        self.session = None
    
    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def initialize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "api-mcp-server",
                    "version": "1.0.0"
                }
            }
        }
    
    async def list_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List available API tools."""
        tools = [
            {
                "name": "get_api_response",
                "description": "Make a GET request to an API endpoint and show the response",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The API endpoint URL to call"
                        },
                        "headers": {
                            "type": "object",
                            "description": "Optional headers to include in the request",
                            "additionalProperties": {"type": "string"}
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "post_api_request",
                "description": "Make a POST request to an API endpoint with data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The API endpoint URL to call"
                        },
                        "data": {
                            "type": "object",
                            "description": "JSON data to send in the POST request"
                        },
                        "headers": {
                            "type": "object",
                            "description": "Optional headers to include in the request",
                            "additionalProperties": {"type": "string"}
                        }
                    },
                    "required": ["url", "data"]
                }
            },
            {
                "name": "api_health_check",
                "description": "Check if an API endpoint is accessible and return basic info",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The API base URL to check"
                        }
                    },
                    "required": ["url"]
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": tools
            }
        }
    
    async def call_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call requests."""
        try:
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "get_api_response":
                return await self._handle_get_request(request.get("id"), arguments)
            elif tool_name == "post_api_request":
                return await self._handle_post_request(request.get("id"), arguments)
            elif tool_name == "api_health_check":
                return await self._handle_health_check(request.get("id"), arguments)
            else:
                return self._error_response(request.get("id"), f"Unknown tool: {tool_name}")
                
        except Exception as e:
            return self._error_response(request.get("id"), f"Tool execution error: {str(e)}")
    
    async def _handle_get_request(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GET API request."""
        try:
            url = arguments.get("url")
            headers = arguments.get("headers", {})
            
            # Merge with default headers
            final_headers = {**self.default_headers, **headers}
            
            # Resolve URL if base_url is provided
            if self.base_url and not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            session = await self._get_session()
            
            async with session.get(url, headers=final_headers, timeout=30) as response:
                response_text = await response.text()
                
                # Try to parse as JSON, fallback to text
                try:
                    response_data = json.loads(response_text)
                    response_content = json.dumps(response_data, indent=2)
                except json.JSONDecodeError:
                    response_content = response_text
                
                result_text = f"""API GET Request Result:
URL: {url}
Status: {response.status} {response.reason}
Headers: {dict(response.headers)}

Response Body:
{response_content}"""
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ],
                        "isError": False
                    }
                }
                
        except Exception as e:
            error_text = f"Error making GET request to {url}: {str(e)}"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": error_text}],
                    "isError": True
                }
            }
    
    async def _handle_post_request(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST API request."""
        try:
            url = arguments.get("url")
            data = arguments.get("data", {})
            headers = arguments.get("headers", {})
            
            # Merge with default headers and set content-type
            final_headers = {
                "Content-Type": "application/json",
                **self.default_headers, 
                **headers
            }
            
            # Resolve URL if base_url is provided
            if self.base_url and not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            session = await self._get_session()
            
            async with session.post(url, json=data, headers=final_headers, timeout=30) as response:
                response_text = await response.text()
                
                # Try to parse as JSON, fallback to text
                try:
                    response_data = json.loads(response_text)
                    response_content = json.dumps(response_data, indent=2)
                except json.JSONDecodeError:
                    response_content = response_text
                
                request_body = json.dumps(data, indent=2)
                
                result_text = f"""API POST Request Result:
URL: {url}
Status: {response.status} {response.reason}
Request Body:
{request_body}

Response Headers: {dict(response.headers)}

Response Body:
{response_content}"""
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ],
                        "isError": False
                    }
                }
                
        except Exception as e:
            error_text = f"Error making POST request to {url}: {str(e)}"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": error_text}],
                    "isError": True
                }
            }
    
    async def _handle_health_check(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle API health check."""
        try:
            url = arguments.get("url")
            
            session = await self._get_session()
            
            # Try to make a simple HEAD or GET request
            try:
                async with session.head(url, timeout=10) as response:
                    status = response.status
                    headers = dict(response.headers)
            except:
                # Fallback to GET if HEAD fails
                async with session.get(url, timeout=10) as response:
                    status = response.status
                    headers = dict(response.headers)
            
            health_status = "✅ Healthy" if 200 <= status < 400 else "❌ Unhealthy"
            
            result_text = f"""API Health Check Result:
URL: {url}
Status: {status}
Health: {health_status}
Server: {headers.get('server', 'Unknown')}
Content-Type: {headers.get('content-type', 'Unknown')}
Response Time: < 10s"""
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text
                        }
                    ],
                    "isError": False
                }
            }
            
        except Exception as e:
            error_text = f"Error checking API health for {url}: {str(e)}"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": error_text}],
                    "isError": True
                }
            }
    
    def _error_response(self, request_id: str, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": message
            }
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP requests."""
        method = request.get("method")
        
        if method == "initialize":
            return await self.initialize(request)
        elif method == "tools/list":
            return await self.list_tools(request)
        elif method == "tools/call":
            return await self.call_tool(request)
        else:
            return self._error_response(request.get("id"), f"Unknown method: {method}")
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()


async def main():
    """Main MCP server loop."""
    base_url = None
    default_headers = {}
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    # You can add default headers for authentication, etc.
    # default_headers = {"Authorization": "Bearer your-token"}
    
    server = MCPAPIServer(base_url=base_url, default_headers=default_headers)
    
    try:
        # Handle MCP protocol over stdin/stdout
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                response = await server.handle_request(request)
                print(json.dumps(response))
                sys.stdout.flush()
            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                print(json.dumps(error_response))
                sys.stdout.flush()
    
    except KeyboardInterrupt:
        pass
    finally:
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())