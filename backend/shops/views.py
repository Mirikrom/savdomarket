from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsOrganizationMember, RolePermissionRequired
from core.tenant import get_membership
from shops.models import Branch, Organization
from shops.serializers import BranchSerializer, OrganizationSerializer


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Organization.objects.none()
        return self.queryset.filter(id=membership.organization_id)


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.select_related("organization").all().order_by("-id")
    serializer_class = BranchSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "branches.manage"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Branch.objects.none()
        return self.queryset.filter(organization=membership.organization)

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)
