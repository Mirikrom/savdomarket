from decimal import Decimal

from rest_framework import serializers

from catalog.models import Product
from inventory.models import ProductBatch, StockMovement
from shops.models import Branch


class ProductBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBatch
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_unit = serializers.CharField(source="product.unit", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "organization",
            "branch",
            "branch_name",
            "product",
            "product_name",
            "product_sku",
            "product_unit",
            "batch",
            "movement_type",
            "quantity",
            "unit_cost",
            "ref_type",
            "ref_id",
            "note",
            "client_uuid",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_by",
            "created_at",
            "product_name",
            "product_sku",
            "product_unit",
            "branch_name",
            "created_by_name",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.full_name or obj.created_by.username


class StockMovementWriteSerializer(serializers.ModelSerializer):
    """For create/update — validates org scoping and quantity sign rules."""

    class Meta:
        model = StockMovement
        fields = [
            "branch",
            "product",
            "batch",
            "movement_type",
            "quantity",
            "unit_cost",
            "ref_type",
            "ref_id",
            "note",
            "client_uuid",
        ]

    def validate(self, attrs):
        membership = self.context.get("membership")
        if membership is None:
            raise serializers.ValidationError("Tashkilot konteksti aniqlanmadi.")

        product = attrs.get("product")
        branch = attrs.get("branch")
        batch = attrs.get("batch")
        movement_type = attrs.get("movement_type")
        quantity = attrs.get("quantity")

        if product and product.organization_id != membership.organization_id:
            raise serializers.ValidationError(
                {"product": "Mahsulot ushbu tashkilotga tegishli emas."}
            )
        if branch and branch.organization_id != membership.organization_id:
            raise serializers.ValidationError(
                {"branch": "Filial ushbu tashkilotga tegishli emas."}
            )
        if batch and product and batch.product_id != product.id:
            raise serializers.ValidationError(
                {"batch": "Tanlangan partiya ushbu mahsulotga tegishli emas."}
            )

        if quantity is None or quantity == 0:
            raise serializers.ValidationError({"quantity": "Miqdor 0 dan farqli bo‘lishi shart."})

        # 'in', 'out', 'return' uchun musbat son; 'adjust' uchun ishorali (musbat/manfiy) ruxsat etiladi.
        if movement_type in (
            StockMovement.MovementType.IN,
            StockMovement.MovementType.OUT,
            StockMovement.MovementType.RETURN,
        ) and quantity < 0:
            raise serializers.ValidationError(
                {"quantity": "Bu harakat turi uchun miqdor musbat son bo‘lishi kerak."}
            )

        return attrs


class StockLevelSerializer(serializers.Serializer):
    """Aggregated current stock per (product, branch)."""

    product = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    product_unit = serializers.CharField()
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(allow_blank=True, allow_null=True)
    branch = serializers.IntegerField(allow_null=True)
    branch_name = serializers.CharField(allow_blank=True, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    min_stock = serializers.DecimalField(max_digits=12, decimal_places=3)
    is_low = serializers.BooleanField()
    sell_price = serializers.DecimalField(max_digits=12, decimal_places=2)


class StockInLineSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))


class StockInBulkSerializer(serializers.Serializer):
    """Bulk kirim — bir nechta mahsulotni bitta blank orqali."""

    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    items = StockInLineSerializer(many=True)

    def validate(self, attrs):
        membership = self.context.get("membership")
        if membership is None:
            raise serializers.ValidationError("Tashkilot konteksti aniqlanmadi.")
        if attrs["branch"].organization_id != membership.organization_id:
            raise serializers.ValidationError(
                {"branch": "Filial ushbu tashkilotga tegishli emas."}
            )
        if not attrs.get("items"):
            raise serializers.ValidationError({"items": "Hech bo‘lmaganda bitta qator kerak."})
        for line in attrs["items"]:
            if line["product"].organization_id != membership.organization_id:
                raise serializers.ValidationError(
                    {"items": "Ba’zi mahsulotlar ushbu tashkilotga tegishli emas."}
                )
        return attrs
