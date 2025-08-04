"""Email notification service for sending various types of notifications."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from core.database import get_db
from core.config import settings
from core.logger import get_logger
from services.email_queue import EmailQueueService
from models.user import User
from models.model import Model
from models.financial import Payout
from models.email_preferences import EmailPreferences, EmailPriority

logger = get_logger(__name__)


class EmailNotificationService:
    """Service for sending email notifications."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.queue_service = EmailQueueService(db)
        self.base_url = settings.FRONTEND_URL
        self.support_email = settings.SUPPORT_EMAIL or "support@agency.com"
    
    async def _get_user_preferences(self, user_id: int) -> Optional[EmailPreferences]:
        """Get user email preferences."""
        prefs = await self.db.scalar(
            select(EmailPreferences).where(EmailPreferences.user_id == user_id)
        )
        
        # Create default preferences if not exists
        if not prefs:
            prefs = EmailPreferences(
                user_id=user_id,
                unsubscribe_token=secrets.token_urlsafe(32)
            )
            self.db.add(prefs)
            await self.db.commit()
            await self.db.refresh(prefs)
        
        return prefs
    
    async def _should_send(
        self, 
        user_id: int, 
        notification_type: str
    ) -> tuple[bool, Optional[str]]:
        """Check if notification should be sent to user."""
        prefs = await self._get_user_preferences(user_id)
        
        if not prefs or not prefs.should_send_notification(notification_type):
            return False, None
        
        # Get user email
        user = await self.db.get(User, user_id)
        if not user:
            return False, None
        
        email = prefs.get_email_address() or user.email
        if not email:
            return False, None
        
        return True, email
    
    async def send_welcome_email(self, user: User) -> bool:
        """Send welcome email to new user."""
        try:
            should_send, email = await self._should_send(user.id, 'account_update')
            if not should_send:
                return False
            
            prefs = await self._get_user_preferences(user.id)
            
            template_data = {
                'user_name': user.full_name or user.username,
                'dashboard_url': f"{self.base_url}/dashboard",
                'login_url': f"{self.base_url}/auth/login",
                'docs_url': f"{self.base_url}/docs",
                'support_email': self.support_email,
                'unsubscribe_url': f"{self.base_url}/unsubscribe/{prefs.unsubscribe_token}",
                'preferences_url': f"{self.base_url}/settings/notifications",
            }
            
            await self.queue_service.enqueue(
                to=[email],
                subject="Welcome to Agency Platform!",
                template_id="welcome",
                template_data=template_data,
                priority=EmailPriority.HIGH,
                user_id=user.id,
                related_object_type='user',
                related_object_id=user.id
            )
            
            logger.info(f"Welcome email queued for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False
    
    async def send_model_approval_email(
        self, 
        model: Model, 
        approved: bool, 
        reason: Optional[str] = None,
        admin_notes: Optional[str] = None
    ) -> bool:
        """Send model approval/rejection email."""
        try:
            # Get model user
            user = await self.db.get(User, model.user_id)
            if not user:
                return False
            
            notification_type = 'model_approval'
            should_send, email = await self._should_send(user.id, notification_type)
            if not should_send:
                return False
            
            prefs = await self._get_user_preferences(user.id)
            
            if approved:
                template_id = "model_approved"
                subject = "Your Profile Has Been Approved! 🎉"
            else:
                template_id = "model_rejected"
                subject = "Profile Review Update"
            
            template_data = {
                'model_name': model.stage_name,
                'dashboard_url': f"{self.base_url}/dashboard",
                'support_email': self.support_email,
                'rejection_reason': reason,
                'admin_notes': admin_notes,
                'unsubscribe_url': f"{self.base_url}/unsubscribe/{prefs.unsubscribe_token}",
                'preferences_url': f"{self.base_url}/settings/notifications",
            }
            
            await self.queue_service.enqueue(
                to=[email],
                subject=subject,
                template_id=template_id,
                template_data=template_data,
                priority=EmailPriority.HIGH,
                user_id=user.id,
                related_object_type='model',
                related_object_id=model.id
            )
            
            logger.info(f"Model approval email queued for model {model.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send model approval email: {str(e)}")
            return False
    
    async def send_payout_created_email(self, payout: Payout) -> bool:
        """Send payout created notification."""
        try:
            # Get model and user
            model = await self.db.get(Model, payout.model_id)
            if not model:
                return False
            
            user = await self.db.get(User, model.user_id)
            if not user:
                return False
            
            should_send, email = await self._should_send(user.id, 'payout_created')
            if not should_send:
                return False
            
            prefs = await self._get_user_preferences(user.id)
            
            template_data = {
                'model_name': model.stage_name,
                'payout_number': payout.payout_number,
                'period_start': datetime.fromisoformat(payout.period_start).strftime('%B %d, %Y'),
                'period_end': datetime.fromisoformat(payout.period_end).strftime('%B %d, %Y'),
                'gross_earnings': f"{payout.gross_earnings:,.2f}",
                'commission_amount': f"{payout.commission_amount:,.2f}",
                'adjustments': f"{payout.adjustments:,.2f}",
                'net_amount': f"{payout.net_amount:,.2f}",
                'status': payout.status.value.replace('_', ' ').title(),
                'payment_method': payout.payment_method.value.replace('_', ' ').title(),
                'payout_url': f"{self.base_url}/financial/payouts/{payout.id}",
                'notes': payout.notes,
                'support_email': self.support_email,
                'unsubscribe_url': f"{self.base_url}/unsubscribe/{prefs.unsubscribe_token}",
                'preferences_url': f"{self.base_url}/settings/notifications",
            }
            
            await self.queue_service.enqueue(
                to=[email],
                subject=f"New Payout Created - {payout.payout_number}",
                template_id="payout_created",
                template_data=template_data,
                priority=EmailPriority.NORMAL,
                user_id=user.id,
                related_object_type='payout',
                related_object_id=payout.id
            )
            
            logger.info(f"Payout created email queued for payout {payout.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payout created email: {str(e)}")
            return False
    
    async def send_payout_approved_email(self, payout: Payout) -> bool:
        """Send payout approved notification."""
        try:
            # Get model and user
            model = await self.db.get(Model, payout.model_id)
            if not model:
                return False
            
            user = await self.db.get(User, model.user_id)
            if not user:
                return False
            
            should_send, email = await self._should_send(user.id, 'payout_approved')
            if not should_send:
                return False
            
            prefs = await self._get_user_preferences(user.id)
            
            # Calculate expected date based on payment method
            processing_days = {
                'bank_transfer': 3,
                'paypal': 1,
                'crypto': 1,
                'wire': 5,
                'check': 7
            }.get(payout.payment_method.value, 3)
            
            expected_date = (
                datetime.utcnow() + timedelta(days=processing_days)
            ).strftime('%B %d, %Y')
            
            template_data = {
                'model_name': model.stage_name,
                'payout_number': payout.payout_number,
                'net_amount': f"{payout.net_amount:,.2f}",
                'payment_method': payout.payment_method.value.replace('_', ' ').title(),
                'expected_date': expected_date,
                'processing_days': processing_days,
                'payout_url': f"{self.base_url}/financial/payouts/{payout.id}",
                'support_email': self.support_email,
                'unsubscribe_url': f"{self.base_url}/unsubscribe/{prefs.unsubscribe_token}",
                'preferences_url': f"{self.base_url}/settings/notifications",
            }
            
            await self.queue_service.enqueue(
                to=[email],
                subject=f"Payout Approved! - {payout.payout_number}",
                template_id="payout_approved",
                template_data=template_data,
                priority=EmailPriority.HIGH,
                user_id=user.id,
                related_object_type='payout',
                related_object_id=payout.id
            )
            
            logger.info(f"Payout approved email queued for payout {payout.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payout approved email: {str(e)}")
            return False
    
    async def update_preferences(
        self,
        user_id: int,
        preferences: Dict[str, Any]
    ) -> EmailPreferences:
        """Update user email preferences."""
        prefs = await self._get_user_preferences(user_id)
        
        # Update preferences
        for key, value in preferences.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        
        prefs.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(prefs)
        
        return prefs
    
    async def unsubscribe_user(
        self,
        token: str,
        reason: Optional[str] = None
    ) -> bool:
        """Unsubscribe user using token."""
        try:
            prefs = await self.db.scalar(
                select(EmailPreferences).where(
                    EmailPreferences.unsubscribe_token == token
                )
            )
            
            if not prefs:
                return False
            
            prefs.email_enabled = False
            prefs.unsubscribed_at = datetime.utcnow().isoformat()
            prefs.unsubscribe_reason = reason
            
            await self.db.commit()
            
            logger.info(f"User {prefs.user_id} unsubscribed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {str(e)}")
            return False
    
    async def send_test_email(
        self,
        to: str,
        template_id: str = "welcome"
    ) -> bool:
        """Send test email for debugging."""
        try:
            template_data = {
                'user_name': 'Test User',
                'dashboard_url': f"{self.base_url}/dashboard",
                'login_url': f"{self.base_url}/auth/login",
                'docs_url': f"{self.base_url}/docs",
                'support_email': self.support_email,
                'unsubscribe_url': f"{self.base_url}/unsubscribe/test-token",
                'preferences_url': f"{self.base_url}/settings/notifications",
                'model_name': 'Test Model',
                'payout_number': 'PO-TEST-12345',
                'period_start': 'January 1, 2024',
                'period_end': 'January 31, 2024',
                'gross_earnings': '10,000.00',
                'commission_amount': '2,000.00',
                'adjustments': '0.00',
                'net_amount': '8,000.00',
                'status': 'Pending',
                'payment_method': 'Bank Transfer',
                'payout_url': f"{self.base_url}/financial/payouts/test",
                'expected_date': 'February 5, 2024',
                'processing_days': 3,
            }
            
            await self.queue_service.enqueue(
                to=[to],
                subject=f"Test Email - {template_id}",
                template_id=template_id,
                template_data=template_data,
                priority=EmailPriority.LOW
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send test email: {str(e)}")
            return False