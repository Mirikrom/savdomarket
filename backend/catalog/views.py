from django.utils import timezone
from rest_framework import viewsets

from catalog.models import Category, Product
from catalog.serializers import CategorySerializer, ProductSerializer
from core.permissions import (
    CatalogReadOrManagePermission,
    IsOrganizationMember,
    ProductReadOrManagePermission,
    SubscriptionFeatureRequired,
)
from core.tenant import get_membership


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related("organization").all().order_by("-id")
    serializer_class = CategorySerializer
    permission_classes = [IsOrganizationMember, CatalogReadOrManagePermission]

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Category.objects.none()
        return self.queryset.filter(organization=membership.organization)

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("organization", "branch", "category").all().order_by("-id")
    serializer_class = ProductSerializer
    permission_classes = [
        IsOrganizationMember,
        ProductReadOrManagePermission,
        SubscriptionFeatureRequired,
    ]
    required_feature = "products"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Product.objects.none()
        return self.queryset.filter(
            organization=membership.organization,
            is_active=True,
            deleted_at__isnull=True,
        )

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)

    def perform_destroy(self, instance):
        """Savdo qatorlari PROTECT — qattiq DELETE 500 beradi. Yumshoq o‘chirish."""
        instance.is_active = False
        instance.deleted_at = timezone.now()
        instance.save()
