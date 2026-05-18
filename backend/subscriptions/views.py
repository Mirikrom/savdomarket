from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsOrganizationMember, RolePermissionRequired
from core.tenant import get_membership
from subscriptions.models import Plan, Subscription, SubscriptionInvoice
from subscriptions.serializers import (
    PlanSerializer,
    SubscriptionInvoiceSerializer,
    SubscriptionSerializer,
)


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(is_active=True).order_by("id")
    serializer_class = PlanSerializer
    permission_classes = [IsOrganizationMember]


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("organization", "plan").all().order_by("-id")
    serializer_class = SubscriptionSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "subscriptions.manage"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Subscription.objects.none()
        return self.queryset.filter(organization=membership.organization)

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        membership = get_membership(request)
        current_subscription = (
            self.get_queryset()
            .filter(status__in=["active", "grace"])
            .order_by("-ends_at")
            .first()
        )
        data = self.get_serializer(current_subscription).data if current_subscription else None
        return Response(
            {
                "organization_id": membership.organization_id if membership else None,
                "subscription": data,
            }
        )


class SubscriptionInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscriptionInvoice.objects.select_related("subscription", "subscription__organization")
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "subscriptions.view_invoices"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return SubscriptionInvoice.objects.none()
        return self.queryset.filter(subscription__organization=membership.organization)
