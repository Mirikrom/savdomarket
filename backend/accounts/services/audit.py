"""Small helper to write auth events without scattering ``.objects.create`` calls."""

from __future__ import annotations

from accounts.models import AuthAuditLog, User


def get_client_ip(request) -> str | None:
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_user_agent(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:1000]


def log_event(
    request,
    event: str,
    *,
    user: User | None = None,
    destination: str = "",
    metadata: dict | None = None,
) -> None:
    AuthAuditLog.objects.create(
        user=user,
        event=event,
        destination=destination,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata=metadata or {},
    )
