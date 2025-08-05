"""
Email Service for Authentication

Handles sending authentication-related emails like password reset and verification.
"""
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from pydantic import BaseModel, EmailStr

from core.config import settings

logger = logging.getLogger(__name__)


class EmailMessage(BaseModel):
    """Email message model."""
    to: List[EmailStr]
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    subject: str
    body: str
    html_body: Optional[str] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    headers: Optional[Dict[str, str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class EmailService:
    """Service for sending authentication emails."""
    
    def __init__(self):
        # Initialize Jinja2 for email templates
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Email configuration
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_use_tls = settings.SMTP_USE_TLS
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME
        self.app_name = "AgencyDark"
        self.app_url = settings.FRONTEND_URL
    
    async def send_verification_email(
        self,
        to_email: str,
        user_name: str,
        verification_token: str
    ) -> bool:
        """Send email verification link."""
        try:
            verification_url = f"{self.app_url}/auth/verify-email/{verification_token}"
            
            # Render email template
            template = self.env.get_template("email_verification.html")
            html_content = template.render(
                user_name=user_name,
                verification_url=verification_url,
                app_name=self.app_name,
                app_url=self.app_url,
                expires_in_hours=24
            )
            
            # Plain text version
            text_content = f"""
Hi {user_name},

Welcome to {self.app_name}! Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create an account, please ignore this email.

Best regards,
The {self.app_name} Team
"""
            
            subject = f"Verify your email for {self.app_name}"
            
            return await self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            return False
    
    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_token: str
    ) -> bool:
        """Send password reset link."""
        try:
            reset_url = f"{self.app_url}/auth/reset-password/{reset_token}"
            
            # Render email template
            template = self.env.get_template("password_reset.html")
            html_content = template.render(
                user_name=user_name,
                reset_url=reset_url,
                app_name=self.app_name,
                app_url=self.app_url,
                expires_in_minutes=60
            )
            
            # Plain text version
            text_content = f"""
Hi {user_name},

You requested to reset your password for {self.app_name}. Click the link below to set a new password:

{reset_url}

This link will expire in 60 minutes.

If you didn't request this, please ignore this email and your password will remain unchanged.

Best regards,
The {self.app_name} Team
"""
            
            subject = f"Reset your password for {self.app_name}"
            
            return await self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            return False
    
    async def send_password_changed_email(
        self,
        to_email: str,
        user_name: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Send password changed notification."""
        try:
            # Render email template
            template = self.env.get_template("password_changed.html")
            html_content = template.render(
                user_name=user_name,
                app_name=self.app_name,
                app_url=self.app_url,
                changed_at=datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
                ip_address=ip_address or "Unknown",
                user_agent=user_agent or "Unknown device"
            )
            
            # Plain text version
            text_content = f"""
Hi {user_name},

Your password for {self.app_name} was successfully changed.

Changed at: {datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")}
IP Address: {ip_address or "Unknown"}
Device: {user_agent or "Unknown device"}

If you didn't make this change, please contact our support team immediately.

Best regards,
The {self.app_name} Team
"""
            
            subject = f"Your {self.app_name} password was changed"
            
            return await self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send password changed email: {e}")
            return False
    
    async def send_login_alert_email(
        self,
        to_email: str,
        user_name: str,
        ip_address: str,
        user_agent: str,
        location: Optional[str] = None
    ) -> bool:
        """Send alert for login from new device/location."""
        try:
            # Parse user agent for friendly display
            from user_agents import parse
            ua = parse(user_agent)
            device_info = f"{ua.browser.family} on {ua.os.family}"
            
            # Render email template
            template = self.env.get_template("login_alert.html")
            html_content = template.render(
                user_name=user_name,
                app_name=self.app_name,
                app_url=self.app_url,
                login_at=datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
                ip_address=ip_address,
                location=location or "Unknown location",
                device_info=device_info
            )
            
            # Plain text version
            text_content = f"""
Hi {user_name},

A new login to your {self.app_name} account was detected:

Time: {datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")}
IP Address: {ip_address}
Location: {location or "Unknown location"}
Device: {device_info}

If this was you, you can safely ignore this email. If you didn't log in, please secure your account immediately.

Best regards,
The {self.app_name} Team
"""
            
            subject = f"New login to your {self.app_name} account"
            
            return await self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send login alert email: {e}")
            return False
    
    async def send_account_locked_email(
        self,
        to_email: str,
        user_name: str,
        unlock_time: datetime
    ) -> bool:
        """Send account locked notification."""
        try:
            # Render email template
            template = self.env.get_template("account_locked.html")
            html_content = template.render(
                user_name=user_name,
                app_name=self.app_name,
                app_url=self.app_url,
                unlock_time=unlock_time.strftime("%B %d, %Y at %I:%M %p UTC"),
                support_url=f"{self.app_url}/support"
            )
            
            # Plain text version
            text_content = f"""
Hi {user_name},

Your {self.app_name} account has been temporarily locked due to multiple failed login attempts.

Your account will be automatically unlocked at: {unlock_time.strftime("%B %d, %Y at %I:%M %p UTC")}

If you believe this is a mistake or need immediate access, please contact our support team.

Best regards,
The {self.app_name} Team
"""
            
            subject = f"Your {self.app_name} account has been locked"
            
            return await self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send account locked email: {e}")
            return False
    
    async def send_email(self, email_message: EmailMessage) -> bool:
        """Send email from EmailMessage object."""
        try:
            # Convert to MIME message
            if email_message.html_body:
                message = MIMEMultipart('alternative')
                text_part = MIMEText(email_message.body, 'plain')
                html_part = MIMEText(email_message.html_body, 'html')
                message.attach(text_part)
                message.attach(html_part)
            else:
                message = MIMEText(email_message.body, 'plain')
            
            # Set headers
            message['Subject'] = email_message.subject
            message['From'] = f"{email_message.from_name or self.from_name} <{email_message.from_email or self.from_email}>"
            message['To'] = ', '.join(email_message.to)
            
            if email_message.cc:
                message['Cc'] = ', '.join(email_message.cc)
            if email_message.bcc:
                message['Bcc'] = ', '.join(email_message.bcc)
            if email_message.reply_to:
                message['Reply-To'] = email_message.reply_to
            
            # Add custom headers
            if email_message.headers:
                for key, value in email_message.headers.items():
                    message[key] = value
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=self.smtp_use_tls
            ) as smtp:
                if self.smtp_username and self.smtp_password:
                    await smtp.login(self.smtp_username, self.smtp_password)
                
                await smtp.send_message(message)
            
            logger.info(f"Email sent successfully to {', '.join(email_message.to)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email using SMTP."""
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email
            if settings.ENVIRONMENT == "development":
                # In development, just log the email
                logger.info(f"Development mode - Would send email to {to_email}")
                logger.debug(f"Subject: {subject}")
                logger.debug(f"Content: {text_content[:200]}...")
                return True
            
            # Send via SMTP
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=self.smtp_use_tls
            ) as smtp:
                if self.smtp_username and self.smtp_password:
                    await smtp.login(self.smtp_username, self.smtp_password)
                
                await smtp.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


# Global instance
email_service = EmailService()


def get_email_service() -> EmailService:
    """Get email service instance."""
    return email_service