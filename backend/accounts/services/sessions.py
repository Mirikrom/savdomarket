"""Track refresh tokens as ``UserSession`` rows so they can be inspected and
revoked individually (per-device logout)."""

from __future__ import annotations

from datetime import datetime, timezone as _tz

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken, Token
from rest_framework_simplejwt.exceptions import TokenError

from accounts.models import User, UserSession


def _refresh_expires_at(refresh: RefreshToken) -> datetime:
    exp = refresh.payload.get("exp")
    if exp is None:
        return timezone.now()
    return datetime.fromtimestamp(int(exp), tz=_tz.utc)


def issue_tokens_for_user(user: User, request=None) -> dict:
    """Issue an access+refresh pair and create a tracking ``UserSession``."""
    refresh = RefreshToken.for_user(user)
    jti = refresh.payload.get("jti")
    from accounts.services.audit import get_client_ip, get_user_agent

    UserSession.objects.create(
        user=user,
        refresh_jti=jti,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        device_name=(get_user_agent(request) or "")[:255],
        last_used_at=timezone.now(),
        expires_at=_refresh_expires_at(refresh),
    )
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def revoke_refresh_token(refresh_token_str: str) -> UserSession | None:
    """Blacklist the refresh token (via SimpleJWT) and mark its session revoked."""
    try:
        token: Token = RefreshToken(refresh_token_str)
    except TokenError:
        return None
    jti = token.payload.get("jti")
    try:
        token.blacklist()
    except Exception:  # noqa: BLE001
        pass
    session = UserSession.objects.filter(refresh_jti=jti).first()
    if session:
        session.revoke()
    return session


def revoke_all_sessions(user: User, *, except_jti: str | None = None) -> int:
    sessions = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    if except_jti:
        sessions = sessions.exclude(refresh_jti=except_jti)
    count = 0
    for session in sessions:
        session.revoke()
        count += 1
    return count
