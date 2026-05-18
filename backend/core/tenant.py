from accounts.models import OrganizationUser


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
    org_id = get_request_organization_id(request)
    if not request.user.is_authenticated or not org_id:
        return None
    return (
        OrganizationUser.objects.select_related("role", "organization", "branch")
        .filter(user=request.user, organization_id=org_id, status="active", is_active=True)
        .first()
    )
