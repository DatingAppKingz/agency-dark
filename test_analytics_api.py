#!/usr/bin/env python3
"""Test analytics API endpoints to debug dashboard issues."""

import asyncio
import httpx
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"

async def test_analytics_endpoints():
    async with httpx.AsyncClient() as client:
        # Step 1: Login to get token
        print("1. Logging in...")
        login_response = await client.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.text}")
            return
        
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print(f"✅ Login successful! Token: {access_token[:20]}...")
        
        # Headers with auth token
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 2: Test dashboard stats endpoint
        print("\n2. Testing dashboard stats endpoint...")
        stats_response = await client.get(
            f"{API_BASE_URL}/analytics/agency/dashboard-stats",
            headers=headers
        )
        
        print(f"Status: {stats_response.status_code}")
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            print("✅ Dashboard stats response:")
            print(json.dumps(stats_data, indent=2))
        else:
            print(f"❌ Error: {stats_response.text}")
        
        # Step 3: Test model performance endpoint
        print("\n3. Testing model performance endpoint...")
        perf_response = await client.get(
            f"{API_BASE_URL}/analytics/agency/model-performance",
            headers=headers,
            params={"period": "month"}
        )
        
        print(f"Status: {perf_response.status_code}")
        if perf_response.status_code == 200:
            perf_data = perf_response.json()
            print("✅ Model performance response:")
            print(json.dumps(perf_data[:2], indent=2))  # Show first 2 models
        else:
            print(f"❌ Error: {perf_response.text}")
        
        # Step 4: Test revenue chart endpoint
        print("\n4. Testing revenue chart endpoint...")
        revenue_response = await client.get(
            f"{API_BASE_URL}/analytics/agency/revenue-chart",
            headers=headers,
            params={"period": "month"}
        )
        
        print(f"Status: {revenue_response.status_code}")
        if revenue_response.status_code == 200:
            revenue_data = revenue_response.json()
            print("✅ Revenue chart response:")
            print(f"Period: {revenue_data.get('period')}")
            print(f"Data points: {len(revenue_data.get('data', []))}")
            print(f"Total revenue: ${revenue_data.get('summary', {}).get('total', 0):,.2f}")
        else:
            print(f"❌ Error: {revenue_response.text}")
        
        # Step 5: Test from browser perspective
        print("\n5. Testing what browser would see...")
        print(f"Frontend would call: {API_BASE_URL}/analytics/agency/dashboard-stats")
        print(f"With Authorization header: Bearer {access_token[:20]}...")

if __name__ == "__main__":
    asyncio.run(test_analytics_endpoints())