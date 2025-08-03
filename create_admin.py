"""Create admin user in database."""
import psycopg2
from passlib.context import CryptContext
import uuid
from datetime import datetime

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Generate password hash
password_hash = pwd_context.hash("admin123")

# Connect to database
conn = psycopg2.connect('postgresql://mariuszbudzisz@localhost/agencydark_dev')
cur = conn.cursor()

# Generate UUID
user_id = str(uuid.uuid4())

# Insert admin user
cur.execute("""
    INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (email) DO UPDATE SET
        hashed_password = EXCLUDED.hashed_password,
        full_name = EXCLUDED.full_name,
        role = EXCLUDED.role,
        is_active = EXCLUDED.is_active,
        is_verified = EXCLUDED.is_verified,
        updated_at = EXCLUDED.updated_at
""", (
    user_id,
    "admin@agency.com",
    password_hash,
    "Admin User",
    "SUPER_ADMIN",
    True,
    True,
    datetime.utcnow(),
    datetime.utcnow()
))

conn.commit()
cur.close()
conn.close()

print("✅ Admin user created/updated successfully!")
print(f"Email: admin@agency.com")
print(f"Password: admin123")