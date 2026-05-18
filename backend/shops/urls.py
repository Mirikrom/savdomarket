from django.urls import include, path
from rest_framework.routers import DefaultRouter

from shops.views import BranchViewSet, OrganizationViewSet

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organizations")
router.register("branches", BranchViewSet, basename="branches")

urlpatterns = [
    path("", include(router.urls)),
]
