"""Helpers to bootstrap a new tenant when a user finishes registration."""

from __future__ import annotations

import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import OrganizationUser, Role, User
from shops.models import Branch, Organization
from subscriptions.models import Plan, Subscription


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug or "shop"


def _unique_slug(base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    counter = 2
    while Organization.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _owner_role_for(organization: Organization) -> Role:
    """Return (or create) the owner role bound to this specific organization.

    The system-wide owner role (``organization=None``) is the template; we
    materialize a per-organization copy so per-tenant permission edits don't
    leak across tenants.
    """
    system_owner = Role.objects.filter(
        organization__isnull=True, code=Role.RoleCode.OWNER, is_system=True
    ).first()
    role, created = Role.objects.get_or_create(
        organization=organization,
        code=Role.RoleCode.OWNER,
        defaults={
            "name": "Owner",
            "description": "Organization owner",
            "is_system": True,
            "is_active": True,
        },
    )
    if created and system_owner is not None:
        from accounts.models import RolePermission

        permissions = list(system_owner.permissions.values_list("permission_code", flat=True))
        RolePermission.objects.bulk_create(
            [RolePermission(role=role, permission_code=p) for p in permissions]
        )
    return role


def _ensure_trial_subscription(organization: Organization) -> Subscription | None:
    """Yangi tashkilotga 14-kunlik Lite trial sub berish.

    Plan `lite` mavjud bo'lmasa, hech narsa yaratmaydi (best-effort).
    """
    plan = Plan.objects.filter(code=Plan.PlanCode.LITE, is_active=True).first()
    if plan is None:
        return None
    now = timezone.now()
    sub, _ = Subscription.objects.get_or_create(
        organization=organization,
        status=Subscription.Status.ACTIVE,
        defaults={
            "plan": plan,
            "starts_at": now,
            "ends_at": now + timedelta(days=14),
            "auto_renew": False,
        },
    )
    return sub


@transaction.atomic
def bootstrap_owner(
    *,
    phone: str,
    password: str,
    full_name: str,
    email: str = "",
    preferred_language: str = User.LanguageChoices.UZ,
    organization_name: str | None = None,
) -> tuple[User, Organization, OrganizationUser]:
    """Create User + Organization + Branch + OrganizationUser(owner) + Trial Sub atomically."""
    organization = Organization.objects.create(
        name=organization_name or full_name or phone,
        slug=_unique_slug(organization_name or full_name or phone),
        phone=phone,
        is_active=True,
    )
    main_branch = Branch.objects.create(
        organization=organization,
        name="Asosiy filial",
        is_main=True,
    )
    owner_role = _owner_role_for(organization)

    user = User(
        phone=phone,
        full_name=full_name,
        email=email or "",
        preferred_language=preferred_language,
        phone_verified_at=timezone.now(),
        is_active=True,
    )
    user.set_password(password)
    user.last_password_changed_at = timezone.now()
    user.save()

    membership = OrganizationUser.objects.create(
        organization=organization,
        user=user,
        role=owner_role,
        branch=main_branch,
        status=OrganizationUser.MembershipStatus.ACTIVE,
    )

    _ensure_trial_subscription(organization)
    return user, organization, membership
