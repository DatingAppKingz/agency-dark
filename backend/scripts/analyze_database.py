"""
Database analysis and optimization script.
"""
import asyncio
import argparse
import json
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.database_utils.query_analyzer import QueryAnalyzer, QueryOptimizer


async def analyze_database(
    output_format: str = "text",
    output_file: str = None
):
    """Run comprehensive database analysis."""
    print("Starting database analysis...")
    
    async with AsyncSessionLocal() as session:
        # Generate optimization report
        report = await QueryAnalyzer.generate_optimization_report(session)
        
        if output_format == "json":
            output = json.dumps(report, indent=2, default=str)
        else:
            # Format as text
            output_lines = [
                "=" * 80,
                "DATABASE OPTIMIZATION REPORT",
                f"Generated: {report['generated_at']}",
                "=" * 80,
                ""
            ]
            
            # Slow queries section
            slow_queries = report["sections"]["slow_queries"]
            output_lines.extend([
                "SLOW QUERIES",
                "-" * 40,
                f"Total slow queries: {slow_queries['count']}",
                ""
            ])
            
            for i, query in enumerate(slow_queries["queries"][:5], 1):
                output_lines.extend([
                    f"{i}. Query (mean: {query['mean_time_ms']}ms, calls: {query['calls']})",
                    f"   {query['query'][:100]}...",
                    ""
                ])
            
            # Missing indexes section
            missing_indexes = report["sections"]["missing_indexes"]
            if missing_indexes["tables"]:
                output_lines.extend([
                    "",
                    "TABLES NEEDING INDEXES",
                    "-" * 40,
                    f"Total tables: {missing_indexes['count']}",
                    ""
                ])
                
                for table in missing_indexes["tables"][:5]:
                    output_lines.extend([
                        f"Table: {table['table']}",
                        f"  Sequential scan ratio: {table['seq_scan_ratio']}%",
                        f"  Sequential scans: {table['seq_scans']:,}",
                        f"  Rows read sequentially: {table['rows_read_seq']:,}",
                        ""
                    ])
            
            # Table bloat section
            bloated_tables = report["sections"]["table_bloat"]
            if bloated_tables["tables"]:
                output_lines.extend([
                    "",
                    "BLOATED TABLES",
                    "-" * 40,
                    f"Total bloated tables: {bloated_tables['count']}",
                    ""
                ])
                
                for table in bloated_tables["tables"][:5]:
                    output_lines.extend([
                        f"Table: {table['table']}",
                        f"  Bloat ratio: {table['bloat_ratio']}",
                        f"  Size: {table['total_size']}",
                        f"  Dead tuples: {table['dead_tuples']:,}",
                        f"  Action: {table['action']}",
                        ""
                    ])
            
            # Unused indexes section
            unused_indexes = report["sections"]["unused_indexes"]
            if unused_indexes["indexes"]:
                output_lines.extend([
                    "",
                    "UNUSED INDEXES",
                    "-" * 40,
                    f"Total unused indexes: {unused_indexes['count']}",
                    ""
                ])
                
                for idx in unused_indexes["indexes"][:5]:
                    output_lines.extend([
                        f"Index: {idx['index']} on {idx['table']}",
                        f"  Size: {idx['size']}",
                        f"  Status: {idx['status']}",
                        ""
                    ])
            
            # Connection stats
            connections = report["sections"]["connections"]["stats"]
            output_lines.extend([
                "",
                "CONNECTION STATISTICS",
                "-" * 40,
                f"Total connections: {connections['total_connections']}",
                f"Active connections: {connections['active_connections']}",
                f"Idle connections: {connections['idle_connections']}",
                f"Idle in transaction: {connections['idle_in_transaction']}",
                f"Longest connection: {connections['longest_connection_minutes']} minutes",
                f"Longest idle: {connections['longest_idle_minutes']} minutes",
                ""
            ])
            
            # Recommendations summary
            output_lines.extend([
                "",
                "RECOMMENDATIONS SUMMARY",
                "-" * 40
            ])
            
            for section, data in report["sections"].items():
                if "recommendation" in data:
                    output_lines.append(f"• {data['recommendation']}")
            
            output = "\n".join(output_lines)
        
        # Output results
        if output_file:
            with open(output_file, "w") as f:
                f.write(output)
            print(f"Report saved to: {output_file}")
        else:
            print(output)


async def optimize_specific_query(query: str):
    """Analyze and optimize a specific query."""
    print("Analyzing query...")
    
    async with AsyncSessionLocal() as session:
        # Get execution plan
        plan = await QueryAnalyzer.get_query_execution_plan(session, query)
        
        # Get optimization suggestions
        suggestions = QueryOptimizer.optimize_query(query)
        
        print("\nQUERY ANALYSIS")
        print("-" * 40)
        print(f"Query: {query[:100]}...")
        
        if plan:
            print("\nExecution Plan:")
            print(json.dumps(plan, indent=2))
        
        print("\nOptimization Suggestions:")
        if suggestions["suggestions"]:
            for i, suggestion in enumerate(suggestions["suggestions"], 1):
                print(f"{i}. {suggestion['issue']}: {suggestion['suggestion']}")
        else:
            print("No optimization issues found.")


async def vacuum_tables(analyze: bool = True):
    """Run VACUUM on all tables."""
    print("Running VACUUM on all tables...")
    
    async with AsyncSessionLocal() as session:
        # Get all tables
        result = await session.execute(
            text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)
        )
        
        tables = [row.tablename for row in result]
        
        for table in tables:
            try:
                print(f"Vacuuming {table}...")
                if analyze:
                    await session.execute(text(f"VACUUM ANALYZE {table}"))
                else:
                    await session.execute(text(f"VACUUM {table}"))
                await session.commit()
            except Exception as e:
                print(f"Error vacuuming {table}: {e}")
                await session.rollback()
        
        print("VACUUM complete.")


async def refresh_materialized_views():
    """Refresh all materialized views."""
    print("Refreshing materialized views...")
    
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("CALL refresh_analytics_views()"))
            await session.commit()
            print("Materialized views refreshed successfully.")
        except Exception as e:
            print(f"Error refreshing views: {e}")
            await session.rollback()


def main():
    parser = argparse.ArgumentParser(description="Database analysis and optimization tool")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run database analysis")
    analyze_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    analyze_parser.add_argument(
        "--output",
        help="Output file path"
    )
    
    # Optimize query command
    optimize_parser = subparsers.add_parser("optimize-query", help="Optimize specific query")
    optimize_parser.add_argument("query", help="SQL query to optimize")
    
    # Vacuum command
    vacuum_parser = subparsers.add_parser("vacuum", help="Run VACUUM on all tables")
    vacuum_parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="Skip ANALYZE"
    )
    
    # Refresh views command
    subparsers.add_parser("refresh-views", help="Refresh materialized views")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        asyncio.run(analyze_database(args.format, args.output))
    elif args.command == "optimize-query":
        asyncio.run(optimize_specific_query(args.query))
    elif args.command == "vacuum":
        asyncio.run(vacuum_tables(not args.no_analyze))
    elif args.command == "refresh-views":
        asyncio.run(refresh_materialized_views())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()