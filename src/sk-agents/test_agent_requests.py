#!/usr/bin/env python3
"""Test agent with file listing requests"""

import requests
import json
import time

def test_agent_endpoint():
    print("🧪 Testing File Listing Agent")
    print("=" * 35)
    
    # Agent endpoint (adjust port if needed)
    agent_url = "http://localhost:8000"
    
    # Wait for server to be ready
    print("⏳ Waiting for agent server to start...")
    for i in range(10):
        try:
            response = requests.get(f"{agent_url}/MyFileAgent/0.1/docs", timeout=5)
            if response.status_code == 200:
                print("✅ Agent server is ready!")
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
        print(f"   Attempt {i+1}/10...")
    else:
        print("❌ Agent server not responding. Make sure it's running.")
        return False
    
    # Test requests
    test_cases = [
        {
            "name": "List current directory",
            "payload": {
                "message": "List all files in the current directory"
            }
        },
        {
            "name": "List with details",
            "payload": {
                "message": "Show me what files are in this directory and tell me about them"
            }
        },
        {
            "name": "Count files",
            "payload": {
                "message": "How many files are in the current directory?"
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📝 Testing: {test_case['name']}")
        print("-" * 40)
        
        try:
            # Make request to agent
            response = requests.post(
                f"{agent_url}/MyFileAgent/0.1/chat",
                json=test_case["payload"],
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Request successful!")
                print(f"📤 Request: {test_case['payload']['message']}")
                print(f"📥 Response: {result.get('response', 'No response field')}")
            else:
                print(f"❌ Request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
    
    print(f"\n🎉 Agent testing completed!")
    return True

if __name__ == "__main__":
    test_agent_endpoint()