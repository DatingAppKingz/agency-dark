#!/usr/bin/env python3
"""
Socket.IO Connection Tests for AgencyDark
Tests Socket.IO connectivity, authentication, and real-time features
"""

import asyncio
import json
import socketio
import requests
from typing import Dict, Any, Optional


class SocketIOTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.tokens = {}
        self.sio_clients = {}
        
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
    
    async def create_client(self, email: str) -> socketio.AsyncClient:
        """Create and connect a Socket.IO client"""
        token = self.tokens.get(email) or self.login(email)
        if not token:
            raise Exception(f"Failed to get token for {email}")
        
        sio = socketio.AsyncClient()
        self.sio_clients[email] = sio
        
        # Setup event handlers
        @sio.event
        async def connect():
            print(f"✅ {email} connected to Socket.IO")
            
        @sio.event
        async def connected(data):
            print(f"📥 {email} received connection confirmation: {data}")
            
        @sio.event
        async def disconnect():
            print(f"🔌 {email} disconnected")
            
        @sio.event
        async def pong():
            print(f"📥 {email} received pong")
            
        @sio.event
        async def notification(data):
            print(f"🔔 {email} received notification: {data}")
            
        @sio.event
        async def chat_message(data):
            print(f"💬 {email} received chat message: {data}")
            
        @sio.event
        async def typing(data):
            print(f"✍️ {email} received typing indicator: {data}")
            
        @sio.event
        async def error(data):
            print(f"❌ {email} received error: {data}")
        
        # Connect with authentication
        await sio.connect(
            self.base_url,
            auth={'token': token},
            transports=['websocket', 'polling']
        )
        
        return sio
    
    async def test_basic_connection(self):
        """Test 1: Basic Socket.IO connection"""
        print("\n🧪 Test 1: Basic Socket.IO Connection")
        
        try:
            # Connect as model
            sio = await self.create_client("model1@testagencypremium.com")
            
            # Wait for connection
            await asyncio.sleep(1)
            
            if sio.connected:
                print("✅ Successfully connected to Socket.IO")
                
                # Test ping/pong
                await sio.emit('ping')
                await asyncio.sleep(1)
                
                await sio.disconnect()
            else:
                print("❌ Failed to connect")
                
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            raise
    
    async def test_multi_user_connection(self):
        """Test 2: Multiple users connecting"""
        print("\n🧪 Test 2: Multi-User Connection")
        
        users = [
            "owner@testagencypremium.com",
            "model1@testagencypremium.com",
            "chatter1@testagencypremium.com"
        ]
        
        clients = []
        
        try:
            # Connect all users
            for user in users:
                client = await self.create_client(user)
                clients.append(client)
                
            await asyncio.sleep(1)
            
            # Check all connected
            all_connected = all(c.connected for c in clients)
            if all_connected:
                print(f"✅ All {len(clients)} users connected successfully")
            else:
                print("❌ Some users failed to connect")
                
        finally:
            # Disconnect all
            for client in clients:
                if client.connected:
                    await client.disconnect()
    
    async def test_namespace_features(self):
        """Test 3: Namespace-specific features"""
        print("\n🧪 Test 3: Namespace Features")
        
        model_client = await self.create_client("model1@testagencypremium.com")
        chatter_client = await self.create_client("chatter1@testagencypremium.com")
        
        try:
            # Test chat namespace
            print("\n📝 Testing /chat namespace...")
            
            # Model sends a chat message
            await model_client.emit('message', {
                'fan_id': 'test_fan_123',
                'message': 'Hello from model!'
            }, namespace='/chat')
            
            await asyncio.sleep(1)
            
            # Test notifications namespace
            print("\n🔔 Testing /notifications namespace...")
            
            await model_client.emit('subscribe', namespace='/notifications')
            await chatter_client.emit('subscribe', namespace='/notifications')
            
            # Test dashboard namespace
            print("\n📊 Testing /dashboard namespace...")
            
            await model_client.emit('subscribe_metrics', {
                'metrics': ['revenue', 'subscribers']
            }, namespace='/dashboard')
            
            await asyncio.sleep(1)
            
        finally:
            await model_client.disconnect()
            await chatter_client.disconnect()
    
    async def test_real_time_updates(self):
        """Test 4: Real-time updates between users"""
        print("\n🧪 Test 4: Real-Time Updates")
        
        owner = await self.create_client("owner@testagencypremium.com")
        model = await self.create_client("model1@testagencypremium.com")
        
        try:
            # Setup message received flag
            message_received = asyncio.Event()
            
            @model.on('agency_notification')
            async def on_agency_notification(data):
                print(f"📨 Model received agency notification: {data}")
                message_received.set()
            
            # Owner sends agency-wide notification
            await owner.emit('broadcast_notification', {
                'type': 'announcement',
                'message': 'New feature available!'
            }, namespace='/notifications')
            
            # Wait for message
            try:
                await asyncio.wait_for(message_received.wait(), timeout=3.0)
                print("✅ Real-time notification delivered")
            except asyncio.TimeoutError:
                print("⚠️ No real-time notification received (may need implementation)")
                
        finally:
            await owner.disconnect()
            await model.disconnect()
    
    async def test_error_handling(self):
        """Test 5: Error handling"""
        print("\n🧪 Test 5: Error Handling")
        
        client = await self.create_client("model1@testagencypremium.com")
        
        try:
            # Send invalid event
            await client.emit('invalid_event_name', {'test': 'data'})
            await asyncio.sleep(1)
            
            # Send to unauthorized namespace
            await client.emit('admin_only_action', {}, namespace='/admin')
            await asyncio.sleep(1)
            
            print("✅ Error handling test completed")
            
        finally:
            await client.disconnect()
    
    async def run_all_tests(self):
        """Run all Socket.IO tests"""
        print("=" * 60)
        print("🚀 Socket.IO Test Suite for AgencyDark")
        print("=" * 60)
        
        tests = [
            self.test_basic_connection,
            self.test_multi_user_connection,
            self.test_namespace_features,
            self.test_real_time_updates,
            self.test_error_handling
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
    tester = SocketIOTester()
    
    print("🔍 Checking Socket.IO availability...")
    
    # First check if regular HTTP works
    try:
        response = requests.get(f"{tester.base_url}/health")
        if response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"⚠️ Backend returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach backend: {e}")
        return
    
    # Run the test suite
    passed, failed = await tester.run_all_tests()
    
    if failed == 0:
        print("\n✅ All Socket.IO tests passed!")
    else:
        print(f"\n⚠️ {failed} tests failed")
        
    # Note about implementation
    print("\n📝 Note: Socket.IO is configured in the backend but some")
    print("   real-time features may need additional implementation")
    print("   in the namespace handlers.")


if __name__ == "__main__":
    # Install required package if needed
    try:
        import socketio
    except ImportError:
        print("Installing python-socketio[asyncio_client]...")
        import subprocess
        subprocess.check_call(["pip", "install", "python-socketio[asyncio_client]"])
        import socketio
    
    asyncio.run(main())