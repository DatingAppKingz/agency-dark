"""
Webhook Signature Verification

Provides secure signature verification for various webhook providers.
"""
import hmac
import hashlib
import json
import time
import base64
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class WebhookSignatureVerifier:
    """Verify webhook signatures from various providers"""
    
    @staticmethod
    def verify_hmac_sha256(
        payload: Union[str, bytes, Dict[str, Any]],
        signature: str,
        secret: str,
        prefix: Optional[str] = None
    ) -> bool:
        """
        Verify HMAC-SHA256 signature.
        
        Args:
            payload: The webhook payload (string, bytes, or dict)
            signature: The provided signature
            secret: The webhook secret
            prefix: Optional prefix (e.g., "sha256=")
        
        Returns:
            bool: True if signature is valid
        """
        # Convert payload to bytes
        if isinstance(payload, dict):
            payload_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        elif isinstance(payload, str):
            payload_bytes = payload.encode('utf-8')
        else:
            payload_bytes = payload
        
        # Calculate expected signature
        expected = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Add prefix if specified
        if prefix:
            expected = f"{prefix}{expected}"
        
        # Remove prefix from provided signature if present
        if prefix and signature.startswith(prefix):
            provided = signature
        else:
            provided = signature.split('=')[-1] if '=' in signature else signature
            if prefix:
                provided = f"{prefix}{provided}"
        
        # Constant-time comparison
        return hmac.compare_digest(expected, provided)
    
    @staticmethod
    def verify_stripe(
        payload: Union[str, bytes],
        signature: str,
        secret: str,
        tolerance: int = 300
    ) -> bool:
        """
        Verify Stripe webhook signature.
        
        Args:
            payload: The raw webhook payload
            signature: The Stripe-Signature header
            secret: The webhook endpoint secret
            tolerance: Max age of webhook in seconds
        
        Returns:
            bool: True if signature is valid
        """
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        
        # Parse signature header
        elements = {}
        for element in signature.split(','):
            k, v = element.split('=', 1)
            elements[k] = v
        
        # Check timestamp
        if 't' not in elements:
            return False
        
        timestamp = int(elements['t'])
        if abs(time.time() - timestamp) > tolerance:
            logger.warning(f"Webhook timestamp too old: {timestamp}")
            return False
        
        # Verify signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Check if any signature matches
        signatures = [v for k, v in elements.items() if k.startswith('v')]
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
    
    @staticmethod
    def verify_github(
        payload: Union[str, bytes],
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify GitHub webhook signature.
        
        Args:
            payload: The webhook payload
            signature: The X-Hub-Signature-256 header
            secret: The webhook secret
        
        Returns:
            bool: True if signature is valid
        """
        return WebhookSignatureVerifier.verify_hmac_sha256(
            payload, signature, secret, prefix="sha256="
        )
    
    @staticmethod
    def verify_coinbase(
        payload: Union[str, bytes],
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify Coinbase Commerce webhook signature.
        
        Args:
            payload: The webhook payload
            signature: The X-CC-Webhook-Signature header
            secret: The webhook shared secret
        
        Returns:
            bool: True if signature is valid
        """
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        
        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def verify_paypal(
        payload: Dict[str, Any],
        headers: Dict[str, str],
        cert_url: str,
        webhook_id: str
    ) -> bool:
        """
        Verify PayPal webhook signature.
        
        Note: This is a placeholder. PayPal verification requires:
        1. Fetching the certificate from cert_url
        2. Verifying the certificate chain
        3. Using the certificate to verify the signature
        
        Args:
            payload: The webhook payload
            headers: All webhook headers
            cert_url: The PAYPAL-CERT-URL header
            webhook_id: Your webhook ID
        
        Returns:
            bool: True if signature is valid
        """
        # This would require additional implementation
        logger.warning("PayPal webhook verification not fully implemented")
        return True
    
    @staticmethod
    def verify_twilio(
        url: str,
        params: Dict[str, str],
        signature: str,
        auth_token: str
    ) -> bool:
        """
        Verify Twilio webhook signature.
        
        Args:
            url: The full webhook URL
            params: The request parameters
            signature: The X-Twilio-Signature header
            auth_token: Your Twilio auth token
        
        Returns:
            bool: True if signature is valid
        """
        # Build the string to sign
        s = url
        keys = sorted(params.keys())
        for key in keys:
            s += key + params[key]
        
        # Calculate expected signature
        expected = base64.b64encode(
            hmac.new(
                auth_token.encode('utf-8'),
                s.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def verify_generic(
        payload: Union[str, bytes, Dict[str, Any]],
        signature: str,
        secret: str,
        algorithm: str = "sha256",
        encoding: str = "hex"
    ) -> bool:
        """
        Generic webhook signature verification.
        
        Args:
            payload: The webhook payload
            signature: The provided signature
            secret: The webhook secret
            algorithm: Hash algorithm (sha256, sha1, md5)
            encoding: Signature encoding (hex, base64)
        
        Returns:
            bool: True if signature is valid
        """
        # Convert payload to bytes
        if isinstance(payload, dict):
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        elif isinstance(payload, str):
            payload_bytes = payload.encode('utf-8')
        else:
            payload_bytes = payload
        
        # Get hash algorithm
        hash_func = getattr(hashlib, algorithm, None)
        if not hash_func:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Calculate signature
        mac = hmac.new(secret.encode('utf-8'), payload_bytes, hash_func)
        
        if encoding == "hex":
            expected = mac.hexdigest()
        elif encoding == "base64":
            import base64
            expected = base64.b64encode(mac.digest()).decode('utf-8')
        else:
            raise ValueError(f"Unsupported encoding: {encoding}")
        
        # Remove any prefix from signature
        provided = signature.split('=')[-1] if '=' in signature else signature
        
        return hmac.compare_digest(expected, provided)


# Convenience functions for specific providers
def verify_inflow_webhook(payload: Dict[str, Any], signature: str, secret: str) -> bool:
    """Verify Inflow webhook signature"""
    return WebhookSignatureVerifier.verify_hmac_sha256(payload, signature, secret)


def verify_onlyfans_webhook(payload: Union[str, bytes], signature: str, secret: str) -> bool:
    """Verify OnlyFans webhook signature"""
    return WebhookSignatureVerifier.verify_hmac_sha256(payload, signature, secret, prefix="sha256=")


def verify_stripe_webhook(payload: Union[str, bytes], signature: str, secret: str) -> bool:
    """Verify Stripe webhook signature"""
    return WebhookSignatureVerifier.verify_stripe(payload, signature, secret)


def verify_github_webhook(payload: Union[str, bytes], signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature"""
    return WebhookSignatureVerifier.verify_github(payload, signature, secret)


def verify_coinbase_webhook(payload: Union[str, bytes], signature: str, secret: str) -> bool:
    """Verify Coinbase webhook signature"""
    return WebhookSignatureVerifier.verify_coinbase(payload, signature, secret)