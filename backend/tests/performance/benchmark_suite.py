"""
Comprehensive benchmark suite for AgencyDark platform.
"""
import asyncio
import time
import json
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Callable
from decimal import Decimal
from uuid import uuid4
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import aioredis
import numpy as np

from core.database import Base
from modules.analytics.application.analytics_service import AnalyticsService
from modules.messaging.application.bulk_message_service import BulkMessageService
from modules.financial.application.transaction_service import TransactionService
from modules.reporting.application.report_builder_service import ReportBuilderService


class BenchmarkResult:
    """Store and analyze benchmark results."""
    
    def __init__(self, name: str):
        self.name = name
        self.measurements: List[float] = []
        self.metadata: Dict[str, Any] = {}
        self.start_time = None
        self.end_time = None
    
    def add_measurement(self, duration: float, **kwargs):
        """Add a measurement."""
        self.measurements.append(duration)
        for key, value in kwargs.items():
            if key not in self.metadata:
                self.metadata[key] = []
            self.metadata[key].append(value)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate statistics."""
        if not self.measurements:
            return {}
        
        sorted_measurements = sorted(self.measurements)
        n = len(self.measurements)
        
        return {
            "name": self.name,
            "count": n,
            "min": min(self.measurements),
            "max": max(self.measurements),
            "mean": statistics.mean(self.measurements),
            "median": statistics.median(self.measurements),
            "std_dev": statistics.stdev(self.measurements) if n > 1 else 0,
            "p50": sorted_measurements[int(0.50 * n)],
            "p90": sorted_measurements[int(0.90 * n)],
            "p95": sorted_measurements[int(0.95 * n)],
            "p99": sorted_measurements[int(0.99 * n)],
            "throughput": n / (self.end_time - self.start_time) if self.end_time else 0
        }
    
    def plot_distribution(self, save_path: str = None):
        """Plot measurement distribution."""
        plt.figure(figsize=(10, 6))
        plt.hist(self.measurements, bins=50, alpha=0.7, color='blue', edgecolor='black')
        plt.axvline(statistics.mean(self.measurements), color='red', linestyle='dashed', linewidth=2, label='Mean')
        plt.axvline(statistics.median(self.measurements), color='green', linestyle='dashed', linewidth=2, label='Median')
        plt.xlabel('Duration (seconds)')
        plt.ylabel('Frequency')
        plt.title(f'Distribution of {self.name}')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()


class BenchmarkSuite:
    """Comprehensive benchmark suite."""
    
    def __init__(self):
        self.results: Dict[str, BenchmarkResult] = {}
        self.engine = None
        self.redis = None
        self.session_factory = None
    
    async def setup(self):
        """Setup test environment."""
        # Setup database
        self.engine = create_async_engine(
            "postgresql+asyncpg://test:test@localhost/agencydark_bench",
            echo=False
        )
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        self.session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Setup Redis
        self.redis = await aioredis.create_redis_pool('redis://localhost')
        
        # Generate test data
        await self._generate_test_data()
    
    async def teardown(self):
        """Cleanup test environment."""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
        
        if self.engine:
            await self.engine.dispose()
    
    async def _generate_test_data(self):
        """Generate comprehensive test data."""
        async with self.session_factory() as session:
            # Create agencies
            agencies = []
            for i in range(5):
                agency = {
                    "id": uuid4(),
                    "name": f"Benchmark Agency {i}",
                    "subdomain": f"bench{i}"
                }
                agencies.append(agency)
            
            # Create models
            models = []
            for agency in agencies:
                for j in range(10):
                    model = {
                        "id": uuid4(),
                        "agency_id": agency["id"],
                        "username": f"model_{i}_{j}",
                        "platform": "onlyfans"
                    }
                    models.append(model)
            
            # Create fans
            fans = []
            for model in models:
                for k in range(100):
                    fan = {
                        "id": uuid4(),
                        "model_id": model["id"],
                        "username": f"fan_{k}",
                        "total_spent": Decimal(str(random.uniform(10, 1000)))
                    }
                    fans.append(fan)
            
            # Store test data IDs for benchmarks
            self.test_data = {
                "agencies": agencies,
                "models": models,
                "fans": fans
            }
    
    async def run_benchmark(self, name: str, func: Callable, iterations: int = 100, **kwargs):
        """Run a benchmark."""
        result = BenchmarkResult(name)
        result.start_time = time.time()
        
        # Warmup
        for _ in range(min(10, iterations // 10)):
            await func(**kwargs)
        
        # Actual benchmark
        for i in range(iterations):
            start = time.time()
            output = await func(**kwargs)
            duration = time.time() - start
            
            result.add_measurement(duration, output=output)
            
            if i % 10 == 0:
                print(f"{name}: {i}/{iterations} iterations completed")
        
        result.end_time = time.time()
        self.results[name] = result
        
        return result
    
    async def benchmark_analytics_aggregation(self):
        """Benchmark analytics aggregation performance."""
        analytics_service = AnalyticsService()
        model_ids = [m["id"] for m in self.test_data["models"][:10]]
        
        async def aggregate_analytics():
            async with self.session_factory() as session:
                results = []
                for model_id in model_ids:
                    result = await analytics_service.get_model_analytics(
                        model_id=model_id,
                        date_from=datetime.now() - timedelta(days=30),
                        date_to=datetime.now(),
                        db=session
                    )
                    results.append(result)
                return len(results)
        
        return await self.run_benchmark(
            "Analytics Aggregation",
            aggregate_analytics,
            iterations=50
        )
    
    async def benchmark_bulk_message_creation(self):
        """Benchmark bulk message creation."""
        bulk_service = BulkMessageService()
        model_id = self.test_data["models"][0]["id"]
        
        async def create_bulk_campaign():
            async with self.session_factory() as session:
                campaign = await bulk_service.create_bulk_campaign(
                    campaign_data={
                        "campaign_name": f"Benchmark {uuid4()}",
                        "model_id": model_id,
                        "message_template": "Test {{display_name}}",
                        "recipient_filters": {"subscription_status": ["active"]},
                        "platform": "onlyfans"
                    },
                    agency_id=self.test_data["agencies"][0]["id"],
                    user_id=uuid4(),
                    db=session
                )
                return campaign.total_recipients
        
        return await self.run_benchmark(
            "Bulk Message Creation",
            create_bulk_campaign,
            iterations=30
        )
    
    async def benchmark_transaction_processing(self):
        """Benchmark transaction processing."""
        transaction_service = TransactionService()
        
        async def process_transaction():
            async with self.session_factory() as session:
                transaction = await transaction_service.create_transaction(
                    transaction_data={
                        "model_id": self.test_data["models"][0]["id"],
                        "fan_id": self.test_data["fans"][0]["id"],
                        "amount": Decimal("50.00"),
                        "currency": "USD",
                        "transaction_type": "tip",
                        "platform": "onlyfans"
                    },
                    agency_id=self.test_data["agencies"][0]["id"],
                    db=session
                )
                
                # Process commission
                commission = await transaction_service.calculate_commission(
                    transaction_id=transaction.id,
                    db=session
                )
                
                return commission.commission_amount
        
        return await self.run_benchmark(
            "Transaction Processing",
            process_transaction,
            iterations=100
        )
    
    async def benchmark_report_generation(self):
        """Benchmark report generation."""
        report_service = ReportBuilderService()
        
        async def generate_report():
            async with self.session_factory() as session:
                # Create a simple template
                template = await report_service.create_report_template(
                    data={
                        "name": f"Benchmark Template {uuid4()}",
                        "report_type": "revenue",
                        "widgets": [
                            {
                                "type": "metric",
                                "config": {"metric_type": "revenue"},
                                "size": "medium"
                            }
                        ]
                    },
                    agency_id=self.test_data["agencies"][0]["id"],
                    user_id=uuid4(),
                    db=session
                )
                
                # Generate report
                report = await report_service.generate_report(
                    template_id=template.id,
                    request={
                        "date_from": datetime.now() - timedelta(days=30),
                        "date_to": datetime.now()
                    },
                    agency_id=self.test_data["agencies"][0]["id"],
                    user_id=uuid4(),
                    db=session
                )
                
                return len(json.dumps(report.report_data))
        
        return await self.run_benchmark(
            "Report Generation",
            generate_report,
            iterations=20
        )
    
    async def benchmark_cache_operations(self):
        """Benchmark cache operations."""
        
        async def cache_operations():
            key = f"bench:{uuid4()}"
            value = {"data": "x" * 1000, "timestamp": datetime.now().isoformat()}
            
            # Write
            await self.redis.setex(key, 3600, json.dumps(value))
            
            # Read
            cached = await self.redis.get(key)
            
            # Delete
            await self.redis.delete(key)
            
            return len(cached) if cached else 0
        
        return await self.run_benchmark(
            "Cache Operations",
            cache_operations,
            iterations=1000
        )
    
    async def benchmark_database_queries(self):
        """Benchmark various database query patterns."""
        queries = {
            "Simple Select": """
                SELECT id, username, total_spent 
                FROM fans 
                WHERE model_id = $1 
                LIMIT 100
            """,
            "Aggregation": """
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM transactions
                WHERE model_id = $1
                    AND created_at > $2
                GROUP BY DATE(created_at)
            """,
            "Complex Join": """
                SELECT 
                    f.id,
                    f.username,
                    COUNT(t.id) as transaction_count,
                    SUM(t.amount) as total_spent
                FROM fans f
                LEFT JOIN transactions t ON f.id = t.fan_id
                WHERE f.model_id = $1
                GROUP BY f.id, f.username
                HAVING SUM(t.amount) > 100
                ORDER BY total_spent DESC
                LIMIT 50
            """
        }
        
        results = {}
        
        for query_name, query in queries.items():
            async def run_query():
                async with self.session_factory() as session:
                    result = await session.execute(
                        query,
                        {
                            "1": self.test_data["models"][0]["id"],
                            "2": datetime.now() - timedelta(days=30)
                        }
                    )
                    return len(result.fetchall())
            
            result = await self.run_benchmark(
                f"DB Query: {query_name}",
                run_query,
                iterations=100
            )
            results[query_name] = result
        
        return results
    
    async def benchmark_concurrent_operations(self):
        """Benchmark system under concurrent load."""
        
        async def concurrent_task(task_id: int):
            # Mix of operations
            if task_id % 4 == 0:
                # Analytics query
                async with self.session_factory() as session:
                    # Simulate analytics query
                    await asyncio.sleep(0.01)
                    return "analytics"
            elif task_id % 4 == 1:
                # Cache operation
                await self.redis.get(f"key:{task_id}")
                return "cache"
            elif task_id % 4 == 2:
                # Database write
                async with self.session_factory() as session:
                    # Simulate DB write
                    await asyncio.sleep(0.02)
                    return "db_write"
            else:
                # API call simulation
                await asyncio.sleep(0.005)
                return "api"
        
        concurrency_levels = [10, 50, 100, 200, 500]
        results = {}
        
        for concurrency in concurrency_levels:
            async def run_concurrent():
                tasks = [concurrent_task(i) for i in range(concurrency)]
                start = time.time()
                results = await asyncio.gather(*tasks)
                duration = time.time() - start
                return {"duration": duration, "count": len(results)}
            
            result = await self.run_benchmark(
                f"Concurrent Operations (n={concurrency})",
                run_concurrent,
                iterations=20
            )
            results[concurrency] = result
        
        return results
    
    def generate_report(self, output_file: str = "benchmark_report.json"):
        """Generate comprehensive benchmark report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": {}
        }
        
        for name, result in self.results.items():
            report["benchmarks"][name] = result.get_statistics()
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate summary
        print("\n" + "="*80)
        print("BENCHMARK SUMMARY")
        print("="*80)
        
        for name, result in self.results.items():
            stats = result.get_statistics()
            print(f"\n{name}:")
            print(f"  Iterations: {stats['count']}")
            print(f"  Mean: {stats['mean']*1000:.2f}ms")
            print(f"  Median: {stats['median']*1000:.2f}ms")
            print(f"  P95: {stats['p95']*1000:.2f}ms")
            print(f"  P99: {stats['p99']*1000:.2f}ms")
            print(f"  Throughput: {stats['throughput']:.2f} ops/sec")
        
        return report
    
    def plot_comparison(self, benchmark_names: List[str], metric: str = "mean"):
        """Plot comparison of benchmarks."""
        plt.figure(figsize=(12, 6))
        
        names = []
        values = []
        
        for name in benchmark_names:
            if name in self.results:
                stats = self.results[name].get_statistics()
                names.append(name)
                values.append(stats[metric] * 1000)  # Convert to ms
        
        plt.bar(names, values, color='skyblue', edgecolor='navy')
        plt.xlabel('Benchmark')
        plt.ylabel(f'{metric.title()} Time (ms)')
        plt.title(f'Benchmark Comparison - {metric.title()}')
        plt.xticks(rotation=45, ha='right')
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.show()


async def run_full_benchmark_suite():
    """Run the complete benchmark suite."""
    suite = BenchmarkSuite()
    
    try:
        print("Setting up benchmark environment...")
        await suite.setup()
        
        print("\nRunning benchmarks...")
        
        # Core benchmarks
        await suite.benchmark_analytics_aggregation()
        await suite.benchmark_bulk_message_creation()
        await suite.benchmark_transaction_processing()
        await suite.benchmark_report_generation()
        await suite.benchmark_cache_operations()
        
        # Database benchmarks
        await suite.benchmark_database_queries()
        
        # Concurrency benchmarks
        await suite.benchmark_concurrent_operations()
        
        # Generate report
        report = suite.generate_report()
        
        # Generate plots
        suite.plot_comparison([
            "Analytics Aggregation",
            "Bulk Message Creation",
            "Transaction Processing",
            "Report Generation"
        ])
        
        # Performance recommendations
        print("\n" + "="*80)
        print("PERFORMANCE RECOMMENDATIONS")
        print("="*80)
        
        for name, result in suite.results.items():
            stats = result.get_statistics()
            
            if stats['p95'] > 1.0:  # More than 1 second
                print(f"\n⚠️  {name}: P95 latency is high ({stats['p95']:.2f}s)")
                print("   Recommendations:")
                print("   - Add caching for frequently accessed data")
                print("   - Optimize database queries with proper indexes")
                print("   - Consider async processing for heavy operations")
            
            if stats['std_dev'] / stats['mean'] > 0.5:  # High variance
                print(f"\n⚠️  {name}: High variance in response times")
                print("   Recommendations:")
                print("   - Investigate sporadic slow queries")
                print("   - Check for resource contention")
                print("   - Add request queuing for stability")
        
    finally:
        print("\nCleaning up...")
        await suite.teardown()


if __name__ == "__main__":
    asyncio.run(run_full_benchmark_suite())