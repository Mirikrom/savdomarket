from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ProductBatch(TimeStampedModel):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="batches"
    )
    batch_no = models.CharField(max_length=64)
    expiry_date = models.DateField(null=True, blank=True)
    buy_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "batch_no"], name="uniq_batch_per_product"
            )
        ]

    def __str__(self):
        return f"{self.product.name} ({self.batch_no})"


class StockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"
        ADJUST = "adjust", "Adjust"
        RETURN = "return", "Return"
        PRODUCT_CREATE = "product_create", "Product create"

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="stock_movements"
    )
    branch = models.ForeignKey(
        "shops.Branch", on_delete=models.CASCADE, related_name="stock_movements"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="stock_movements"
    )
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
        null=True,
        blank=True,
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ref_type = models.CharField(max_length=32, blank=True)
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        indexes = [
            models.Index(fields=["organization", "branch", "product"]),
            models.Index(fields=["movement_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.movement_type} - {self.quantity}"
