"""External API credential validation service."""

import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import httpx
import stripe

from core.config import settings
from core.logger import get_logger
from models.user import User
from models.external_api import ExternalAPICredential, APIProvider
from services.exceptions import APIValidationException, APIConnectionException

logger = get_logger(__name__)


class ExternalAPIValidator:
    """Service for validating external API credentials."""
    
    def __init__(self):
        self.timeout = httpx.Timeout(10.0)
        
    async def validate_credentials(
        self,
        provider: APIProvider,
        credentials: Dict[str, Any],
        user: Optional[User] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate credentials for external API provider.
        
        Args:
            provider: API provider type
            credentials: Credential data
            user: Optional user for context
            
        Returns:
            Tuple of (is_valid, error_message, metadata)
        """
        try:
            if provider == APIProvider.ONLYFANS:
                return await self._validate_onlyfans(credentials)
            elif provider == APIProvider.STRIPE:
                return await self._validate_stripe(credentials)
            elif provider == APIProvider.INFLOW:
                return await self._validate_inflow(credentials)
            else:
                return False, f"Unknown provider: {provider}", None
                
        except Exception as e:
            logger.error(f"Error validating {provider} credentials: {e}")
            return False, str(e), None
    
    async def _validate_onlyfans(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate OnlyFans API credentials."""
        required_fields = ['api_key']
        optional_fields = ['cookie', 'x_bc', 'user_agent']
        
        # Check required fields
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                return False, f"Missing required field: {field}", None
        
        # Prepare headers
        headers = {
            "Accept": "application/json",
            "X-API-Key": credentials['api_key'],
            "User-Agent": credentials.get('user_agent', 'AgencyDark/1.0')
        }
        
        if credentials.get('cookie'):
            headers['Cookie'] = credentials['cookie']
        if credentials.get('x_bc'):
            headers['X-BC'] = credentials['x_bc']
        
        # Test API endpoint
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Try to fetch profile info
                response = await client.get(
                    f"{settings.ONLYFANS_BASE_URL}/api2/v2/users/me",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    metadata = {
                        'username': data.get('username'),
                        'name': data.get('name'),
                        'id': data.get('id'),
                        'verified_at': datetime.utcnow().isoformat()
                    }
                    return True, None, metadata
                elif response.status_code == 401:
                    return False, "Invalid API key or authentication credentials", None
                elif response.status_code == 403:
                    return False, "Access forbidden - check your credentials", None
                else:
                    return False, f"API returned status code: {response.status_code}", None
                    
            except httpx.TimeoutException:
                return False, "Connection timeout - OnlyFans API may be unavailable", None
            except httpx.ConnectError:
                return False, "Failed to connect to OnlyFans API", None
            except Exception as e:
                return False, f"Unexpected error: {str(e)}", None
    
    async def _validate_stripe(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate Stripe API credentials."""
        required_fields = ['secret_key']
        optional_fields = ['webhook_secret', 'publishable_key']
        
        # Check required fields
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                return False, f"Missing required field: {field}", None
        
        # Check if it's a valid Stripe key format
        secret_key = credentials['secret_key']
        if not (secret_key.startswith('sk_test_') or secret_key.startswith('sk_live_')):
            return False, "Invalid Stripe secret key format", None
        
        # Test the key
        try:
            stripe.api_key = secret_key
            
            # Try to retrieve account info
            account = stripe.Account.retrieve()
            
            metadata = {
                'account_id': account.id,
                'business_name': account.business_profile.name if account.business_profile else None,
                'country': account.country,
                'charges_enabled': account.charges_enabled,
                'payouts_enabled': account.payouts_enabled,
                'is_live': secret_key.startswith('sk_live_'),
                'verified_at': datetime.utcnow().isoformat()
            }
            
            # Test webhook secret if provided
            if credentials.get('webhook_secret'):
                webhook_secret = credentials['webhook_secret']
                if not webhook_secret.startswith('whsec_'):
                    return False, "Invalid webhook secret format", metadata
                metadata['webhook_configured'] = True
            
            return True, None, metadata
            
        except stripe.error.AuthenticationError:
            return False, "Invalid Stripe API key", None
        except stripe.error.PermissionError:
            return False, "Insufficient permissions for this Stripe API key", None
        except stripe.error.APIConnectionError:
            return False, "Failed to connect to Stripe API", None
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", None
    
    async def _validate_inflow(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate Inflow API credentials."""
        required_fields = ['api_key', 'agency_id']
        optional_fields = ['webhook_secret']
        
        # Check required fields
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                return False, f"Missing required field: {field}", None
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {credentials['api_key']}",
            "X-Agency-ID": credentials['agency_id'],
            "Accept": "application/json"
        }
        
        # Test API endpoint
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Try to fetch agency info
                response = await client.get(
                    f"{settings.INFLOW_BASE_URL}/api/v1/agency",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    metadata = {
                        'agency_name': data.get('name'),
                        'agency_id': data.get('id'),
                        'plan': data.get('plan'),
                        'features': data.get('features', []),
                        'verified_at': datetime.utcnow().isoformat()
                    }
                    return True, None, metadata
                elif response.status_code == 401:
                    return False, "Invalid API key", None
                elif response.status_code == 403:
                    return False, "Access forbidden - check your agency ID", None
                elif response.status_code == 404:
                    return False, "Agency not found", None
                else:
                    return False, f"API returned status code: {response.status_code}", None
                    
            except httpx.TimeoutException:
                return False, "Connection timeout - Inflow API may be unavailable", None
            except httpx.ConnectError:
                return False, "Failed to connect to Inflow API", None
            except Exception as e:
                return False, f"Unexpected error: {str(e)}", None
    
    async def validate_webhook_signature(
        self,
        provider: APIProvider,
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Validate webhook signature from external API.
        
        Args:
            provider: API provider type
            payload: Raw webhook payload
            signature: Signature from headers
            secret: Webhook secret
            
        Returns:
            True if signature is valid
        """
        try:
            if provider == APIProvider.STRIPE:
                return self._validate_stripe_webhook_signature(payload, signature, secret)
            elif provider == APIProvider.ONLYFANS:
                return self._validate_onlyfans_webhook_signature(payload, signature, secret)
            elif provider == APIProvider.INFLOW:
                return self._validate_inflow_webhook_signature(payload, signature, secret)
            else:
                logger.warning(f"Unknown provider for webhook validation: {provider}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating webhook signature for {provider}: {e}")
            return False
    
    def _validate_stripe_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Validate Stripe webhook signature."""
        try:
            stripe.Webhook.construct_event(payload, signature, secret)
            return True
        except stripe.error.SignatureVerificationError:
            return False
    
    def _validate_onlyfans_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Validate OnlyFans webhook signature."""
        import hmac
        import hashlib
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def _validate_inflow_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Validate Inflow webhook signature."""
        import hmac
        import hashlib
        
        # Inflow uses SHA-256 HMAC
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Inflow prefixes with "sha256="
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def test_all_credentials(self, user: User) -> Dict[str, Dict[str, Any]]:
        """
        Test all stored credentials for a user.
        
        Args:
            user: User to test credentials for
            
        Returns:
            Dictionary with test results for each provider
        """
        results = {}
        
        # Get all credentials for user
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        from core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            stmt = select(ExternalAPICredential).where(
                ExternalAPICredential.user_id == user.id,
                ExternalAPICredential.is_active == True
            )
            result = await db.execute(stmt)
            credentials = result.scalars().all()
            
            for cred in credentials:
                is_valid, error, metadata = await self.validate_credentials(
                    cred.provider,
                    cred.credentials,
                    user
                )
                
                results[cred.provider.value] = {
                    'credential_id': str(cred.id),
                    'is_valid': is_valid,
                    'error': error,
                    'metadata': metadata,
                    'last_validated': datetime.utcnow().isoformat()
                }
                
                # Update credential status
                cred.is_valid = is_valid
                cred.last_validated = datetime.utcnow()
                if metadata:
                    cred.metadata = {**cred.metadata, **metadata} if cred.metadata else metadata
                
            await db.commit()
        
        return results


# Singleton instance
_validator_instance = None


def get_external_api_validator() -> ExternalAPIValidator:
    """Get singleton instance of external API validator."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ExternalAPIValidator()
    return _validator_instance