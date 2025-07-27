#!/usr/bin/env python3
"""
Validate production environment configuration
"""
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class EnvValidator:
    """Environment configuration validator"""
    
    REQUIRED_VARS = [
        'ENVIRONMENT',
        'SECRET_KEY',
        'DATABASE_URL',
        'REDIS_URL',
        'JWT_SECRET',
        'ENCRYPTION_KEY',
    ]
    
    SENSITIVE_VARS = [
        'SECRET_KEY',
        'DB_PASSWORD',
        'REDIS_PASSWORD',
        'JWT_SECRET',
        'ENCRYPTION_KEY',
        'SMTP_PASSWORD',
        'INFLOW_API_KEY',
        'ONLYFANS_API_KEY',
        'SENTRY_DSN',
        'STRIPE_SECRET_KEY',
        'AWS_SECRET_ACCESS_KEY',
        'CLOUDFLARE_SECRET_ACCESS_KEY',
    ]
    
    DEFAULT_VALUES = {
        'your-very-secure-secret-key-change-this',
        'your-secure-database-password',
        'your-secure-redis-password',
        'your-jwt-secret-key-change-this',
        'your-32-byte-encryption-key-base64',
        'your-smtp-password',
        'your-inflow-api-key',
        'your-onlyfans-api-key',
    }
    
    URL_PATTERNS = {
        'DATABASE_URL': r'^postgresql\+asyncpg:\/\/.+@.+:\d+\/.+$',
        'REDIS_URL': r'^redis:\/\/(:.+@)?.+:\d+\/\d+$',
        'FRONTEND_URL': r'^https?:\/\/.+$',
        'SENTRY_DSN': r'^https:\/\/.+@.+\.ingest\.sentry\.io\/\d+$',
    }
    
    def __init__(self, env_file: str = '.env.production'):
        self.env_file = env_file
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.env_vars: Dict[str, str] = {}
        
    def load_env_file(self) -> bool:
        """Load environment file"""
        try:
            env_path = Path(self.env_file)
            if not env_path.exists():
                self.errors.append(f"Environment file {self.env_file} not found")
                return False
                
            with open(env_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    if '=' not in line:
                        self.warnings.append(f"Line {line_num}: Invalid format (missing =)")
                        continue
                        
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                        
                    self.env_vars[key] = value
                    
            return True
            
        except Exception as e:
            self.errors.append(f"Error reading env file: {str(e)}")
            return False
            
    def validate_required(self):
        """Check for required variables"""
        for var in self.REQUIRED_VARS:
            if var not in self.env_vars:
                self.errors.append(f"Required variable {var} is missing")
            elif not self.env_vars[var]:
                self.errors.append(f"Required variable {var} is empty")
                
    def validate_sensitive(self):
        """Check sensitive variables for default values"""
        for var in self.SENSITIVE_VARS:
            if var in self.env_vars:
                value = self.env_vars[var]
                if value in self.DEFAULT_VALUES:
                    self.errors.append(f"Sensitive variable {var} still has default value")
                elif len(value) < 16:
                    self.warnings.append(f"Sensitive variable {var} seems too short (< 16 chars)")
                    
    def validate_urls(self):
        """Validate URL formats"""
        for var, pattern in self.URL_PATTERNS.items():
            if var in self.env_vars:
                value = self.env_vars[var]
                if value and not re.match(pattern, value):
                    self.errors.append(f"{var} has invalid format: {value}")
                    
    def validate_encryption_key(self):
        """Validate encryption key format"""
        if 'ENCRYPTION_KEY' in self.env_vars:
            key = self.env_vars['ENCRYPTION_KEY']
            try:
                import base64
                decoded = base64.b64decode(key)
                if len(decoded) != 32:
                    self.errors.append("ENCRYPTION_KEY must be 32 bytes when decoded")
            except Exception:
                self.errors.append("ENCRYPTION_KEY must be valid base64")
                
    def validate_booleans(self):
        """Validate boolean values"""
        bool_vars = ['DEBUG', 'SMTP_USE_TLS', 'RATE_LIMIT_ENABLED', 'MAINTENANCE_MODE']
        valid_values = {'true', 'false', 'True', 'False', '1', '0'}
        
        for var in bool_vars:
            if var in self.env_vars:
                value = self.env_vars[var]
                if value not in valid_values:
                    self.errors.append(f"{var} must be a boolean value (true/false)")
                    
    def validate_numbers(self):
        """Validate numeric values"""
        numeric_vars = {
            'DATABASE_POOL_SIZE': (1, 100),
            'REDIS_TTL': (60, 86400),
            'ACCESS_TOKEN_EXPIRE_MINUTES': (5, 1440),
            'REFRESH_TOKEN_EXPIRE_DAYS': (1, 90),
            'SMTP_PORT': (1, 65535),
            'WEB_CONCURRENCY': (1, 16),
            'MAX_REQUESTS': (100, 100000),
        }
        
        for var, (min_val, max_val) in numeric_vars.items():
            if var in self.env_vars:
                try:
                    value = int(self.env_vars[var])
                    if value < min_val or value > max_val:
                        self.warnings.append(f"{var} value {value} is outside recommended range [{min_val}, {max_val}]")
                except ValueError:
                    self.errors.append(f"{var} must be a number")
                    
    def validate_production_settings(self):
        """Validate production-specific settings"""
        if self.env_vars.get('ENVIRONMENT') != 'production':
            self.warnings.append("ENVIRONMENT is not set to 'production'")
            
        if self.env_vars.get('DEBUG', '').lower() == 'true':
            self.errors.append("DEBUG must be false in production")
            
        if 'localhost' in self.env_vars.get('ALLOWED_ORIGINS', ''):
            self.warnings.append("ALLOWED_ORIGINS contains localhost")
            
        if not self.env_vars.get('SENTRY_DSN'):
            self.warnings.append("SENTRY_DSN not configured - error tracking disabled")
            
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validations"""
        if not self.load_env_file():
            return False, self.errors, self.warnings
            
        self.validate_required()
        self.validate_sensitive()
        self.validate_urls()
        self.validate_encryption_key()
        self.validate_booleans()
        self.validate_numbers()
        self.validate_production_settings()
        
        return len(self.errors) == 0, self.errors, self.warnings
        
    def print_report(self):
        """Print validation report"""
        print(f"\n🔍 Validating {self.env_file}")
        print(f"Found {len(self.env_vars)} environment variables\n")
        
        if self.errors:
            print("❌ ERRORS:")
            for error in self.errors:
                print(f"  - {error}")
            print()
            
        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")
            print()
            
        if not self.errors and not self.warnings:
            print("✅ All validations passed!")
            
        return len(self.errors) == 0


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate environment configuration')
    parser.add_argument('--env-file', default='.env.production', help='Environment file to validate')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    args = parser.parse_args()
    
    validator = EnvValidator(args.env_file)
    is_valid, errors, warnings = validator.validate()
    
    validator.print_report()
    
    if args.strict and warnings:
        print("\n❌ Failed validation in strict mode (warnings treated as errors)")
        sys.exit(1)
    
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()