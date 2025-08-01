"""Seed data configuration using environment variables."""

import os
from typing import Dict, Any

def get_seed_password(user_type: str, default: str = None) -> str:
    """Get password for seed user from environment or use default."""
    env_key = f"SEED_{user_type.upper()}_PASSWORD"
    password = os.getenv(env_key)
    
    if not password and default:
        # In development, use default but warn
        if os.getenv("ENVIRONMENT", "development") == "development":
            print(f"WARNING: Using default password for {user_type}. Set {env_key} in production!")
            return default
        else:
            raise ValueError(f"Password not set for {user_type}. Please set {env_key} environment variable.")
    
    return password or ""

# Seed user configuration
SEED_USERS = {
    "super_admin": {
        "email": os.getenv("SEED_ADMIN_EMAIL", "admin@agencydark.com"),
        "username": "admin",
        "password": get_seed_password("admin", "admin123"),
        "first_name": "Super",
        "last_name": "Admin"
    },
    "agency_owner": {
        "email": os.getenv("SEED_OWNER_EMAIL", "owner@elitemodels.com"),
        "username": "elite_owner",
        "password": get_seed_password("owner", "owner123"),
        "first_name": "John",
        "last_name": "Elite"
    },
    "model": {
        "email": os.getenv("SEED_MODEL_EMAIL", "sarah@elitemodels.com"),
        "username": "sarah_model",
        "password": get_seed_password("model", "model123"),
        "first_name": "Sarah",
        "last_name": "Johnson"
    },
    "chatter": {
        "email": os.getenv("SEED_CHATTER_EMAIL", "mike@elitemodels.com"),
        "username": "mike_chatter",
        "password": get_seed_password("chatter", "chatter123"),
        "first_name": "Mike",
        "last_name": "Davis"
    }
}

def should_seed_data() -> bool:
    """Check if data seeding is enabled."""
    return os.getenv("ENABLE_SEED_DATA", "false").lower() == "true"

def get_seed_config() -> Dict[str, Any]:
    """Get complete seed configuration."""
    return {
        "enabled": should_seed_data(),
        "users": SEED_USERS,
        "environment": os.getenv("ENVIRONMENT", "development")
    }