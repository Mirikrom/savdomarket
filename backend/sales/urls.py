from django.urls import include, path
from rest_framework.routers import DefaultRouter

from sales.views import (
    DebtPaymentViewSet,
    DebtorViewSet,
    PaymentViewSet,
    SaleItemViewSet,
    SaleViewSet,
)

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sales")
router.register("sale-items", SaleItemViewSet, basename="sale-items")
router.register("payments", PaymentViewSet, basename="payments")
router.register("debtors", DebtorViewSet, basename="debtors")
router.register("debt-payments", DebtPaymentViewSet, basename="debt-payments")

urlpatterns = [
    path("", include(router.urls)),
]
