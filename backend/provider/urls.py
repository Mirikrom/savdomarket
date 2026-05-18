from django.urls import include, path
from rest_framework.routers import DefaultRouter

from provider.views import (
    ProviderChangePasswordView,
    ProviderOrganizationViewSet,
    ProviderPlanViewSet,
    ProviderSettingsView,
    ProviderStatsView,
    ProviderUserViewSet,
)

router = DefaultRouter()
router.register("organizations", ProviderOrganizationViewSet, basename="provider-org")
router.register("plans", ProviderPlanViewSet, basename="provider-plan")
router.register("users", ProviderUserViewSet, basename="provider-user")

urlpatterns = [
    path("stats/", ProviderStatsView.as_view(), name="provider-stats"),
    path("settings/", ProviderSettingsView.as_view(), name="provider-settings"),
    path("change-password/", ProviderChangePasswordView.as_view(), name="provider-change-password"),
    path("", include(router.urls)),
]
