"""Email service for sending transactional emails."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
from functools import lru_cache
import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from pydantic import BaseModel, EmailStr

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class EmailConfig(BaseModel):
    """Email configuration."""
    provider: str = "sendgrid"  # sendgrid, smtp
    from_email: str = "noreply@agency.com"
    from_name: str = "Agency Platform"
    
    # SendGrid settings
    sendgrid_api_key: Optional[str] = None
    
    # SMTP settings
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    
    # General settings
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    batch_size: int = 100
    rate_limit: int = 100  # per minute


class EmailMessage(BaseModel):
    """Email message model."""
    to: List[EmailStr]
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    reply_to: Optional[EmailStr] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None


class EmailService:
    """Email service for sending emails."""
    
    def __init__(self):
        self.config = self._load_config()
        self.template_env = self._setup_templates()
        self._client = None
    
    def _load_config(self) -> EmailConfig:
        """Load email configuration from environment."""
        return EmailConfig(
            provider=os.getenv("EMAIL_PROVIDER", "sendgrid"),
            from_email=os.getenv("EMAIL_FROM", "noreply@agency.com"),
            from_name=os.getenv("EMAIL_FROM_NAME", "Agency Platform"),
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY"),
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        )
    
    def _setup_templates(self) -> Environment:
        """Setup Jinja2 template environment."""
        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "templates", 
            "emails"
        )
        
        return Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    @property
    def client(self):
        """Get email client based on provider."""
        if self._client is None:
            if self.config.provider == "sendgrid":
                if not self.config.sendgrid_api_key:
                    raise ValueError("SendGrid API key not configured")
                self._client = sendgrid.SendGridAPIClient(
                    api_key=self.config.sendgrid_api_key
                )
            else:
                # Default to SMTP
                if not self.config.smtp_host:
                    raise ValueError("SMTP host not configured")
                self._client = aiosmtplib.SMTP(
                    hostname=self.config.smtp_host,
                    port=self.config.smtp_port,
                    use_tls=self.config.smtp_use_tls,
                    username=self.config.smtp_username,
                    password=self.config.smtp_password,
                )
        return self._client
    
    async def send(self, message: EmailMessage) -> Dict[str, Any]:
        """Send an email message."""
        try:
            # Render template if specified
            if message.template_id:
                html_content, text_content = await self._render_template(
                    message.template_id,
                    message.template_data or {}
                )
                message.html_content = html_content
                message.text_content = text_content
            
            # Send based on provider
            if self.config.provider == "sendgrid":
                return await self._send_sendgrid(message)
            else:
                return await self._send_smtp(message)
                
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise
    
    async def _render_template(
        self, 
        template_id: str, 
        data: Dict[str, Any]
    ) -> tuple[str, str]:
        """Render email template."""
        try:
            # Add default template data
            data.update({
                'current_year': datetime.utcnow().year,
                'company_name': self.config.from_name,
                'base_url': settings.FRONTEND_URL,
            })
            
            # Render HTML template
            html_template = self.template_env.get_template(f"{template_id}.html")
            html_content = html_template.render(**data)
            
            # Try to render text template, fall back to HTML strip
            try:
                text_template = self.template_env.get_template(f"{template_id}.txt")
                text_content = text_template.render(**data)
            except:
                # Simple HTML to text conversion
                import re
                text_content = re.sub('<[^<]+?>', '', html_content)
            
            return html_content, text_content
            
        except Exception as e:
            logger.error(f"Failed to render template {template_id}: {str(e)}")
            raise
    
    async def _send_sendgrid(self, message: EmailMessage) -> Dict[str, Any]:
        """Send email using SendGrid."""
        try:
            # Create message
            mail = Mail()
            mail.from_email = Email(self.config.from_email, self.config.from_name)
            
            # Add recipients
            for email in message.to:
                mail.add_to(To(email))
            
            # Set content
            mail.subject = message.subject
            if message.text_content:
                mail.add_content(Content("text/plain", message.text_content))
            if message.html_content:
                mail.add_content(Content("text/html", message.html_content))
            
            # Add CC/BCC
            if message.cc:
                for email in message.cc:
                    mail.add_cc(email)
            if message.bcc:
                for email in message.bcc:
                    mail.add_bcc(email)
            
            # Set reply-to
            if message.reply_to:
                mail.reply_to = message.reply_to
            
            # Send
            response = self.client.send(mail)
            
            return {
                'success': True,
                'message_id': response.headers.get('X-Message-Id'),
                'status_code': response.status_code,
            }
            
        except Exception as e:
            logger.error(f"SendGrid error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _send_smtp(self, message: EmailMessage) -> Dict[str, Any]:
        """Send email using SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message.subject
            msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
            msg['To'] = ', '.join(message.to)
            
            if message.cc:
                msg['Cc'] = ', '.join(message.cc)
            if message.reply_to:
                msg['Reply-To'] = message.reply_to
            
            # Add content
            if message.text_content:
                msg.attach(MIMEText(message.text_content, 'plain'))
            if message.html_content:
                msg.attach(MIMEText(message.html_content, 'html'))
            
            # Connect and send
            async with self.client:
                await self.client.send_message(msg)
            
            return {
                'success': True,
                'message_id': msg['Message-ID'],
            }
            
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_bulk(
        self, 
        messages: List[EmailMessage],
        batch_delay: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Send multiple emails in batches."""
        results = []
        
        for i in range(0, len(messages), self.config.batch_size):
            batch = messages[i:i + self.config.batch_size]
            
            # Send batch concurrently
            batch_results = await asyncio.gather(*[
                self.send(msg) for msg in batch
            ], return_exceptions=True)
            
            results.extend(batch_results)
            
            # Rate limiting
            if i + self.config.batch_size < len(messages):
                await asyncio.sleep(batch_delay)
        
        return results


# Singleton instance
_email_service = None


def get_email_service() -> EmailService:
    """Get email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


# Convenience functions
async def send_email(
    to: List[str],
    subject: str,
    template_id: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Send an email."""
    service = get_email_service()
    
    message = EmailMessage(
        to=to,
        subject=subject,
        template_id=template_id,
        template_data=template_data,
        html_content=html_content,
        text_content=text_content,
        **kwargs
    )
    
    return await service.send(message)