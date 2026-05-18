from rest_framework import serializers

from shops.models import Branch, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "phone", "address", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "id",
            "organization",
            "name",
            "address",
            "is_main",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "organization"]
