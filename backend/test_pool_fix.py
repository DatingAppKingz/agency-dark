#!/usr/bin/env python3
"""
Test script to verify the database pool monitoring fix.
"""
import asyncio
from core.database import engine
from core.monitoring import HealthChecker


async def test_pool_monitoring():
    """Test the database pool monitoring."""
    print("Testing database pool monitoring fix...")
    
    try:
        # Test the check_database method directly
        result = await HealthChecker.check_database()
        
        print("\nDatabase health check result:")
        print(f"Status: {result['status']}")
        print(f"Latency: {result.get('latency_ms', 'N/A')} ms")
        
        if 'pool' in result:
            pool = result['pool']
            print("\nPool status:")
            print(f"  Size: {pool.get('size', 'N/A')}")
            print(f"  Checked out: {pool.get('checked_out', 'N/A')}")
            print(f"  Overflow: {pool.get('overflow', 'N/A')}")
            print(f"  Total: {pool.get('total', 'N/A')}")
            print(f"  Available: {pool.get('available', 'N/A')}")
            if 'status_string' in pool:
                print(f"  Raw status: {pool['status_string']}")
        
        if 'error' in result:
            print(f"\nError: {result['error']}")
            
    except Exception as e:
        print(f"\nError during test: {type(e).__name__}: {e}")
    
    finally:
        # Clean up
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_pool_monitoring())