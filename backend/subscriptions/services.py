from django.utils import timezone

from subscriptions.models import Subscription


def get_active_subscription(organization):
    now = timezone.now()
    return (
        Subscription.objects.select_related("plan")
        .filter(
            organization=organization,
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.GRACE],
            starts_at__lte=now,
            ends_at__gte=now,
        )
        .order_by("-ends_at")
        .first()
    )


def has_feature_access(organization, feature_code):
    subscription = get_active_subscription(organization)
    if not subscription:
        return False
    if subscription.plan.code == "pro":
        return True
    feature_flags = subscription.plan.feature_flags or {}
    return bool(feature_flags.get(feature_code, False))
