#!/usr/bin/env python3
"""Run the file listing agent with MCP integration"""

import asyncio
import uvicorn
import os
import sys

# Set environment variables
os.environ['TA_API_KEY'] = os.getenv('TA_API_KEY', 'your-openai-api-key-here')
os.environ['TA_SERVICE_CONFIG'] = '/home/agp/teal-agents/src/sk-agents/file-listing-agent-config.yaml'

# Add src to path
sys.path.insert(0, '/home/agp/teal-agents/src/sk-agents/src')

def main():
    print("🚀 Starting File Listing Agent with MCP Integration")
    print("=" * 55)
    print(f"📁 Agent config: {os.environ['TA_SERVICE_CONFIG']}")
    api_key_status = '✅ Set' if os.environ.get('TA_API_KEY') and os.environ.get('TA_API_KEY') != 'your-openai-api-key-here' else '❌ Missing/Default'
    print(f"🔑 API key: {api_key_status}")
    if api_key_status == '❌ Missing/Default':
        print("   ⚠️  Set TA_API_KEY environment variable with your OpenAI API key")
    
    # Verify config file exists
    config_path = os.environ['TA_SERVICE_CONFIG']
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return
    
    print(f"✅ Config file found!")
    print(f"\n🌐 Starting server...")
    print(f"📖 Documentation will be available at: http://localhost:8000/FileListingAgent/1.0/docs")
    print(f"💬 Chat endpoint: http://localhost:8000/FileListingAgent/1.0/chat")
    print(f"\n🔧 To test, run in another terminal:")
    print(f'curl -X POST "http://localhost:8000/FileListingAgent/1.0/chat" \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{\"message\": \"List all files in the current directory\"}}\'')
    print(f"\n" + "=" * 55)
    
    try:
        # Import after setting environment
        from sk_agents.app import app
        
        # Start the server
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            log_level="info"
        )
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        print(f"\n🔧 Troubleshooting:")
        print(f"1. Check config file: {config_path}")
        print(f"2. Verify dependencies: uv sync")
        print(f"3. Check MCP server: npx @modelcontextprotocol/server-filesystem")

if __name__ == "__main__":
    main()