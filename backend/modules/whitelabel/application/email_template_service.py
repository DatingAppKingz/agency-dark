"""
Email template management service.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from jinja2 import Template, Environment, meta, TemplateSyntaxError
import re

from backend.modules.whitelabel.domain.models import (
    EmailTemplate,
    EmailTemplateType
)
from backend.modules.whitelabel.domain.schemas import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTemplatePreview
)
from backend.core.exceptions import NotFoundException, BadRequestException


class EmailTemplateService:
    """Service for managing email templates."""
    
    def __init__(self):
        self.env = Environment(autoescape=True)
        self.default_templates = self._load_default_templates()
    
    async def get_template(
        self,
        template_id: UUID,
        db: AsyncSession
    ) -> EmailTemplateResponse:
        """Get a specific email template."""
        result = await db.execute(
            select(EmailTemplate)
            .filter(EmailTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundException("Email template not found")
        
        return EmailTemplateResponse.from_orm(template)
    
    async def get_agency_templates(
        self,
        agency_id: UUID,
        template_type: Optional[EmailTemplateType] = None,
        language: Optional[str] = None,
        active_only: bool = True,
        db: AsyncSession = None
    ) -> List[EmailTemplateResponse]:
        """Get all email templates for an agency."""
        query = select(EmailTemplate).filter(
            EmailTemplate.agency_id == agency_id
        )
        
        if template_type:
            query = query.filter(EmailTemplate.template_type == template_type.value)
        
        if language:
            query = query.filter(EmailTemplate.language == language)
        
        if active_only:
            query = query.filter(EmailTemplate.is_active == True)
        
        query = query.order_by(
            EmailTemplate.template_type,
            EmailTemplate.language
        )
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        return [EmailTemplateResponse.from_orm(template) for template in templates]
    
    async def create_template(
        self,
        agency_id: UUID,
        template_data: EmailTemplateCreate,
        user_id: UUID,
        db: AsyncSession
    ) -> EmailTemplateResponse:
        """Create a new email template."""
        # Validate template syntax
        variables = await self._validate_template(
            template_data.subject,
            template_data.html_body,
            template_data.text_body
        )
        
        # Check for existing active template
        existing = await db.execute(
            select(EmailTemplate).filter(
                and_(
                    EmailTemplate.agency_id == agency_id,
                    EmailTemplate.template_type == template_data.template_type.value,
                    EmailTemplate.language == template_data.language,
                    EmailTemplate.is_active == True
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise BadRequestException(
                f"Active {template_data.template_type.value} template "
                f"already exists for language {template_data.language}"
            )
        
        # Create template
        template = EmailTemplate(
            agency_id=agency_id,
            template_type=template_data.template_type.value,
            language=template_data.language,
            subject=template_data.subject,
            html_body=template_data.html_body,
            text_body=template_data.text_body or self._html_to_text(template_data.html_body),
            variables=list(variables),
            test_data=template_data.test_data,
            is_active=True,
            updated_by=user_id
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        return EmailTemplateResponse.from_orm(template)
    
    async def update_template(
        self,
        template_id: UUID,
        template_update: EmailTemplateUpdate,
        user_id: UUID,
        db: AsyncSession
    ) -> EmailTemplateResponse:
        """Update an email template."""
        result = await db.execute(
            select(EmailTemplate)
            .filter(EmailTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundException("Email template not found")
        
        # Validate if content is being updated
        if template_update.subject or template_update.html_body or template_update.text_body:
            variables = await self._validate_template(
                template_update.subject or template.subject,
                template_update.html_body or template.html_body,
                template_update.text_body or template.text_body
            )
            template.variables = list(variables)
        
        # Update fields
        update_data = template_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        
        template.updated_by = user_id
        
        await db.commit()
        await db.refresh(template)
        
        return EmailTemplateResponse.from_orm(template)
    
    async def delete_template(
        self,
        template_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete an email template."""
        result = await db.execute(
            select(EmailTemplate)
            .filter(EmailTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundException("Email template not found")
        
        await db.delete(template)
        await db.commit()
        
        return True
    
    async def preview_template(
        self,
        template_id: UUID,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> EmailTemplatePreview:
        """Preview a template with sample data."""
        result = await db.execute(
            select(EmailTemplate)
            .filter(EmailTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundException("Email template not found")
        
        # Use test data if no data provided
        if not data and template.test_data:
            data = template.test_data
        
        try:
            # Render templates
            subject_template = self.env.from_string(template.subject)
            html_template = self.env.from_string(template.html_body)
            text_template = self.env.from_string(template.text_body) if template.text_body else None
            
            rendered_subject = subject_template.render(**data)
            rendered_html = html_template.render(**data)
            rendered_text = text_template.render(**data) if text_template else None
            
            # Check for missing variables
            warnings = []
            for var in template.variables:
                if var not in data:
                    warnings.append(f"Missing variable: {var}")
            
            return EmailTemplatePreview(
                subject=rendered_subject,
                html_body=rendered_html,
                text_body=rendered_text,
                warnings=warnings
            )
            
        except Exception as e:
            raise BadRequestException(f"Template rendering error: {str(e)}")
    
    async def get_or_create_default(
        self,
        agency_id: UUID,
        template_type: EmailTemplateType,
        language: str = "en",
        db: AsyncSession = None
    ) -> EmailTemplateResponse:
        """Get agency template or create from default."""
        # Check for existing template
        result = await db.execute(
            select(EmailTemplate).filter(
                and_(
                    EmailTemplate.agency_id == agency_id,
                    EmailTemplate.template_type == template_type.value,
                    EmailTemplate.language == language,
                    EmailTemplate.is_active == True
                )
            )
        )
        template = result.scalar_one_or_none()
        
        if template:
            return EmailTemplateResponse.from_orm(template)
        
        # Create from default
        default = self.default_templates.get(template_type)
        if not default:
            raise NotFoundException(f"No default template for {template_type.value}")
        
        template = EmailTemplate(
            agency_id=agency_id,
            template_type=template_type.value,
            language=language,
            subject=default["subject"],
            html_body=default["html_body"],
            text_body=default.get("text_body"),
            variables=default["variables"],
            test_data=default.get("test_data"),
            is_active=True,
            is_default=True
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        return EmailTemplateResponse.from_orm(template)
    
    async def _validate_template(
        self,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> set:
        """Validate template syntax and extract variables."""
        variables = set()
        
        try:
            # Parse subject
            subject_ast = self.env.parse(subject)
            variables.update(meta.find_undeclared_variables(subject_ast))
            
            # Parse HTML body
            html_ast = self.env.parse(html_body)
            variables.update(meta.find_undeclared_variables(html_ast))
            
            # Parse text body if provided
            if text_body:
                text_ast = self.env.parse(text_body)
                variables.update(meta.find_undeclared_variables(text_ast))
            
        except TemplateSyntaxError as e:
            raise BadRequestException(f"Invalid template syntax: {str(e)}")
        
        return variables
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Simple HTML to text conversion
        # In production, use a proper HTML parser
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _load_default_templates(self) -> Dict[EmailTemplateType, dict]:
        """Load default email templates."""
        return {
            EmailTemplateType.WELCOME: {
                "subject": "Welcome to {{agency_name}}!",
                "html_body": '''
                <h1>Welcome {{user_name}}!</h1>
                <p>Thank you for joining {{agency_name}}. We're excited to have you on board.</p>
                <p>Get started by <a href="{{login_url}}">logging in to your account</a>.</p>
                <p>Best regards,<br>{{agency_name}} Team</p>
                ''',
                "variables": ["user_name", "agency_name", "login_url"],
                "test_data": {
                    "user_name": "John Doe",
                    "agency_name": "Example Agency",
                    "login_url": "https://example.com/login"
                }
            },
            EmailTemplateType.PASSWORD_RESET: {
                "subject": "Reset your password",
                "html_body": '''
                <h2>Password Reset Request</h2>
                <p>Hi {{user_name}},</p>
                <p>We received a request to reset your password. Click the link below to create a new password:</p>
                <p><a href="{{reset_url}}">Reset Password</a></p>
                <p>This link will expire in {{expiry_hours}} hours.</p>
                <p>If you didn't request this, please ignore this email.</p>
                ''',
                "variables": ["user_name", "reset_url", "expiry_hours"],
                "test_data": {
                    "user_name": "John Doe",
                    "reset_url": "https://example.com/reset?token=abc123",
                    "expiry_hours": 24
                }
            },
            EmailTemplateType.INVOICE: {
                "subject": "Invoice #{{invoice_number}} - {{agency_name}}",
                "html_body": '''
                <h2>Invoice #{{invoice_number}}</h2>
                <p>Date: {{invoice_date}}</p>
                <p>Due Date: {{due_date}}</p>
                <h3>Bill To:</h3>
                <p>{{customer_name}}<br>{{customer_address}}</p>
                <h3>Amount Due: {{total_amount}}</h3>
                <p>Thank you for your business!</p>
                ''',
                "variables": ["invoice_number", "invoice_date", "due_date", "customer_name", "customer_address", "total_amount", "agency_name"],
                "test_data": {
                    "invoice_number": "INV-2024-001",
                    "invoice_date": "2024-01-01",
                    "due_date": "2024-01-31",
                    "customer_name": "John Doe",
                    "customer_address": "123 Main St, City, State 12345",
                    "total_amount": "$1,500.00",
                    "agency_name": "Example Agency"
                }
            },
            EmailTemplateType.NEW_SUBSCRIBER: {
                "subject": "New subscriber on {{model_name}}'s OnlyFans!",
                "html_body": '''
                <h2>Great news!</h2>
                <p>{{model_name}} has a new subscriber:</p>
                <ul>
                    <li>Username: {{subscriber_name}}</li>
                    <li>Subscription type: {{subscription_type}}</li>
                    <li>Price: {{subscription_price}}</li>
                </ul>
                <p>Keep up the great work!</p>
                ''',
                "variables": ["model_name", "subscriber_name", "subscription_type", "subscription_price"],
                "test_data": {
                    "model_name": "Jane Model",
                    "subscriber_name": "fan123",
                    "subscription_type": "Monthly",
                    "subscription_price": "$9.99"
                }
            }
        }