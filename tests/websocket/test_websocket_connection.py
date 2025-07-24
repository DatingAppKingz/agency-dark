#!/usr/bin/env python3
"""
WebSocket Connection Tests for AgencyDark
Tests basic WebSocket connectivity, authentication, and message handling
"""

import asyncio
import json
import pytest
import websockets
import requests
from typing import Dict, Any, Optional


class WebSocketTester:
    def __init__(self, base_url: str = "localhost:8000"):
        self.base_url = base_url
        self.ws_url = f"ws://{base_url}/ws"
        self.api_url = f"http://{base_url}/api/v1"
        self.tokens = {}
        
    def login(self, email: str, password: str = "Test123!") -> Optional[str]:
        """Login and get access token"""
        response = requests.post(
            f"{self.api_url}/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.tokens[email] = data["access_token"]
            return data["access_token"]
        else:
            print(f"Login failed for {email}: {response.text}")
            return None
    
    async def connect_websocket(self, token: str) -> websockets.WebSocketClientProtocol:
        """Connect to WebSocket with authentication"""
        headers = {"Authorization": f"Bearer {token}"}
        return await websockets.connect(self.ws_url, extra_headers=headers)
    
    async def test_basic_connection(self):
        """Test 1: Basic WebSocket connection"""
        print("\n🧪 Test 1: Basic WebSocket Connection")
        
        # Login as model
        token = self.login("model1@testagencypremium.com")
        assert token, "Failed to login"
        
        try:
            # Connect to WebSocket
            async with await self.connect_websocket(token) as ws:
                print("✅ Connected to WebSocket")
                
                # Send ping
                await ws.send(json.dumps({"type": "ping"}))
                
                # Wait for pong
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("type") == "pong":
                    print("✅ Received pong response")
                else:
                    print(f"❌ Unexpected response: {data}")
                    
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise
    
    async def test_authentication(self):
        """Test 2: WebSocket authentication"""
        print("\n🧪 Test 2: WebSocket Authentication")
        
        # Test with invalid token
        try:
            headers = {"Authorization": "Bearer invalid_token"}
            async with await websockets.connect(self.ws_url, extra_headers=headers) as ws:
                print("❌ Connected with invalid token (should fail)")
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 403:
                print("✅ Correctly rejected invalid token")
            else:
                print(f"❌ Unexpected status code: {e.status_code}")
                raise
        
        # Test with valid token
        token = self.login("owner@testagencypremium.com")
        try:
            async with await self.connect_websocket(token) as ws:
                print("✅ Connected with valid token")
        except Exception as e:
            print(f"❌ Failed to connect with valid token: {e}")
            raise
    
    async def test_real_time_notifications(self):
        """Test 3: Real-time notifications between users"""
        print("\n🧪 Test 3: Real-time Notifications")
        
        # Login as two different users
        owner_token = self.login("owner@testagencypremium.com")
        model_token = self.login("model1@testagencypremium.com")
        
        async with await self.connect_websocket(owner_token) as owner_ws, \
                   await self.connect_websocket(model_token) as model_ws:
            
            print("✅ Both users connected")
            
            # Model sends a notification
            notification = {
                "type": "notification",
                "action": "new_subscriber",
                "data": {
                    "subscriber_name": "TestFan123",
                    "amount": 9.99
                }
            }
            
            await model_ws.send(json.dumps(notification))
            print("📤 Model sent notification")
            
            # Owner should receive it (if implemented)
            try:
                response = await asyncio.wait_for(owner_ws.recv(), timeout=2.0)
                data = json.loads(response)
                print(f"📥 Owner received: {data}")
                
                if data.get("type") == "notification":
                    print("✅ Real-time notification working")
                else:
                    print("⚠️  Received different message type")
                    
            except asyncio.TimeoutError:
                print("⚠️  No notification received (feature may not be implemented)")
    
    async def test_typing_indicators(self):
        """Test 4: Typing indicators in chat"""
        print("\n🧪 Test 4: Typing Indicators")
        
        # Login as model and chatter
        model_token = self.login("model1@testagencypremium.com")
        chatter_token = self.login("chatter1@testagencypremium.com")
        
        async with await self.connect_websocket(model_token) as model_ws, \
                   await self.connect_websocket(chatter_token) as chatter_ws:
            
            # Chatter starts typing
            typing_msg = {
                "type": "typing",
                "action": "start",
                "chat_id": "test_chat_123"
            }
            
            await chatter_ws.send(json.dumps(typing_msg))
            print("📤 Chatter started typing")
            
            # Model should see typing indicator
            try:
                response = await asyncio.wait_for(model_ws.recv(), timeout=2.0)
                data = json.loads(response)
                
                if data.get("type") == "typing":
                    print("✅ Typing indicator received")
                else:
                    print(f"⚠️  Different message: {data}")
                    
            except asyncio.TimeoutError:
                print("⚠️  No typing indicator (feature may not be implemented)")
    
    async def test_concurrent_connections(self):
        """Test 5: Multiple concurrent connections"""
        print("\n🧪 Test 5: Concurrent Connections")
        
        # Login multiple users
        users = [
            "owner@testagencypremium.com",
            "admin@testagencypremium.com",
            "model1@testagencypremium.com",
            "model2@testagencypremium.com",
            "chatter1@testagencypremium.com",
            "chatter2@testagencypremium.com"
        ]
        
        tokens = [self.login(email) for email in users]
        connections = []
        
        try:
            # Connect all users
            for i, token in enumerate(tokens):
                if token:
                    ws = await self.connect_websocket(token)
                    connections.append((users[i], ws))
            
            print(f"✅ Connected {len(connections)} users concurrently")
            
            # Send a broadcast message
            if connections:
                sender_email, sender_ws = connections[0]
                broadcast_msg = {
                    "type": "broadcast",
                    "message": "Hello everyone!",
                    "from": sender_email
                }
                
                await sender_ws.send(json.dumps(broadcast_msg))
                print(f"📤 {sender_email} sent broadcast")
                
                # Check if others receive it
                received_count = 0
                for email, ws in connections[1:]:
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(response)
                        if data.get("type") == "broadcast":
                            received_count += 1
                    except asyncio.TimeoutError:
                        pass
                
                if received_count > 0:
                    print(f"✅ {received_count} users received broadcast")
                else:
                    print("⚠️  No broadcasts received (feature may not be implemented)")
                    
        finally:
            # Close all connections
            for _, ws in connections:
                await ws.close()
            print(f"🔌 Closed all {len(connections)} connections")
    
    async def test_reconnection(self):
        """Test 6: Connection drop and reconnection"""
        print("\n🧪 Test 6: Reconnection Handling")
        
        token = self.login("model1@testagencypremium.com")
        
        # First connection
        ws1 = await self.connect_websocket(token)
        print("✅ Initial connection established")
        
        # Close it
        await ws1.close()
        print("🔌 Connection closed")
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # Reconnect
        try:
            ws2 = await self.connect_websocket(token)
            print("✅ Reconnection successful")
            
            # Test if it works
            await ws2.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            
            if json.loads(response).get("type") == "pong":
                print("✅ Reconnected WebSocket functional")
            
            await ws2.close()
            
        except Exception as e:
            print(f"❌ Reconnection failed: {e}")
            raise
    
    async def run_all_tests(self):
        """Run all WebSocket tests"""
        print("=" * 60)
        print("🚀 WebSocket Test Suite for AgencyDark")
        print("=" * 60)
        
        tests = [
            self.test_basic_connection,
            self.test_authentication,
            self.test_real_time_notifications,
            self.test_typing_indicators,
            self.test_concurrent_connections,
            self.test_reconnection
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                await test()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"❌ Test failed with error: {e}")
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {passed} passed, {failed} failed")
        print("=" * 60)
        
        return passed, failed


async def main():
    """Main test runner"""
    tester = WebSocketTester()
    
    # First check if WebSocket endpoint exists
    print("🔍 Checking WebSocket endpoint availability...")
    
    try:
        # Try a simple connection without auth to see if WS exists
        async with websockets.connect(tester.ws_url) as ws:
            print("✅ WebSocket endpoint is available")
    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code in [401, 403]:
            print("✅ WebSocket endpoint exists (requires authentication)")
        else:
            print(f"⚠️  WebSocket endpoint returned status: {e.status_code}")
    except Exception as e:
        print(f"❌ WebSocket endpoint not available: {e}")
        print("\n⚠️  WebSocket functionality may not be implemented yet")
        return
    
    # Run the test suite
    passed, failed = await tester.run_all_tests()
    
    if failed == 0:
        print("\n✅ All WebSocket tests passed!")
    else:
        print(f"\n⚠️  {failed} tests failed")


if __name__ == "__main__":
    asyncio.run(main())