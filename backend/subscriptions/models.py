from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class Plan(TimeStampedModel):
    class PlanCode(models.TextChoices):
        LITE = "lite", "Lite"
        PRO = "pro", "Pro"

    code = models.CharField(max_length=16, choices=PlanCode.choices, unique=True)
    name = models.CharField(max_length=64)
    price_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_users = models.PositiveIntegerField(default=3)
    max_products = models.PositiveIntegerField(default=500)
    max_branches = models.PositiveIntegerField(default=1)
    feature_flags = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subscription(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        GRACE = "grace", "Grace"
        EXPIRED = "expired", "Expired"
        CANCELED = "canceled", "Canceled"

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    auto_renew = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["ends_at"]),
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.plan.code}"


class SubscriptionInvoice(TimeStampedModel):
    class InvoiceStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="invoices"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING
    )
    transaction_ref = models.CharField(max_length=120, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "due_date"])]

    def __str__(self):
        return f"Invoice #{self.pk} - {self.subscription.organization.name}"
