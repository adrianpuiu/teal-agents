#!/usr/bin/env python3
"""
Custom MCP server for GitHub CLI operations.
Provides tools to interact with GitHub repositories using the gh CLI.
"""

import json
import sys
import asyncio
import subprocess
from typing import Any, Dict
import shlex


class MCPGitHubCLIServer:
    """MCP server that provides GitHub CLI capabilities."""
    
    def __init__(self):
        self.gh_available = None
    
    async def _check_gh_cli(self) -> bool:
        """Check if GitHub CLI is available and user is authenticated."""
        if self.gh_available is not None:
            return self.gh_available
        
        try:
            # Check if gh is installed
            result = await asyncio.create_subprocess_exec(
                'gh', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            if result.returncode != 0:
                self.gh_available = False
                return False
            
            # Check if user is authenticated
            result = await asyncio.create_subprocess_exec(
                'gh', 'auth', 'status',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            self.gh_available = result.returncode == 0
            return self.gh_available
            
        except Exception:
            self.gh_available = False
            return False
    
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
                    "name": "github-cli-mcp-server",
                    "version": "1.0.0"
                }
            }
        }
    
    async def list_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List available GitHub CLI tools."""
        tools = [
            {
                "name": "list_repositories",
                "description": "List all repositories for the authenticated GitHub user",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "visibility": {
                            "type": "string",
                            "description": "Repository visibility filter",
                            "enum": ["all", "public", "private"],
                            "default": "all"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of repositories to return",
                            "default": 30,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort repositories by",
                            "enum": ["created", "updated", "pushed", "full_name"],
                            "default": "updated"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_repository_info",
                "description": "Get detailed information about a specific repository",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository": {
                            "type": "string",
                            "description": "Repository name in format 'owner/repo' or just 'repo' for user's repos"
                        }
                    },
                    "required": ["repository"]
                }
            },
            {
                "name": "list_repository_issues",
                "description": "List issues for a repository",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository": {
                            "type": "string",
                            "description": "Repository name in format 'owner/repo' or just 'repo' for user's repos"
                        },
                        "state": {
                            "type": "string",
                            "description": "Issue state filter",
                            "enum": ["open", "closed", "all"],
                            "default": "open"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of issues to return",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50
                        }
                    },
                    "required": ["repository"]
                }
            },
            {
                "name": "get_user_info",
                "description": "Get information about the authenticated GitHub user",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "github_cli_status",
                "description": "Check GitHub CLI installation and authentication status",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "create_repository",
                "description": "Create a new GitHub repository",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Repository name"
                        },
                        "description": {
                            "type": "string",
                            "description": "Repository description",
                            "default": ""
                        },
                        "visibility": {
                            "type": "string",
                            "description": "Repository visibility",
                            "enum": ["public", "private"],
                            "default": "public"
                        },
                        "clone": {
                            "type": "boolean",
                            "description": "Clone the repository after creation",
                            "default": False
                        }
                    },
                    "required": ["name"]
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
            
            if tool_name == "list_repositories":
                return await self._handle_list_repositories(request.get("id"), arguments)
            elif tool_name == "get_repository_info":
                return await self._handle_get_repository_info(request.get("id"), arguments)
            elif tool_name == "list_repository_issues":
                return await self._handle_list_repository_issues(request.get("id"), arguments)
            elif tool_name == "get_user_info":
                return await self._handle_get_user_info(request.get("id"), arguments)
            elif tool_name == "github_cli_status":
                return await self._handle_github_cli_status(request.get("id"), arguments)
            elif tool_name == "create_repository":
                return await self._handle_create_repository(request.get("id"), arguments)
            else:
                return self._error_response(request.get("id"), f"Unknown tool: {tool_name}")
                
        except Exception as e:
            return self._error_response(request.get("id"), f"Tool execution error: {str(e)}")
    
    async def _handle_list_repositories(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle repository listing request."""
        try:
            if not await self._check_gh_cli():
                return self._gh_not_available_response(request_id)
            
            visibility = arguments.get("visibility", "all")
            limit = arguments.get("limit", 30)
            sort = arguments.get("sort", "updated")
            
            # Build gh command (note: --sort may not be available in older versions)
            cmd = [
                'gh', 'repo', 'list',
                '--limit', str(limit),
                '--json', 'name,description,visibility,updatedAt,pushedAt,url,stargazerCount,forkCount,primaryLanguage'
            ]
            
            if visibility != "all":
                cmd.extend(['--visibility', visibility])
            
            # Execute command
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                return self._tool_error_response(request_id, f"Failed to list repositories: {error_msg}")
            
            # Parse JSON response
            repos_data = json.loads(stdout.decode('utf-8'))
            
            # Format the response
            if not repos_data:
                result_text = "No repositories found for the authenticated user."
            else:
                result_lines = [
                    f"📚 GitHub Repositories ({len(repos_data)} found)",
                    f"Visibility: {visibility}",
                    "=" * 60
                ]
                
                for i, repo in enumerate(repos_data, 1):
                    name = repo.get('name', 'Unknown')
                    description = repo.get('description', 'No description')
                    visibility_icon = "🔒" if repo.get('visibility') == 'private' else "🌐"
                    stars = repo.get('stargazerCount', 0)
                    forks = repo.get('forkCount', 0)
                    language = repo.get('primaryLanguage', {}).get('name', 'Unknown') if repo.get('primaryLanguage') else 'None'
                    updated = repo.get('updatedAt', '')[:10]  # Just the date part
                    url = repo.get('url', '')
                    
                    result_lines.extend([
                        f"\n{i}. {visibility_icon} {name}",
                        f"   Description: {description}",
                        f"   Language: {language}",
                        f"   ⭐ {stars} stars, 🍴 {forks} forks",
                        f"   Last updated: {updated}",
                        f"   URL: {url}"
                    ])
                
                result_text = "\n".join(result_lines)
            
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
            return self._tool_error_response(request_id, f"Error listing repositories: {str(e)}")
    
    async def _handle_get_repository_info(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle repository info request."""
        try:
            if not await self._check_gh_cli():
                return self._gh_not_available_response(request_id)
            
            repository = arguments.get("repository", "")
            if not repository:
                return self._tool_error_response(request_id, "Repository name is required")
            
            # Execute command
            cmd = [
                'gh', 'repo', 'view', repository,
                '--json', 'name,description,visibility,url,stargazerCount,forkCount,watchers,primaryLanguage,createdAt,updatedAt,pushedAt,defaultBranch,topics,licenseInfo,homepageUrl'
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Repository not found"
                return self._tool_error_response(request_id, f"Failed to get repository info: {error_msg}")
            
            # Parse JSON response
            repo_data = json.loads(stdout.decode('utf-8'))
            
            # Format the response
            name = repo_data.get('name', 'Unknown')
            description = repo_data.get('description', 'No description')
            visibility = repo_data.get('visibility', 'Unknown')
            visibility_icon = "🔒" if visibility == 'private' else "🌐"
            url = repo_data.get('url', '')
            stars = repo_data.get('stargazerCount', 0)
            forks = repo_data.get('forkCount', 0)
            watchers = repo_data.get('watchers', 0)
            language = repo_data.get('primaryLanguage', {}).get('name', 'None') if repo_data.get('primaryLanguage') else 'None'
            created = repo_data.get('createdAt', '')[:10]
            updated = repo_data.get('updatedAt', '')[:10]
            pushed = repo_data.get('pushedAt', '')[:10]
            default_branch = repo_data.get('defaultBranch', 'main')
            topics = repo_data.get('topics', [])
            license_info = repo_data.get('licenseInfo', {})
            license_name = license_info.get('name', 'No license') if license_info else 'No license'
            homepage = repo_data.get('homepageUrl', '')
            
            result_lines = [
                f"📊 Repository Information: {name}",
                "=" * 50,
                f"{visibility_icon} Name: {name}",
                f"📝 Description: {description}",
                f"🔍 Visibility: {visibility}",
                f"💻 Primary Language: {language}",
                f"⭐ Stars: {stars}",
                f"🍴 Forks: {forks}",
                f"👀 Watchers: {watchers}",
                f"🌿 Default Branch: {default_branch}",
                f"📅 Created: {created}",
                f"🔄 Last Updated: {updated}",
                f"📤 Last Push: {pushed}",
                f"⚖️ License: {license_name}",
            ]
            
            if homepage:
                result_lines.append(f"🏠 Homepage: {homepage}")
            
            if topics:
                result_lines.append(f"🏷️ Topics: {', '.join(topics)}")
            
            result_lines.append(f"🔗 URL: {url}")
            
            result_text = "\n".join(result_lines)
            
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
            return self._tool_error_response(request_id, f"Error getting repository info: {str(e)}")
    
    async def _handle_list_repository_issues(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle repository issues listing request."""
        try:
            if not await self._check_gh_cli():
                return self._gh_not_available_response(request_id)
            
            repository = arguments.get("repository", "")
            state = arguments.get("state", "open")
            limit = arguments.get("limit", 10)
            
            if not repository:
                return self._tool_error_response(request_id, "Repository name is required")
            
            # Execute command
            cmd = [
                'gh', 'issue', 'list',
                '--repo', repository,
                '--state', state,
                '--limit', str(limit),
                '--json', 'number,title,state,author,createdAt,updatedAt,url,labels'
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Failed to list issues"
                return self._tool_error_response(request_id, f"Failed to list issues: {error_msg}")
            
            # Parse JSON response
            issues_data = json.loads(stdout.decode('utf-8'))
            
            # Format the response
            if not issues_data:
                result_text = f"No {state} issues found in repository {repository}."
            else:
                result_lines = [
                    f"🐛 Issues in {repository} ({len(issues_data)} {state} issues)",
                    "=" * 50
                ]
                
                for issue in issues_data:
                    number = issue.get('number', 0)
                    title = issue.get('title', 'No title')
                    state_icon = "🟢" if issue.get('state') == 'open' else "🔴"
                    author = issue.get('author', {}).get('login', 'Unknown') if issue.get('author') else 'Unknown'
                    created = issue.get('createdAt', '')[:10]
                    url = issue.get('url', '')
                    labels = [label.get('name', '') for label in issue.get('labels', [])]
                    
                    result_lines.extend([
                        f"\n{state_icon} #{number}: {title}",
                        f"   👤 Author: {author}",
                        f"   📅 Created: {created}",
                    ])
                    
                    if labels:
                        result_lines.append(f"   🏷️ Labels: {', '.join(labels)}")
                    
                    result_lines.append(f"   🔗 URL: {url}")
                
                result_text = "\n".join(result_lines)
            
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
            return self._tool_error_response(request_id, f"Error listing issues: {str(e)}")
    
    async def _handle_get_user_info(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user info request."""
        try:
            if not await self._check_gh_cli():
                return self._gh_not_available_response(request_id)
            
            # Get authenticated user info
            result = await asyncio.create_subprocess_exec(
                'gh', 'api', 'user',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Failed to get user info"
                return self._tool_error_response(request_id, f"Failed to get user info: {error_msg}")
            
            # Parse JSON response
            user_data = json.loads(stdout.decode('utf-8'))
            
            # Format the response
            login = user_data.get('login', 'Unknown')
            name = user_data.get('name', 'No name')
            bio = user_data.get('bio', 'No bio')
            company = user_data.get('company', 'No company')
            location = user_data.get('location', 'No location')
            email = user_data.get('email', 'No public email')
            blog = user_data.get('blog', '')
            public_repos = user_data.get('public_repos', 0)
            followers = user_data.get('followers', 0)
            following = user_data.get('following', 0)
            created = user_data.get('created_at', '')[:10]
            avatar_url = user_data.get('avatar_url', '')
            html_url = user_data.get('html_url', '')
            
            result_lines = [
                f"👤 GitHub User Information: {login}",
                "=" * 40,
                f"📛 Name: {name}",
                f"🏠 Username: {login}",
                f"📝 Bio: {bio}",
                f"🏢 Company: {company}",
                f"📍 Location: {location}",
                f"📧 Email: {email}",
                f"📚 Public Repositories: {public_repos}",
                f"👥 Followers: {followers}",
                f"👤 Following: {following}",
                f"📅 Joined: {created}",
            ]
            
            if blog:
                result_lines.append(f"🌐 Website: {blog}")
            
            result_lines.extend([
                f"🖼️ Avatar: {avatar_url}",
                f"🔗 Profile: {html_url}"
            ])
            
            result_text = "\n".join(result_lines)
            
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
            return self._tool_error_response(request_id, f"Error getting user info: {str(e)}")
    
    async def _handle_github_cli_status(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub CLI status check."""
        try:
            status_lines = ["🔧 GitHub CLI Status Check", "=" * 30]
            
            # Check if gh is installed
            try:
                result = await asyncio.create_subprocess_exec(
                    'gh', '--version',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    version_info = stdout.decode('utf-8').strip().split('\n')[0]
                    status_lines.append(f"✅ GitHub CLI installed: {version_info}")
                else:
                    status_lines.append("❌ GitHub CLI not installed")
                    return self._create_status_response(request_id, status_lines)
            except Exception:
                status_lines.append("❌ GitHub CLI not found")
                return self._create_status_response(request_id, status_lines)
            
            # Check authentication status
            try:
                result = await asyncio.create_subprocess_exec(
                    'gh', 'auth', 'status',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    auth_info = stderr.decode('utf-8').strip()  # gh auth status outputs to stderr
                    status_lines.append("✅ Authentication: Logged in")
                    
                    # Extract account info if available
                    for line in auth_info.split('\n'):
                        if 'Logged in to github.com as' in line:
                            status_lines.append(f"   {line.strip()}")
                        elif 'Token:' in line:
                            status_lines.append(f"   {line.strip()}")
                else:
                    status_lines.append("❌ Authentication: Not logged in")
                    status_lines.append("   Run 'gh auth login' to authenticate")
            except Exception:
                status_lines.append("❌ Authentication: Status unknown")
            
            return self._create_status_response(request_id, status_lines)
            
        except Exception as e:
            return self._tool_error_response(request_id, f"Error checking GitHub CLI status: {str(e)}")
    
    async def _handle_create_repository(self, request_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle repository creation request."""
        try:
            if not await self._check_gh_cli():
                return self._gh_not_available_response(request_id)
            
            name = arguments.get("name", "")
            description = arguments.get("description", "")
            visibility = arguments.get("visibility", "public")
            clone = arguments.get("clone", False)
            
            if not name:
                return self._tool_error_response(request_id, "Repository name is required")
            
            # Build gh command for repository creation
            cmd = ['gh', 'repo', 'create', name]
            
            if description:
                cmd.extend(['--description', description])
            
            if visibility == "private":
                cmd.append('--private')
            else:
                cmd.append('--public')
            
            if clone:
                cmd.append('--clone')
            
            # Execute command
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Failed to create repository"
                return self._tool_error_response(request_id, f"Failed to create repository: {error_msg}")
            
            # Parse the success output
            output = stdout.decode('utf-8').strip()
            
            result_lines = [
                f"🎉 Repository Created Successfully!",
                "=" * 40,
                f"📚 Name: {name}",
                f"🔍 Visibility: {visibility}",
            ]
            
            if description:
                result_lines.append(f"📝 Description: {description}")
            
            # Extract URL from output if available
            if "https://github.com/" in output:
                url_line = [line for line in output.split('\n') if "https://github.com/" in line]
                if url_line:
                    result_lines.append(f"🔗 URL: {url_line[0].strip()}")
            
            if clone:
                result_lines.append("📂 Repository cloned locally")
            
            result_lines.extend([
                "",
                "✅ Repository is ready to use!",
                "You can now push code, create issues, and collaborate."
            ])
            
            result_text = "\n".join(result_lines)
            
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
            return self._tool_error_response(request_id, f"Error creating repository: {str(e)}")
    
    def _create_status_response(self, request_id: str, status_lines: list) -> Dict[str, Any]:
        """Create a status response."""
        result_text = "\n".join(status_lines)
        
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
    
    def _gh_not_available_response(self, request_id: str) -> Dict[str, Any]:
        """Create response when GitHub CLI is not available."""
        error_text = """❌ GitHub CLI Not Available

The GitHub CLI (gh) is either not installed or not authenticated.

To use GitHub CLI features:
1. Install GitHub CLI: https://cli.github.com/
2. Authenticate: gh auth login
3. Verify status: gh auth status

Once set up, you'll be able to list repositories and access other GitHub features."""

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": error_text}],
                "isError": True
            }
        }
    
    def _tool_error_response(self, request_id: str, message: str) -> Dict[str, Any]:
        """Create a tool error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": f"Error: {message}"}],
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


async def main():
    """Main MCP server loop."""
    server = MCPGitHubCLIServer()
    
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
    except Exception as e:
        sys.stderr.write(f"Server error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())