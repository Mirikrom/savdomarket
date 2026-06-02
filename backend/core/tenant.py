from accounts.models import OrganizationUser, Role


def active_organization_memberships(user):
    """Faqat faol tashkilot va faol a'zoliklar (o'chirilgan do'konlar chiqariladi)."""
    return OrganizationUser.objects.select_related("role", "organization", "branch").filter(
        user=user,
        is_active=True,
        deleted_at__isnull=True,
        status=OrganizationUser.MembershipStatus.ACTIVE,
        organization__deleted_at__isnull=True,
        organization__is_active=True,
    )


def get_request_organization_id(request):
    # DRF Request has `query_params`; bare WSGIRequest only has `GET`.
    query_params = getattr(request, "query_params", None) or getattr(request, "GET", None) or {}
    raw_org_id = request.headers.get("X-Organization-Id") or query_params.get("organization_id")
    if not raw_org_id:
        return None
    try:
        return int(raw_org_id)
    except (TypeError, ValueError):
        return None


def get_owner_membership_for_organization(organization_id: int):
    """Tashkilot owner a'zoligi — superuser qo'llab-quvvatlash rejimi uchun."""
    return (
        OrganizationUser.objects.select_related("role", "organization", "branch", "user")
        .filter(
            organization_id=organization_id,
            organization__deleted_at__isnull=True,
            organization__is_active=True,
            role__code=Role.RoleCode.OWNER,
            is_active=True,
            deleted_at__isnull=True,
            status=OrganizationUser.MembershipStatus.ACTIVE,
        )
        .order_by("id")
        .first()
    )


def get_membership(request):
    """Faol a'zolik — X-Organization-Id bo'yicha; yo'q bo'lsa birinchi a'zolik (accounts/me bilan bir xil).

    Superuser + X-Organization-Id: tanlangan do'kon owner huquqlari (o'z JWT bilan).
    """
    if not request.user.is_authenticated:
        return None

    org_id = get_request_organization_id(request)
    if request.user.is_superuser and org_id:
        return get_owner_membership_for_organization(org_id)

    qs = active_organization_memberships(request.user)
    if org_id:
        membership = qs.filter(organization_id=org_id).first()
        if membership:
            return membership
    return qs.order_by("id").first()
