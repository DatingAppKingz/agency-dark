#!/usr/bin/env python3
"""
Docker health check script
"""
import sys
import asyncio
import aiohttp
import asyncpg
import redis.asyncio as redis
from typing import Dict, List, Tuple


class HealthChecker:
    """Health check implementation"""
    
    def __init__(self):
        self.checks: Dict[str, bool] = {}
        self.errors: List[str] = []
        
    async def check_api(self) -> bool:
        """Check if API is responding"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/health', timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.checks['api'] = data.get('status') == 'healthy'
                        return self.checks['api']
        except Exception as e:
            self.errors.append(f"API check failed: {str(e)}")
            self.checks['api'] = False
        return False
        
    async def check_database(self) -> bool:
        """Check database connectivity"""
        import os
        db_url = os.getenv('DATABASE_URL', '')
        
        if not db_url:
            self.errors.append("DATABASE_URL not set")
            self.checks['database'] = False
            return False
            
        try:
            # Parse connection string
            if db_url.startswith('postgresql+asyncpg://'):
                db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
                
            conn = await asyncpg.connect(db_url, timeout=5)
            await conn.fetchval('SELECT 1')
            await conn.close()
            
            self.checks['database'] = True
            return True
        except Exception as e:
            self.errors.append(f"Database check failed: {str(e)}")
            self.checks['database'] = False
        return False
        
    async def check_redis(self) -> bool:
        """Check Redis connectivity"""
        import os
        redis_url = os.getenv('REDIS_URL', '')
        
        if not redis_url:
            self.errors.append("REDIS_URL not set")
            self.checks['redis'] = False
            return False
            
        try:
            client = redis.from_url(redis_url, decode_responses=True)
            await client.ping()
            await client.close()
            
            self.checks['redis'] = True
            return True
        except Exception as e:
            self.errors.append(f"Redis check failed: {str(e)}")
            self.checks['redis'] = False
        return False
        
    async def check_disk_space(self) -> bool:
        """Check available disk space"""
        try:
            import shutil
            stat = shutil.disk_usage('/')
            # Check if we have at least 1GB free
            free_gb = stat.free / (1024 ** 3)
            self.checks['disk_space'] = free_gb > 1.0
            
            if not self.checks['disk_space']:
                self.errors.append(f"Low disk space: {free_gb:.2f}GB free")
            return self.checks['disk_space']
        except Exception as e:
            self.errors.append(f"Disk space check failed: {str(e)}")
            self.checks['disk_space'] = False
        return False
        
    async def check_memory(self) -> bool:
        """Check available memory"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            # Check if we have at least 10% free memory
            self.checks['memory'] = memory.percent < 90
            
            if not self.checks['memory']:
                self.errors.append(f"High memory usage: {memory.percent}%")
            return self.checks['memory']
        except Exception as e:
            self.errors.append(f"Memory check failed: {str(e)}")
            self.checks['memory'] = False
        return False
        
    async def run_all_checks(self) -> Tuple[bool, Dict[str, bool], List[str]]:
        """Run all health checks"""
        # Run checks concurrently
        results = await asyncio.gather(
            self.check_api(),
            self.check_database(),
            self.check_redis(),
            self.check_disk_space(),
            self.check_memory(),
            return_exceptions=True
        )
        
        # Check for exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_name = ['api', 'database', 'redis', 'disk_space', 'memory'][i]
                self.errors.append(f"{check_name} check exception: {str(result)}")
                self.checks[check_name] = False
                
        # Overall health is true only if all checks pass
        all_healthy = all(self.checks.values())
        
        return all_healthy, self.checks, self.errors
        

async def main():
    """Main health check function"""
    checker = HealthChecker()
    is_healthy, checks, errors = await checker.run_all_checks()
    
    # Print results for debugging
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
            
    print(f"Health Status: {'HEALTHY' if is_healthy else 'UNHEALTHY'}")
    for check, status in checks.items():
        print(f"  {check}: {'✓' if status else '✗'}")
        
    # Exit with appropriate code
    sys.exit(0 if is_healthy else 1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"Health check failed: {str(e)}", file=sys.stderr)
        sys.exit(1)