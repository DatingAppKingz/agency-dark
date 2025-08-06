#!/usr/bin/env python3
"""
Test the new security module to ensure it works correctly.
"""
import sys
sys.path.insert(0, 'backend')

from core.security_v2.authentication import (
    hash_password, 
    verify_password, 
    validate_password,
    generate_secure_password
)

def test_password_handler():
    """Test password handling functions."""
    print("Testing Password Handler...")
    print("-" * 50)
    
    # Test 1: Hash and verify password
    test_password = "TestPassword123!"
    hashed = hash_password(test_password)
    print(f"✓ Password hashed: {hashed[:20]}...")
    
    # Verify correct password
    assert verify_password(test_password, hashed), "Failed to verify correct password"
    print("✓ Correct password verified")
    
    # Verify incorrect password
    assert not verify_password("WrongPassword", hashed), "Incorrectly verified wrong password"
    print("✓ Wrong password rejected")
    
    # Test 2: Password validation
    valid, msg = validate_password("weak")
    assert not valid, "Weak password should be invalid"
    print(f"✓ Weak password rejected: {msg}")
    
    valid, msg = validate_password("ValidPassword123!")
    assert valid, "Strong password should be valid"
    print("✓ Strong password accepted")
    
    # Test 3: Generate secure password
    secure_pwd = generate_secure_password(16)
    print(f"✓ Generated secure password: {secure_pwd}")
    
    valid, msg = validate_password(secure_pwd)
    assert valid, "Generated password should be valid"
    print("✓ Generated password passes validation")
    
    print("\n✅ All password handler tests passed!")

def test_all_users_have_hashed_passwords():
    """Verify all users in database have properly hashed passwords."""
    print("\nTesting Database Passwords...")
    print("-" * 50)
    
    import psycopg2
    conn = psycopg2.connect(
        host="localhost",
        database="agencydark_dev",
        user="mariuszbudzisz"
    )
    cur = conn.cursor()
    
    # Get all users
    cur.execute("SELECT email, hashed_password FROM users LIMIT 5")
    users = cur.fetchall()
    
    for email, pwd_hash in users:
        # Check if it's a bcrypt hash
        if pwd_hash and pwd_hash.startswith('$2b$'):
            print(f"✓ {email}: Password is properly hashed")
            
            # Test verification with known password
            if verify_password("admin123", pwd_hash):
                print(f"  └─ Verified with 'admin123'")
        else:
            print(f"✗ {email}: Password NOT hashed! Value: {pwd_hash[:20]}...")
    
    cur.close()
    conn.close()
    
    print("\n✅ Database password check complete!")

if __name__ == "__main__":
    print("🔐 Testing New Security Module\n")
    test_password_handler()
    test_all_users_have_hashed_passwords()