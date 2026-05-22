"""Tashkilot rollari: faqat owner (egasi) va seller (sotuvchi).

Platforma admini — Django ``is_superuser`` (provider panel), ``Role.code='admin'`` emas.
"""

from accounts.models import Role

# Tashkilotga taklif qilinadigan yagona xodim roli
STAFF_ROLE_CODE = Role.RoleCode.SELLER

# Tizimda saqlanadi, lekin yangi tayinlashda ishlatilmaydi
LEGACY_ROLE_CODES = (
    Role.RoleCode.ADMIN,
    Role.RoleCode.MODERATOR,
    Role.RoleCode.CASHIER,
)

ACTIVE_SYSTEM_ROLE_CODES = (
    Role.RoleCode.OWNER,
    Role.RoleCode.SELLER,
)

SELLER_PERMISSIONS = (
    "sales.manage",
    "sales.view",
    "catalog.manage",
    "catalog.view",
    "products.manage",
    "products.view",
    "inventory.receive",
)

OWNER_PERMISSIONS = (
    "users.manage",
    "roles.manage",
    "organization_users.manage",
    "branches.manage",
    "subscriptions.manage",
    "subscriptions.view_invoices",
    "catalog.manage",
    "products.manage",
    "inventory.manage",
    "sales.manage",
    "sales.view",
)


def is_staff_assignable_role(code: str) -> bool:
    return code == STAFF_ROLE_CODE


def is_valid_member_role_code(code: str) -> bool:
    return code in (Role.RoleCode.OWNER, Role.RoleCode.SELLER)
