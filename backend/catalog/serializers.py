from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from catalog.models import Category, Product
from core.tenant import get_membership
from inventory.models import StockMovement

MAX_PRODUCT_IMAGE_BYTES = 3 * 1024 * 1024


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["id", "organization", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    """Yaratishda: initial_quantity > 0 bo‘lsa branch majburiy, boshlang‘ich kirim yoziladi."""

    initial_quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        write_only=True,
        default=Decimal("0"),
    )
    clear_image = serializers.BooleanField(write_only=True, required=False, default=False)
    image_url = serializers.SerializerMethodField(read_only=True)
    image = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "organization",
            "branch",
            "category",
            "name",
            "sku",
            "barcode",
            "unit",
            "sell_price",
            "cost_price",
            "min_stock",
            "image_url",
            "image",
            "is_active",
            "deleted_at",
            "created_at",
            "updated_at",
            "initial_quantity",
            "clear_image",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_at",
            "updated_at",
            "is_active",
            "deleted_at",
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        return obj.image.url

    def validate_image(self, value):
        if value and getattr(value, "size", 0) > MAX_PRODUCT_IMAGE_BYTES:
            raise serializers.ValidationError("Rasm hajmi 3 MB dan oshmasin.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        membership = get_membership(request)
        if membership and "name" in attrs:
            name = (attrs.get("name") or "").strip()
            if name:
                qs = Product.objects.filter(
                    organization=membership.organization,
                    is_active=True,
                    deleted_at__isnull=True,
                    name__iexact=name,
                )
                if self.instance is not None:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError(
                        {"name": "Bu nomdagi mahsulot allaqachon mavjud."}
                    )

        if self.instance is not None:
            return attrs
        qty = attrs.get("initial_quantity", Decimal("0"))
        if qty is None:
            qty = Decimal("0")
        if qty > 0 and not attrs.get("branch"):
            raise serializers.ValidationError(
                {"branch": "Boshlang‘ich ombor qoldiqi uchun filialni tanlang."}
            )
        return attrs

    def create(self, validated_data):
        initial_qty = validated_data.pop("initial_quantity", Decimal("0"))
        validated_data.pop("clear_image", None)
        validated_data.pop("is_active", None)
        validated_data.pop("deleted_at", None)
        if initial_qty is None:
            initial_qty = Decimal("0")
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        with transaction.atomic():
            product = super().create(validated_data)
            if not product.is_active or product.deleted_at is not None:
                product.is_active = True
                product.deleted_at = None
                product.save(update_fields=["is_active", "deleted_at", "updated_at"])
            if initial_qty > 0 and product.branch_id:
                StockMovement.objects.create(
                    organization=product.organization,
                    branch=product.branch,
                    product=product,
                    movement_type=StockMovement.MovementType.PRODUCT_CREATE,
                    quantity=Decimal("0"),
                    unit_cost=Decimal("0"),
                    note="Mahsulot qo'shildi",
                    ref_type="catalog",
                    ref_id=product.id,
                    created_by=user,
                )
                StockMovement.objects.create(
                    organization=product.organization,
                    branch=product.branch,
                    product=product,
                    movement_type=StockMovement.MovementType.IN,
                    quantity=initial_qty,
                    unit_cost=product.cost_price or Decimal("0"),
                    note="Kirim",
                    ref_type="catalog",
                    ref_id=product.id,
                    created_by=user,
                )
            return product

    def update(self, instance, validated_data):
        validated_data.pop("initial_quantity", None)
        validated_data.pop("is_active", None)
        validated_data.pop("deleted_at", None)
        clear_image = validated_data.pop("clear_image", False)
        has_new_image = "image" in validated_data
        if clear_image and not has_new_image:
            if instance.image:
                instance.image.delete(save=False)
            validated_data["image"] = None
        return super().update(instance, validated_data)
