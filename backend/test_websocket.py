"""Test WebSocket connections."""

import asyncio
import websockets
import json
import sys

async def test_chat_websocket(token: str):
    """Test chat WebSocket connection."""
    uri = f"ws://localhost:8001/api/v1/ws/chat?token={token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to chat WebSocket")
            
            # Join a chat room
            await websocket.send(json.dumps({
                "type": "join_chat",
                "chat_id": 1
            }))
            
            # Send a test message
            await websocket.send(json.dumps({
                "type": "chat_message",
                "chat_id": 1,
                "content": "Hello from WebSocket!",
                "message_type": "text"
            }))
            
            # Listen for messages
            for i in range(5):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    print(f"Received: {data}")
                except asyncio.TimeoutError:
                    print("No message received (timeout)")
                    
    except Exception as e:
        print(f"WebSocket error: {e}")


async def test_notification_websocket(token: str):
    """Test notification WebSocket connection."""
    uri = f"ws://localhost:8001/api/v1/ws/notifications?token={token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("\nConnected to notification WebSocket")
            
            # Send ping
            await websocket.send(json.dumps({
                "type": "ping"
            }))
            
            # Listen for messages
            for i in range(3):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    print(f"Received: {data}")
                except asyncio.TimeoutError:
                    print("No message received (timeout)")
                    
    except Exception as e:
        print(f"WebSocket error: {e}")


async def test_dashboard_websocket(token: str):
    """Test dashboard WebSocket connection."""
    uri = f"ws://localhost:8001/api/v1/ws/dashboard?token={token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("\nConnected to dashboard WebSocket")
            
            # Request dashboard stats
            await websocket.send(json.dumps({
                "type": "get_dashboard_stats"
            }))
            
            # Set update interval
            await websocket.send(json.dumps({
                "type": "set_update_interval",
                "interval": 10
            }))
            
            # Listen for updates
            for i in range(5):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(message)
                    print(f"Dashboard update: {data['type']}")
                except asyncio.TimeoutError:
                    print("No update received (timeout)")
                    
    except Exception as e:
        print(f"WebSocket error: {e}")


async def main():
    """Run WebSocket tests."""
    if len(sys.argv) < 2:
        print("Usage: python test_websocket.py <jwt_token>")
        print("\nTo get a token, login first:")
        print("curl -X POST http://localhost:8001/api/v1/auth/login \\")
        print("  -H 'Content-Type: application/json' \\")
        print("  -d '{\"username\": \"superadmin\", \"password\": \"admin123\"}'")
        return
        
    token = sys.argv[1]
    
    print("Testing WebSocket connections...")
    
    # Test each WebSocket endpoint
    await test_chat_websocket(token)
    await test_notification_websocket(token)
    await test_dashboard_websocket(token)


if __name__ == "__main__":
    asyncio.run(main())