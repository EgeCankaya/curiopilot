"""Email configuration and test API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from curiopilot.api.deps import get_config

router = APIRouter(tags=["email"])
log = logging.getLogger(__name__)


class TestEmailRequest(BaseModel):
    password: str
    recipient_email: str | None = None


class TestEmailResponse(BaseModel):
    status: str
    detail: str = ""


@router.post("/email/test", response_model=TestEmailResponse)
async def send_test_email(body: TestEmailRequest, config=Depends(get_config)):
    """Send a test email using current config and the provided password."""
    from curiopilot.email_digest import send_briefing_email

    email_cfg = config.email
    if body.recipient_email:
        email_cfg = email_cfg.model_copy(update={"recipient_email": body.recipient_email})

    test_markdown = (
        "# CurioPilot Test Email\n\n"
        "This is a test email from CurioPilot. "
        "If you can read this, your email configuration is working correctly.\n\n"
        f"- **SMTP Host**: {email_cfg.smtp_host}\n"
        f"- **Sender**: {email_cfg.sender_email}\n"
        f"- **Recipient**: {email_cfg.recipient_email}\n"
    )

    try:
        await send_briefing_email(
            email_cfg,
            test_markdown,
            "test",
            password_override=body.password,
        )
        return TestEmailResponse(
            status="sent",
            detail=f"Test email sent to {email_cfg.recipient_email}",
        )
    except Exception as exc:
        log.warning("Test email failed: %s", exc)
        return TestEmailResponse(status="failed", detail=str(exc))
