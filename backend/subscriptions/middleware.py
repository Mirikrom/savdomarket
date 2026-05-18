from django.http import JsonResponse

from core.tenant import get_membership
from subscriptions.services import get_active_subscription


class SubscriptionAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/v1/"):
            return self.get_response(request)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Platforma egasi (superuser) va Provider API uchun cheklov yo'q.
        if request.path.startswith("/api/v1/provider/") or request.user.is_superuser:
            return self.get_response(request)

        membership = get_membership(request)
        if not membership:
            return self.get_response(request)

        request.membership = membership
        request.organization = membership.organization
        request.subscription = get_active_subscription(membership.organization)

        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.subscription:
            return JsonResponse(
                {"detail": "Active subscription is required for write operations."},
                status=402,
            )

        return self.get_response(request)
