"""Email delivery providers."""
from services.email.factory import get_email_provider
from services.email.types import EmailDeliveryResult, EmailProvider

__all__ = ["EmailDeliveryResult", "EmailProvider", "get_email_provider"]
