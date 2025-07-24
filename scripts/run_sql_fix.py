#!/usr/bin/env python3
"""
Execute SQL fix script against the database
"""

import subprocess
import os
import sys

# Database URL from backend .env
DATABASE_URL = "postgresql://postgres:i6cx9yJ3vBLHT6nb@db.qrabdwmdewqzpozgfiju.supabase.co:5432/postgres?sslmode=require"

def run_sql_file(sql_file):
    """Run SQL file using psql"""
    print(f"🔧 Executing SQL fixes from {sql_file}...")
    
    # Use docker to run psql since we don't have it installed locally
    cmd = [
        "docker", "run", "--rm", "-i",
        "-e", f"PGPASSWORD={DATABASE_URL.split(':')[2].split('@')[0]}",
        "postgres:16-alpine",
        "psql", DATABASE_URL,
        "-f", "-"
    ]
    
    try:
        with open(sql_file, 'r') as f:
            result = subprocess.run(cmd, stdin=f, capture_output=True, text=True)
            
        if result.returncode == 0:
            print("✅ SQL executed successfully!")
            print("\nOutput:")
            print(result.stdout)
        else:
            print("❌ SQL execution failed!")
            print("\nError:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    sql_file = os.path.join(os.path.dirname(__file__), "fix_user_roles_and_data.sql")
    
    if not os.path.exists(sql_file):
        print(f"❌ SQL file not found: {sql_file}")
        sys.exit(1)
        
    if run_sql_file(sql_file):
        print("\n🎉 Database fixes applied successfully!")
        print("\nNext steps:")
        print("1. Restart the backend: docker-compose restart backend")
        print("2. Run enhanced tests: python scripts/test_api_endpoints_enhanced.py")
    else:
        print("\n❌ Failed to apply database fixes")
        sys.exit(1)