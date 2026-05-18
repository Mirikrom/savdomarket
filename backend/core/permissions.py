from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import RolePermission
from core.tenant import get_membership
from subscriptions.services import has_feature_access


class IsOrganizationMember(BasePermission):
    message = "Organization membership is required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = getattr(request, "membership", None) or get_membership(request)
        if not membership:
            return False
        request.membership = membership
        request.organization = membership.organization
        return True


class RolePermissionRequired(BasePermission):
    message = "You do not have enough permissions for this action."

    def has_permission(self, request, view):
        required = getattr(view, "required_permission", None)
        if not required:
            return True
        membership = getattr(request, "membership", None) or get_membership(request)
        if not membership:
            return False
        if membership.role.code in ("owner", "admin"):
            return True
        return RolePermission.objects.filter(
            role=membership.role, permission_code=required
        ).exists()


def _role_permission_codes(membership) -> set:
    return set(
        RolePermission.objects.filter(role=membership.role).values_list(
            "permission_code", flat=True
        )
    )


class CatalogReadOrManagePermission(BasePermission):
    """GET — catalog.view yoki catalog.manage; o‘zgartirish — faqat catalog.manage."""

    message = "You do not have enough permissions for this action."

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None) or get_membership(request)
        if not membership:
            return False
        if membership.role.code in ("owner", "admin"):
            return True
        codes = _role_permission_codes(membership)
        if request.method in SAFE_METHODS:
            return "catalog.manage" in codes or "catalog.view" in codes
        return "catalog.manage" in codes


class ProductReadOrManagePermission(BasePermission):
    """GET — products.view yoki products.manage; yozuv — faqat products.manage."""

    message = "You do not have enough permissions for this action."

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None) or get_membership(request)
        if not membership:
            return False
        if membership.role.code in ("owner", "admin"):
            return True
        codes = _role_permission_codes(membership)
        if request.method in SAFE_METHODS:
            return "products.manage" in codes or "products.view" in codes
        return "products.manage" in codes


class StockMovementScopePermission(BasePermission):
    """bulk-in — inventory.receive yoki inventory.manage; boshqa — faqat inventory.manage."""

    message = "You do not have enough permissions for this action."

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None) or get_membership(request)
        if not membership:
            return False
        if membership.role.code in ("owner", "admin"):
            return True
        codes = _role_permission_codes(membership)
        if getattr(view, "action", None) == "bulk_in":
            return "inventory.manage" in codes or "inventory.receive" in codes
        return "inventory.manage" in codes


class SubscriptionFeatureRequired(BasePermission):
    message = "Current subscription plan does not include this feature."

    def has_permission(self, request, view):
        feature_code = getattr(view, "required_feature", None)
        if not feature_code:
            return True
        org = getattr(request, "organization", None)
        if not org:
            membership = getattr(request, "membership", None) or get_membership(request)
            if not membership:
                return False
            org = membership.organization
            request.organization = org
        return has_feature_access(org, feature_code)
