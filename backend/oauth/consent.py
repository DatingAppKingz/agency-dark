"""
OAuth2 Consent Management System.
Handles user consent for OAuth applications with agency-level scoping.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import secrets
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from fastapi import HTTPException, status

from oauth.models import OAuthConsentRecord, OAuthClient
from oauth.config import oauth_config
from models.user import User

logger = logging.getLogger(__name__)


class ConsentManager:
    """
    Manages OAuth consent records with multi-tenant support.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_consent(
        self,
        user_id: str,
        client_id: str,
        requested_scopes: List[str]
    ) -> Optional[OAuthConsentRecord]:
        """
        Check if user has valid consent for client and scopes.
        
        Args:
            user_id: User ID
            client_id: OAuth client ID
            requested_scopes: List of requested scopes
            
        Returns:
            Valid consent record or None
        """
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.client_id == client_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            )
        )
        consent = result.scalar_one_or_none()
        
        if not consent:
            return None
        
        # Check if consent is still valid
        if not consent.is_valid:
            logger.info(f"Consent expired for user {user_id} and client {client_id}")
            return None
        
        # Check if all requested scopes are covered
        consented_scopes = set(consent.scope.split())
        requested_scopes_set = set(requested_scopes)
        
        if not requested_scopes_set.issubset(consented_scopes):
            missing_scopes = requested_scopes_set - consented_scopes
            logger.info(
                f"Missing consent for scopes {missing_scopes} "
                f"for user {user_id} and client {client_id}"
            )
            return None
        
        return consent
    
    async def save_consent(
        self,
        user_id: str,
        client_id: str,
        scopes: List[str],
        remember: bool = False,
        expires_in_days: Optional[int] = None
    ) -> OAuthConsentRecord:
        """
        Save or update user consent.
        
        Args:
            user_id: User ID
            client_id: OAuth client ID
            scopes: List of consented scopes
            remember: Whether to remember consent long-term
            expires_in_days: Custom expiration in days
            
        Returns:
            Created or updated consent record
        """
        # Check for existing consent
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.client_id == client_id
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        scope_string = " ".join(scopes)
        
        if existing:
            # Update existing consent
            existing.scope = scope_string
            existing.granted_at = datetime.now(timezone.utc)
            existing.revoked_at = None
            
            # Set expiration
            if expires_in_days:
                existing.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            elif remember:
                existing.expires_at = datetime.now(timezone.utc) + timedelta(
                    days=oauth_config.CONSENT_VALIDITY_DAYS
                )
            else:
                # Short-lived consent (1 hour)
                existing.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            
            await self.db.commit()
            logger.info(f"Updated consent for user {user_id} and client {client_id}")
            return existing
        
        # Create new consent
        consent = OAuthConsentRecord(
            user_id=user_id,
            client_id=client_id,
            scope=scope_string,
            granted_at=datetime.now(timezone.utc)
        )
        
        # Set expiration
        if expires_in_days:
            consent.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        elif remember:
            consent.expires_at = datetime.now(timezone.utc) + timedelta(
                days=oauth_config.CONSENT_VALIDITY_DAYS
            )
        else:
            consent.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        self.db.add(consent)
        await self.db.commit()
        
        logger.info(f"Created new consent for user {user_id} and client {client_id}")
        return consent
    
    async def revoke_consent(
        self,
        user_id: str,
        client_id: str
    ) -> bool:
        """
        Revoke user consent for a client.
        
        Args:
            user_id: User ID
            client_id: OAuth client ID
            
        Returns:
            True if consent was revoked, False if not found
        """
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.client_id == client_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            )
        )
        consent = result.scalar_one_or_none()
        
        if not consent:
            return False
        
        consent.revoke()
        await self.db.commit()
        
        logger.info(f"Revoked consent for user {user_id} and client {client_id}")
        return True
    
    async def revoke_all_consents(self, user_id: str) -> int:
        """
        Revoke all consents for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of consents revoked
        """
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            )
        )
        consents = result.scalars().all()
        
        count = 0
        for consent in consents:
            consent.revoke()
            count += 1
        
        if count > 0:
            await self.db.commit()
            logger.info(f"Revoked {count} consents for user {user_id}")
        
        return count
    
    async def get_user_consents(
        self,
        user_id: str,
        include_revoked: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all consents for a user.
        
        Args:
            user_id: User ID
            include_revoked: Whether to include revoked consents
            
        Returns:
            List of consent records with client information
        """
        query = select(
            OAuthConsentRecord,
            OAuthClient
        ).join(
            OAuthClient,
            OAuthConsentRecord.client_id == OAuthClient.client_id
        ).where(
            OAuthConsentRecord.user_id == user_id
        )
        
        if not include_revoked:
            query = query.where(OAuthConsentRecord.revoked_at.is_(None))
        
        query = query.order_by(OAuthConsentRecord.granted_at.desc())
        
        result = await self.db.execute(query)
        rows = result.all()
        
        consents = []
        for consent_record, client in rows:
            consents.append({
                "consent_id": str(consent_record.id),
                "client": {
                    "client_id": client.client_id,
                    "client_name": client.client_name or client.client_id,
                    "agency_id": str(client.agency_id)
                },
                "scope": consent_record.scope,
                "scopes": consent_record.scope.split(),
                "granted_at": consent_record.granted_at.isoformat(),
                "expires_at": consent_record.expires_at.isoformat() if consent_record.expires_at else None,
                "revoked_at": consent_record.revoked_at.isoformat() if consent_record.revoked_at else None,
                "is_valid": consent_record.is_valid,
                "is_expired": (
                    consent_record.expires_at < datetime.now(timezone.utc)
                    if consent_record.expires_at else False
                )
            })
        
        return consents
    
    async def cleanup_expired_consents(self, user_id: Optional[str] = None) -> int:
        """
        Remove expired consent records.
        
        Args:
            user_id: Optional user ID to limit cleanup
            
        Returns:
            Number of records deleted
        """
        query = delete(OAuthConsentRecord).where(
            and_(
                OAuthConsentRecord.expires_at.isnot(None),
                OAuthConsentRecord.expires_at < datetime.now(timezone.utc)
            )
        )
        
        if user_id:
            query = query.where(OAuthConsentRecord.user_id == user_id)
        
        result = await self.db.execute(query)
        await self.db.commit()
        
        deleted = result.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired consent records")
        
        return deleted
    
    async def update_consent_scopes(
        self,
        user_id: str,
        client_id: str,
        add_scopes: Optional[List[str]] = None,
        remove_scopes: Optional[List[str]] = None
    ) -> Optional[OAuthConsentRecord]:
        """
        Update scopes for existing consent.
        
        Args:
            user_id: User ID
            client_id: OAuth client ID
            add_scopes: Scopes to add
            remove_scopes: Scopes to remove
            
        Returns:
            Updated consent record or None if not found
        """
        result = await self.db.execute(
            select(OAuthConsentRecord).where(
                and_(
                    OAuthConsentRecord.user_id == user_id,
                    OAuthConsentRecord.client_id == client_id,
                    OAuthConsentRecord.revoked_at.is_(None)
                )
            )
        )
        consent = result.scalar_one_or_none()
        
        if not consent:
            return None
        
        current_scopes = set(consent.scope.split())
        
        if add_scopes:
            current_scopes.update(add_scopes)
        
        if remove_scopes:
            current_scopes.difference_update(remove_scopes)
        
        consent.scope = " ".join(sorted(current_scopes))
        await self.db.commit()
        
        logger.info(
            f"Updated consent scopes for user {user_id} and client {client_id}: "
            f"added {add_scopes}, removed {remove_scopes}"
        )
        
        return consent


class ConsentUI:
    """
    Generates consent UI templates and handles consent form data.
    """
    
    @staticmethod
    def generate_consent_html(
        client: OAuthClient,
        user: User,
        scopes: List[str],
        state: Optional[str] = None,
        nonce: Optional[str] = None,
        branding: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate HTML for consent screen.
        
        Args:
            client: OAuth client
            user: Current user
            scopes: Requested scopes
            state: OAuth state parameter
            nonce: CSRF nonce
            branding: Optional agency branding
            
        Returns:
            HTML content for consent screen
        """
        # Get scope descriptions
        scope_items = []
        for scope in scopes:
            description = oauth_config.get_scope_description(scope)
            scope_items.append(f'<li class="scope-item">{description}</li>')
        
        scope_list = "\n".join(scope_items)
        
        # Apply branding if provided
        theme_color = branding.get("primary_color", "#4A90E2") if branding else "#4A90E2"
        logo_url = branding.get("logo_url", "") if branding else ""
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Authorization Request - AgencyDark</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                
                .consent-container {{
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 480px;
                    width: 100%;
                    padding: 40px;
                }}
                
                .logo {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                
                .logo img {{
                    max-height: 60px;
                }}
                
                h1 {{
                    color: #333;
                    font-size: 24px;
                    margin-bottom: 10px;
                    text-align: center;
                }}
                
                .client-info {{
                    text-align: center;
                    margin-bottom: 30px;
                    color: #666;
                }}
                
                .client-name {{
                    font-weight: 600;
                    color: {theme_color};
                }}
                
                .user-info {{
                    background: #f8f9fa;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 25px;
                    text-align: center;
                }}
                
                .user-email {{
                    color: #495057;
                    font-size: 14px;
                }}
                
                .scopes-section {{
                    margin-bottom: 30px;
                }}
                
                .scopes-title {{
                    font-size: 16px;
                    color: #333;
                    margin-bottom: 15px;
                    font-weight: 500;
                }}
                
                .scope-list {{
                    list-style: none;
                }}
                
                .scope-item {{
                    padding: 12px 15px;
                    background: #f8f9fa;
                    border-radius: 6px;
                    margin-bottom: 8px;
                    color: #495057;
                    font-size: 14px;
                    position: relative;
                    padding-left: 35px;
                }}
                
                .scope-item:before {{
                    content: "✓";
                    position: absolute;
                    left: 15px;
                    color: #28a745;
                    font-weight: bold;
                }}
                
                .remember-section {{
                    margin-bottom: 25px;
                }}
                
                .remember-checkbox {{
                    display: flex;
                    align-items: center;
                    font-size: 14px;
                    color: #666;
                }}
                
                .remember-checkbox input {{
                    margin-right: 8px;
                }}
                
                .button-group {{
                    display: flex;
                    gap: 10px;
                }}
                
                .btn {{
                    flex: 1;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                
                .btn-allow {{
                    background: {theme_color};
                    color: white;
                }}
                
                .btn-allow:hover {{
                    background: {theme_color}dd;
                    transform: translateY(-1px);
                }}
                
                .btn-deny {{
                    background: #f8f9fa;
                    color: #666;
                }}
                
                .btn-deny:hover {{
                    background: #e9ecef;
                }}
                
                .security-note {{
                    margin-top: 25px;
                    padding-top: 25px;
                    border-top: 1px solid #e9ecef;
                    font-size: 12px;
                    color: #999;
                    text-align: center;
                }}
                
                .security-note a {{
                    color: {theme_color};
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="consent-container">
                {'<div class="logo"><img src="' + logo_url + '" alt="Logo"></div>' if logo_url else ''}
                
                <h1>Authorization Request</h1>
                
                <div class="client-info">
                    <span class="client-name">{client.client_name or client.client_id}</span>
                    <span>is requesting access to your account</span>
                </div>
                
                <div class="user-info">
                    <div class="user-email">Authorizing as: {user.email}</div>
                </div>
                
                <div class="scopes-section">
                    <div class="scopes-title">This application will be able to:</div>
                    <ul class="scope-list">
                        {scope_list}
                    </ul>
                </div>
                
                <form method="post" action="/oauth/authorize" id="consentForm">
                    <input type="hidden" name="client_id" value="{client.client_id}">
                    <input type="hidden" name="scope" value="{' '.join(scopes)}">
                    <input type="hidden" name="state" value="{state or ''}">
                    <input type="hidden" name="nonce" value="{nonce or ''}">
                    
                    <div class="remember-section">
                        <label class="remember-checkbox">
                            <input type="checkbox" name="remember" value="true">
                            Remember this decision for {oauth_config.CONSENT_VALIDITY_DAYS} days
                        </label>
                    </div>
                    
                    <div class="button-group">
                        <button type="submit" name="consent" value="allow" class="btn btn-allow">
                            Allow Access
                        </button>
                        <button type="submit" name="consent" value="deny" class="btn btn-deny">
                            Deny
                        </button>
                    </div>
                </form>
                
                <div class="security-note">
                    By authorizing, you agree to share the information above.
                    <br>
                    <a href="/privacy" target="_blank">Privacy Policy</a> • 
                    <a href="/terms" target="_blank">Terms of Service</a>
                </div>
            </div>
            
            <script>
                // Add CSRF protection if needed
                document.getElementById('consentForm').addEventListener('submit', function(e) {{
                    // Add any client-side validation here
                }});
            </script>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def parse_consent_response(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse consent form submission.
        
        Args:
            form_data: Form data from consent screen
            
        Returns:
            Parsed consent decision
        """
        return {
            "granted": form_data.get("consent") == "allow",
            "remember": form_data.get("remember") == "true",
            "client_id": form_data.get("client_id"),
            "scope": form_data.get("scope", ""),
            "state": form_data.get("state"),
            "nonce": form_data.get("nonce")
        }