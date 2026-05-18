from rest_framework import serializers

from subscriptions.models import Plan, Subscription, SubscriptionInvoice


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = PlanSerializer(source="plan", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "organization",
            "plan",
            "plan_detail",
            "starts_at",
            "ends_at",
            "status",
            "auto_renew",
            "created_at",
        ]
        read_only_fields = ["id", "organization", "created_at"]


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionInvoice
        fields = "__all__"
        read_only_fields = ["id", "subscription", "created_at"]
