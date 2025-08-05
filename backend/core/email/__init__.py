"""
Email Service Module

Handles sending authentication and notification emails.
"""
from .email_service import email_service, EmailMessage, get_email_service

__all__ = ["email_service", "EmailMessage", "get_email_service"]