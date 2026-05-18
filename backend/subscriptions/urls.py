from django.urls import include, path
from rest_framework.routers import DefaultRouter

from subscriptions.views import PlanViewSet, SubscriptionInvoiceViewSet, SubscriptionViewSet

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="plans")
router.register("subscriptions", SubscriptionViewSet, basename="subscriptions")
router.register("subscription-invoices", SubscriptionInvoiceViewSet, basename="subscription-invoices")

urlpatterns = [
    path("", include(router.urls)),
]
