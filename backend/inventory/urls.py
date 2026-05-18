from django.urls import include, path
from rest_framework.routers import DefaultRouter

from inventory.views import ProductBatchViewSet, StockLevelView, StockMovementViewSet

router = DefaultRouter()
router.register("product-batches", ProductBatchViewSet, basename="product-batches")
router.register("stock-movements", StockMovementViewSet, basename="stock-movements")

urlpatterns = [
    path("", include(router.urls)),
    path("stock-levels/", StockLevelView.as_view(), name="stock-levels"),
]
