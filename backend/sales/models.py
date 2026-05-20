from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import SoftDeleteModel, TimeStampedModel


class Debtor(TimeStampedModel, SoftDeleteModel):
    """Qarzdor mijoz (tashkilot ichidagi retail mijoz)."""

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="debtors"
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    note = models.CharField(max_length=500, blank=True)
    due_date = models.DateField(null=True, blank=True, help_text="Qarz qaytarish muddati")
    client_uuid = models.UUIDField(null=True, blank=True, editable=False, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "name"])]
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="uniq_debtor_client_uuid_per_org",
            )
        ]

    def __str__(self):
        return self.name


class Sale(TimeStampedModel):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"
        RETURNED = "returned", "Returned"

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="sales"
    )
    branch = models.ForeignKey("shops.Branch", on_delete=models.CASCADE, related_name="sales")
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales"
    )
    debtor = models.ForeignKey(
        Debtor,
        on_delete=models.SET_NULL,
        related_name="sales",
        null=True,
        blank=True,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED)
    sold_at = models.DateTimeField(default=timezone.now)
    client_uuid = models.UUIDField(null=True, blank=True, editable=False, db_index=True)
    stock_conflict = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "branch", "sold_at"]),
            models.Index(fields=["cashier", "sold_at"]),
            models.Index(fields=["organization", "debtor"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="uniq_sale_client_uuid_per_org",
            )
        ]

    def __str__(self):
        return f"Sale #{self.pk}"

    @property
    def balance_due(self):
        return max(Decimal("0"), (self.total or Decimal("0")) - (self.paid or Decimal("0")))


class SaleItem(TimeStampedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="sale_items"
    )
    batch = models.ForeignKey(
        "inventory.ProductBatch",
        on_delete=models.SET_NULL,
        related_name="sale_items",
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        MIXED = "mixed", "Mixed"
        TRANSFER = "transfer", "Transfer"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=16, choices=Method.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    transaction_ref = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.sale_id} - {self.method} - {self.amount}"


class DebtPayment(TimeStampedModel):
    """Qarzdor qarzini qoplash (to'liq yoki qisman)."""

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        TRANSFER = "transfer", "Transfer"

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="debt_payments"
    )
    branch = models.ForeignKey(
        "shops.Branch", on_delete=models.CASCADE, related_name="debt_payments"
    )
    debtor = models.ForeignKey(Debtor, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.CASH)
    note = models.CharField(max_length=255, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="debt_payments_received",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "debtor", "created_at"])]

    def __str__(self):
        return f"DebtPayment #{self.pk} — {self.debtor.name}: {self.amount}"
