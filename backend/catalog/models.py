from django.db import models
from django.db.models import Q

from core.models import SoftDeleteModel, TimeStampedModel


class Category(TimeStampedModel, SoftDeleteModel):
    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_category_per_organization"
            )
        ]

    def __str__(self):
        return self.name


class Product(TimeStampedModel, SoftDeleteModel):
    class Unit(models.TextChoices):
        PIECE = "piece", "Piece"
        KG = "kg", "Kilogram"
        LITER = "liter", "Liter"
        PACK = "pack", "Pack"

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="products"
    )
    branch = models.ForeignKey(
        "shops.Branch",
        on_delete=models.SET_NULL,
        related_name="products",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, related_name="products", null=True, blank=True
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    unit = models.CharField(max_length=16, choices=Unit.choices, default=Unit.PIECE)
    sell_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tan narxi",
    )
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True,
        verbose_name="Rasm",
    )

    class Meta:
        indexes = [models.Index(fields=["organization", "name"])]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sku"],
                condition=~Q(sku=""),
                name="uniq_sku_per_organization",
            )
        ]

    def __str__(self):
        return self.name
