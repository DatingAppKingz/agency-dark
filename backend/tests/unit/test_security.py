"""
Unit tests for security features.
"""
import pytest
from backend.core.validation import InputValidator, ValidationError
from backend.core.encryption import EncryptionService, mask_email, mask_phone, mask_api_key
from backend.core.api_keys import APIKeyManager
from backend.core.audit import AuditLogger, AuditEventType
import re


class TestInputValidation:
    """Test input validation utilities."""
    
    def test_email_validation(self):
        """Test email validation."""
        # Valid emails
        assert InputValidator.validate_email("test@example.com") == "test@example.com"
        assert InputValidator.validate_email("USER@EXAMPLE.COM") == "user@example.com"
        assert InputValidator.validate_email("  test@example.com  ") == "test@example.com"
        
        # Invalid emails
        with pytest.raises(ValidationError):
            InputValidator.validate_email("invalid.email")
        with pytest.raises(ValidationError):
            InputValidator.validate_email("@example.com")
        with pytest.raises(ValidationError):
            InputValidator.validate_email("test@")
    
    def test_username_validation(self):
        """Test username validation."""
        # Valid usernames
        assert InputValidator.validate_username("user123") == "user123"
        assert InputValidator.validate_username("test_user") == "test_user"
        assert InputValidator.validate_username("user-name") == "user-name"
        
        # Invalid usernames
        with pytest.raises(ValidationError):
            InputValidator.validate_username("ab")  # Too short
        with pytest.raises(ValidationError):
            InputValidator.validate_username("a" * 33)  # Too long
        with pytest.raises(ValidationError):
            InputValidator.validate_username("user@name")  # Invalid character
    
    def test_password_strength(self):
        """Test password strength validation."""
        # Valid passwords
        assert InputValidator.validate_password_strength("SecurePass123") == "SecurePass123"
        assert InputValidator.validate_password_strength("MyP@ssw0rd") == "MyP@ssw0rd"
        
        # Invalid passwords
        with pytest.raises(ValidationError):
            InputValidator.validate_password_strength("short")  # Too short
        with pytest.raises(ValidationError):
            InputValidator.validate_password_strength("alllowercase")  # No uppercase
        with pytest.raises(ValidationError):
            InputValidator.validate_password_strength("ALLUPPERCASE")  # No lowercase
        with pytest.raises(ValidationError):
            InputValidator.validate_password_strength("NoNumbers")  # No numbers
    
    def test_phone_validation(self):
        """Test phone number validation."""
        # Valid phones
        assert InputValidator.validate_phone("+1234567890") == "+1234567890"
        assert InputValidator.validate_phone("1234567890") == "1234567890"
        assert InputValidator.validate_phone("+1 234-567-890") == "+1234567890"
        
        # Invalid phones
        with pytest.raises(ValidationError):
            InputValidator.validate_phone("123")  # Too short
        with pytest.raises(ValidationError):
            InputValidator.validate_phone("abc123")  # Letters
    
    def test_html_sanitization(self):
        """Test HTML sanitization."""
        # Safe HTML
        safe_html = "<p>Hello <strong>world</strong></p>"
        assert InputValidator.sanitize_html(safe_html) == safe_html
        
        # Dangerous HTML
        dangerous = '<script>alert("XSS")</script><p>Hello</p>'
        sanitized = InputValidator.sanitize_html(dangerous)
        assert "<script>" not in sanitized
        assert "<p>Hello</p>" in sanitized
        
        # Event handlers
        dangerous = '<img src="x" onerror="alert(1)">'
        sanitized = InputValidator.sanitize_html(dangerous)
        assert "onerror" not in sanitized
    
    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        assert InputValidator.validate_url("https://example.com") == "https://example.com"
        assert InputValidator.validate_url("http://sub.example.com/path") == "http://sub.example.com/path"
        
        # Invalid URLs
        with pytest.raises(ValidationError):
            InputValidator.validate_url("javascript:alert(1)")
        with pytest.raises(ValidationError):
            InputValidator.validate_url("ftp://example.com")
        with pytest.raises(ValidationError):
            InputValidator.validate_url("not-a-url")


class TestEncryption:
    """Test encryption service."""
    
    def test_string_encryption(self):
        """Test string encryption and decryption."""
        service = EncryptionService()
        
        # Test string
        original = "sensitive data"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        
        assert encrypted != original
        assert decrypted == original
    
    def test_json_encryption(self):
        """Test JSON encryption and decryption."""
        service = EncryptionService()
        
        # Test JSON
        original = {"api_key": "secret", "user_id": 123}
        encrypted = service.encrypt_json(original)
        decrypted = service.decrypt_json(encrypted)
        
        assert encrypted != str(original)
        assert decrypted == original
    
    def test_field_encryption(self):
        """Test field-level encryption."""
        service = EncryptionService()
        
        # Test field
        original = "field value"
        encrypted_field = service.encrypt_field(original)
        
        assert "nonce" in encrypted_field
        assert "ciphertext" in encrypted_field
        assert "version" in encrypted_field
        assert "timestamp" in encrypted_field
        
        decrypted = service.decrypt_field(encrypted_field)
        assert decrypted == original
    
    def test_data_masking(self):
        """Test data masking functions."""
        # Email masking
        assert mask_email("user@example.com") == "us**@example.com"
        assert mask_email("a@b.com") == "****@b.com"
        
        # Phone masking
        assert mask_phone("+1 234 567 8901") == "+1 ****8901"
        assert mask_phone("1234567890") == "****7890"
        
        # API key masking
        assert mask_api_key("agdk_abcdefghijklmnopqrstuvwxyz") == "agdk_abc...wxyz"
        assert mask_api_key("short") == "****"


class TestSQLInjectionPatterns:
    """Test SQL injection detection."""
    
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        from backend.core.middleware.security import SecurityMiddleware
        
        middleware = SecurityMiddleware(None)
        
        # SQL injection attempts
        dangerous_inputs = [
            "1' OR '1'='1",
            "admin'; DROP TABLE users--",
            "1 UNION SELECT * FROM users",
            "' OR 1=1--",
            "admin' AND SLEEP(5)--",
            "'; EXEC xp_cmdshell('dir')--"
        ]
        
        for input_str in dangerous_inputs:
            assert middleware._contains_sql_injection(input_str) == True
        
        # Safe inputs
        safe_inputs = [
            "normal text",
            "user@example.com",
            "John O'Brien",  # Apostrophe in name
            "price > 100 and category = electronics"  # Safe comparison
        ]
        
        for input_str in safe_inputs:
            assert middleware._contains_sql_injection(input_str) == False


class TestXSSPatterns:
    """Test XSS detection."""
    
    def test_xss_detection(self):
        """Test XSS pattern detection."""
        from backend.core.middleware.security import SecurityMiddleware
        
        middleware = SecurityMiddleware(None)
        
        # XSS attempts
        dangerous_inputs = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
            "javascript:alert(1)",
            "<iframe src='evil.com'></iframe>",
            "<object data='evil.swf'></object>"
        ]
        
        for input_str in dangerous_inputs:
            assert middleware._contains_xss(input_str) == True
        
        # Safe inputs
        safe_inputs = [
            "normal text",
            "<p>Hello world</p>",
            "price < 100",
            "user@example.com"
        ]
        
        for input_str in safe_inputs:
            assert middleware._contains_xss(input_str) == False


class TestAPIKeyManager:
    """Test API key management."""
    
    def test_api_key_generation(self):
        """Test API key generation."""
        manager = APIKeyManager()
        
        # Generate key
        key = manager._generate_api_key()
        
        assert key.startswith("agdk_")
        assert len(key) > 40
        
        # Keys should be unique
        key2 = manager._generate_api_key()
        assert key != key2
    
    def test_api_key_hashing(self):
        """Test API key hashing."""
        manager = APIKeyManager()
        
        key = "agdk_test_key"
        hash1 = manager._hash_key(key)
        hash2 = manager._hash_key(key)
        
        # Same key should produce same hash
        assert hash1 == hash2
        
        # Different keys should produce different hashes
        hash3 = manager._hash_key("agdk_different_key")
        assert hash1 != hash3
        
        # Hash should be SHA-512 (128 hex characters)
        assert len(hash1) == 128
        assert all(c in "0123456789abcdef" for c in hash1)


class TestAuditLogger:
    """Test audit logging."""
    
    def test_event_categorization(self):
        """Test audit event categorization."""
        logger = AuditLogger()
        
        assert logger._get_event_category(AuditEventType.LOGIN_SUCCESS) == "authentication"
        assert logger._get_event_category(AuditEventType.USER_CREATED) == "user_management"
        assert logger._get_event_category(AuditEventType.DATA_READ) == "data_access"
        assert logger._get_event_category(AuditEventType.PAYMENT_PROCESSED) == "financial"
        assert logger._get_event_category(AuditEventType.PERMISSION_DENIED) == "security"
    
    def test_critical_events(self):
        """Test critical event identification."""
        logger = AuditLogger()
        
        # Critical events
        assert logger._is_critical_event(AuditEventType.LOGIN_FAILED) == True
        assert logger._is_critical_event(AuditEventType.PERMISSION_DENIED) == True
        assert logger._is_critical_event(AuditEventType.SUSPICIOUS_ACTIVITY) == True
        
        # Non-critical events
        assert logger._is_critical_event(AuditEventType.LOGIN_SUCCESS) == False
        assert logger._is_critical_event(AuditEventType.DATA_READ) == False