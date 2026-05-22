from accounts.models import OrganizationUser


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


def get_membership(request):
    if not request.user.is_authenticated:
        return None
    qs = active_organization_memberships(request.user)
    org_id = get_request_organization_id(request)
    if org_id:
        return qs.filter(organization_id=org_id).first()
    return None
