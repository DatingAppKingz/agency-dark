#!/usr/bin/env python3
"""
Health Check Script

Performs comprehensive health checks on the Agency Dark backend.
Can be used for deployment validation, monitoring, and debugging.
"""
import asyncio
import sys
import json
import argparse
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp
import psutil
from sqlalchemy import create_engine, text
import redis

# Color output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'


class HealthChecker:
    """Comprehensive health checker for Agency Dark backend."""
    
    def __init__(self, api_url: str, database_url: str, redis_url: str):
        self.api_url = api_url.rstrip('/')
        self.database_url = database_url
        self.redis_url = redis_url
        self.results = {}
        
    async def check_api_health(self) -> Dict[str, Any]:
        """Check API server health."""
        try:
            async with aiohttp.ClientSession() as session:
                # Check main health endpoint
                async with session.get(f"{self.api_url}/health") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "status": "healthy",
                            "response_time": resp.headers.get("X-Response-Time", "N/A"),
                            "data": data
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "error": f"HTTP {resp.status}"
                        }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_api_endpoints(self) -> Dict[str, Any]:
        """Check critical API endpoints."""
        endpoints = [
            ("/api/v1/users", "GET"),
            ("/api/v1/agencies", "GET"),
            ("/api/v1/auth/login", "POST"),
            ("/metrics", "GET"),
            ("/docs", "GET")
        ]
        
        results = {}
        async with aiohttp.ClientSession() as session:
            for endpoint, method in endpoints:
                try:
                    url = f"{self.api_url}{endpoint}"
                    
                    if method == "GET":
                        async with session.get(url) as resp:
                            results[endpoint] = {
                                "status": "healthy" if resp.status < 500 else "unhealthy",
                                "http_status": resp.status,
                                "response_time": resp.headers.get("X-Response-Time", "N/A")
                            }
                    elif method == "POST":
                        # For POST endpoints, just check if they're accessible
                        async with session.post(url, json={}) as resp:
                            results[endpoint] = {
                                "status": "healthy" if resp.status < 500 else "unhealthy",
                                "http_status": resp.status
                            }
                            
                except Exception as e:
                    results[endpoint] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
        
        return results
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            engine = create_engine(self.database_url)
            
            with engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
                
                # Check database version
                version_result = conn.execute(text("SELECT version()"))
                db_version = version_result.fetchone()[0]
                
                # Check table count
                tables_result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
                table_count = tables_result.fetchone()[0]
                
                # Check connection count
                conn_result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """))
                active_connections = conn_result.fetchone()[0]
                
                return {
                    "status": "healthy",
                    "version": db_version,
                    "tables": table_count,
                    "active_connections": active_connections
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity and stats."""
        try:
            r = redis.from_url(self.redis_url)
            
            # Test connectivity
            r.ping()
            
            # Get info
            info = r.info()
            
            return {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "uptime_days": info.get("uptime_in_days", 0)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        return {
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count()
            },
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2)
            },
            "disk": {
                "percent": psutil.disk_usage('/').percent,
                "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2)
            },
            "network": {
                "connections": len(psutil.net_connections())
            }
        }
    
    async def check_external_services(self) -> Dict[str, Any]:
        """Check connectivity to external services."""
        services = {
            "dns": "8.8.8.8",
            "ntp": "time.google.com",
            "docker_hub": "hub.docker.com"
        }
        
        results = {}
        async with aiohttp.ClientSession() as session:
            for service, host in services.items():
                try:
                    if service == "dns":
                        # Simple DNS check
                        import socket
                        socket.gethostbyname(host)
                        results[service] = {"status": "healthy"}
                    else:
                        # HTTP check
                        async with session.get(f"https://{host}", timeout=5) as resp:
                            results[service] = {
                                "status": "healthy" if resp.status < 500 else "unhealthy",
                                "http_status": resp.status
                            }
                except Exception as e:
                    results[service] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
        
        return results
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        print(f"{Colors.BLUE}Running comprehensive health checks...{Colors.ENDC}\n")
        
        # API Health
        print("Checking API health...")
        self.results["api_health"] = await self.check_api_health()
        self._print_result("API Health", self.results["api_health"])
        
        # API Endpoints
        print("\nChecking API endpoints...")
        self.results["api_endpoints"] = await self.check_api_endpoints()
        self._print_endpoints_result(self.results["api_endpoints"])
        
        # Database
        print("\nChecking database...")
        self.results["database"] = self.check_database_health()
        self._print_result("Database", self.results["database"])
        
        # Redis
        print("\nChecking Redis...")
        self.results["redis"] = self.check_redis_health()
        self._print_result("Redis", self.results["redis"])
        
        # System Resources
        print("\nChecking system resources...")
        self.results["system"] = self.check_system_resources()
        self._print_system_result(self.results["system"])
        
        # External Services
        print("\nChecking external services...")
        self.results["external_services"] = await self.check_external_services()
        self._print_external_services_result(self.results["external_services"])
        
        # Overall status
        overall_status = self._calculate_overall_status()
        self.results["overall_status"] = overall_status
        self.results["timestamp"] = datetime.utcnow().isoformat()
        
        print(f"\n{Colors.BLUE}={'='*50}{Colors.ENDC}")
        if overall_status == "healthy":
            print(f"{Colors.GREEN}✓ Overall Status: HEALTHY{Colors.ENDC}")
        elif overall_status == "degraded":
            print(f"{Colors.YELLOW}⚠ Overall Status: DEGRADED{Colors.ENDC}")
        else:
            print(f"{Colors.RED}✗ Overall Status: UNHEALTHY{Colors.ENDC}")
        
        return self.results
    
    def _print_result(self, name: str, result: Dict[str, Any]):
        """Print a single check result."""
        status = result.get("status", "unknown")
        if status == "healthy":
            print(f"{Colors.GREEN}✓ {name}: HEALTHY{Colors.ENDC}")
            if "version" in result:
                print(f"  Version: {result['version']}")
            if "response_time" in result:
                print(f"  Response Time: {result['response_time']}")
        else:
            print(f"{Colors.RED}✗ {name}: UNHEALTHY{Colors.ENDC}")
            if "error" in result:
                print(f"  Error: {result['error']}")
    
    def _print_endpoints_result(self, results: Dict[str, Any]):
        """Print endpoints check results."""
        for endpoint, result in results.items():
            status = result.get("status", "unknown")
            http_status = result.get("http_status", "N/A")
            
            if status == "healthy":
                print(f"{Colors.GREEN}✓ {endpoint}: {http_status}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}✗ {endpoint}: {http_status}{Colors.ENDC}")
                if "error" in result:
                    print(f"  Error: {result['error']}")
    
    def _print_system_result(self, result: Dict[str, Any]):
        """Print system resources result."""
        cpu = result["cpu"]["percent"]
        memory = result["memory"]["percent"]
        disk = result["disk"]["percent"]
        
        # CPU
        if cpu < 80:
            print(f"{Colors.GREEN}✓ CPU: {cpu}%{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}⚠ CPU: {cpu}%{Colors.ENDC}")
        
        # Memory
        if memory < 80:
            print(f"{Colors.GREEN}✓ Memory: {memory}% ({result['memory']['available_gb']}GB available){Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}⚠ Memory: {memory}% ({result['memory']['available_gb']}GB available){Colors.ENDC}")
        
        # Disk
        if disk < 90:
            print(f"{Colors.GREEN}✓ Disk: {disk}% ({result['disk']['free_gb']}GB free){Colors.ENDC}")
        else:
            print(f"{Colors.RED}✗ Disk: {disk}% ({result['disk']['free_gb']}GB free){Colors.ENDC}")
    
    def _print_external_services_result(self, results: Dict[str, Any]):
        """Print external services check results."""
        for service, result in results.items():
            status = result.get("status", "unknown")
            if status == "healthy":
                print(f"{Colors.GREEN}✓ {service}: HEALTHY{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}⚠ {service}: UNHEALTHY{Colors.ENDC}")
                if "error" in result:
                    print(f"  Error: {result['error']}")
    
    def _calculate_overall_status(self) -> str:
        """Calculate overall system status."""
        critical_checks = ["api_health", "database", "redis"]
        
        # Check critical services
        for check in critical_checks:
            if check in self.results:
                if self.results[check].get("status") != "healthy":
                    return "unhealthy"
        
        # Check system resources
        if "system" in self.results:
            system = self.results["system"]
            if system["cpu"]["percent"] > 90 or system["memory"]["percent"] > 90:
                return "degraded"
            if system["disk"]["percent"] > 95:
                return "unhealthy"
        
        # Check API endpoints
        if "api_endpoints" in self.results:
            unhealthy_count = sum(
                1 for r in self.results["api_endpoints"].values()
                if r.get("status") != "healthy"
            )
            if unhealthy_count > len(self.results["api_endpoints"]) / 2:
                return "degraded"
        
        return "healthy"


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Agency Dark Backend Health Checker")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--database-url", default="postgresql://localhost/agency_dark", help="Database URL")
    parser.add_argument("--redis-url", default="redis://localhost:6379", help="Redis URL")
    parser.add_argument("--output", choices=["console", "json"], default="console", help="Output format")
    parser.add_argument("--output-file", help="Output file for JSON format")
    
    args = parser.parse_args()
    
    # Create health checker
    checker = HealthChecker(
        api_url=args.api_url,
        database_url=args.database_url,
        redis_url=args.redis_url
    )
    
    # Run checks
    results = await checker.run_all_checks()
    
    # Output results
    if args.output == "json":
        json_output = json.dumps(results, indent=2)
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(json_output)
            print(f"\nResults written to {args.output_file}")
        else:
            print(f"\n{json_output}")
    
    # Exit with appropriate code
    overall_status = results.get("overall_status", "unknown")
    if overall_status == "healthy":
        sys.exit(0)
    elif overall_status == "degraded":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())