"""Tashkilotni provider paneldan butunlay o‘chirish (qayta ro‘yxatdan o‘tish uchun)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import OrganizationUser, Role
from catalog.models import Category, Product
from inventory.models import ProductBatch, StockMovement
from sales.models import DebtPayment, Sale
from shops.models import Organization
from subscriptions.models import Subscription

User = get_user_model()


@transaction.atomic
def purge_organization(organization: Organization) -> dict:
    """Do‘kon va unga bog‘liq barcha ma’lumotlarni o‘chiradi.

    Tashkilot a’zolari (superuserdan tashqari) boshqa do‘konda bo‘lmasa,
    User yozuvi ham o‘chiriladi — shu telefon bilan qayta ro‘yxatdan o‘tish mumkin.
    """
    org_id = organization.pk
    user_ids = list(
        OrganizationUser.objects.filter(organization_id=org_id)
        .values_list("user_id", flat=True)
        .distinct()
    )

    DebtPayment.objects.filter(organization_id=org_id).delete()
    Sale.objects.filter(organization_id=org_id).delete()
    StockMovement.objects.filter(organization_id=org_id).delete()
    ProductBatch.objects.filter(product__organization_id=org_id).delete()
    Product.objects.filter(organization_id=org_id).delete()
    Category.objects.filter(organization_id=org_id).delete()
    Subscription.objects.filter(organization_id=org_id).delete()
    OrganizationUser.objects.filter(organization_id=org_id).delete()
    Role.objects.filter(organization_id=org_id).delete()

    organization.delete()

    users_removed = 0
    for uid in user_ids:
        user = User.objects.filter(pk=uid).first()
        if not user or user.is_superuser:
            continue
        if OrganizationUser.objects.filter(user_id=uid).exists():
            continue
        user.delete()
        users_removed += 1

    return {
        "organization_id": org_id,
        "users_removed": users_removed,
    }
