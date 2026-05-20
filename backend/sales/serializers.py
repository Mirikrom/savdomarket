from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from catalog.models import Product
from inventory.models import StockMovement
from inventory.stock_utils import get_product_quantity_at_branch
from sales.debt_utils import debtors_stats_bulk, debtor_balance_due
from sales.models import Debtor, DebtPayment, Payment, Sale, SaleItem
from shops.models import Branch


class SaleItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_unit = serializers.CharField(source="product.unit", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "product_unit",
            "batch",
            "quantity",
            "unit_price",
            "line_total",
        ]
        read_only_fields = fields


class SaleItemWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    batch = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )


class PaymentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "method", "amount", "paid_at", "transaction_ref"]
        read_only_fields = fields


class PaymentWriteSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    transaction_ref = serializers.CharField(max_length=100, required=False, allow_blank=True)


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemReadSerializer(many=True, read_only=True)
    payments = PaymentReadSerializer(many=True, read_only=True)
    cashier_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    debtor_name = serializers.CharField(source="debtor.name", read_only=True)
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "id",
            "organization",
            "branch",
            "branch_name",
            "cashier",
            "cashier_name",
            "debtor",
            "debtor_name",
            "subtotal",
            "discount",
            "total",
            "paid",
            "change",
            "balance_due",
            "status",
            "sold_at",
            "client_uuid",
            "stock_conflict",
            "note",
            "items",
            "payments",
        ]
        read_only_fields = fields

    def get_cashier_name(self, obj):
        if not obj.cashier:
            return None
        return obj.cashier.full_name or obj.cashier.username

    def get_balance_due(self, obj):
        return obj.balance_due


class SaleCreateSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    sold_at = serializers.DateTimeField(required=False, allow_null=True, write_only=True)
    allow_offline = serializers.BooleanField(required=False, default=False, write_only=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    debtor = serializers.PrimaryKeyRelatedField(
        queryset=Debtor.objects.filter(is_active=True), required=False, allow_null=True
    )
    discount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    items = SaleItemWriteSerializer(many=True)
    payments = PaymentWriteSerializer(many=True, required=False, default=list)

    def validate(self, attrs):
        membership = self.context.get("membership")
        if membership is None:
            raise serializers.ValidationError("Tashkilot konteksti aniqlanmadi.")

        branch = attrs["branch"]
        if branch.organization_id != membership.organization_id:
            raise serializers.ValidationError(
                {"branch": "Filial ushbu tashkilotga tegishli emas."}
            )
        if not attrs.get("items"):
            raise serializers.ValidationError({"items": "Hech bo'lmaganda bitta mahsulot kerak."})

        for line in attrs["items"]:
            if line["product"].organization_id != membership.organization_id:
                raise serializers.ValidationError(
                    {"items": "Ba'zi mahsulotlar ushbu tashkilotga tegishli emas."}
                )

        debtor = attrs.get("debtor")
        if debtor and debtor.organization_id != membership.organization_id:
            raise serializers.ValidationError(
                {"debtor": "Qarzdor ushbu tashkilotga tegishli emas."}
            )

        payments_data = attrs.get("payments") or []
        paid = sum((Decimal(p["amount"]) for p in payments_data), Decimal("0"))

        subtotal = Decimal("0")
        discount = attrs.get("discount", Decimal("0")) or Decimal("0")
        for line in attrs["items"]:
            product = line["product"]
            quantity = Decimal(line["quantity"])
            unit_price = (
                Decimal(line["unit_price"])
                if line.get("unit_price") is not None
                else product.sell_price
            )
            subtotal += (quantity * unit_price).quantize(Decimal("0.01"))
        total = (subtotal - discount).quantize(Decimal("0.01"))

        if paid > total:
            raise serializers.ValidationError(
                {"payments": "To'langan summa savdo summasidan oshmasligi kerak."}
            )
        if paid < total and not debtor:
            raise serializers.ValidationError(
                {"payments": "Qarzga savdo uchun qarzdorni tanlang yoki to'liq to'lang."}
            )

        return attrs

    def validate_sold_at(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            parsed = parse_datetime(value)
            if parsed is None:
                raise serializers.ValidationError("sold_at formati noto‘g‘ri.")
            value = parsed
        if timezone.is_aware(value):
            value = timezone.localtime(value).replace(tzinfo=None)
        return value

    @transaction.atomic
    def create(self, validated_data):
        membership = self.context["membership"]
        request = self.context["request"]
        organization = membership.organization

        client_uuid = validated_data.pop("client_uuid", None)
        sold_at_raw = validated_data.pop("sold_at", None)
        allow_offline = validated_data.pop("allow_offline", False)
        items_data = validated_data.pop("items")
        payments_data = validated_data.pop("payments", []) or []
        branch = validated_data.pop("branch")
        debtor = validated_data.pop("debtor", None)
        discount = validated_data.pop("discount", Decimal("0")) or Decimal("0")
        note = validated_data.pop("note", "") or ""

        if client_uuid:
            existing = Sale.objects.filter(
                organization=organization, client_uuid=client_uuid
            ).first()
            if existing:
                return existing

        if sold_at_raw is not None:
            sold_at = sold_at_raw
        elif allow_offline:
            raise serializers.ValidationError(
                {"sold_at": "Offline savdo uchun sotuv vaqti (sold_at) majburiy."}
            )
        else:
            sold_at = timezone.now()

        subtotal = Decimal("0")
        line_payloads = []
        for line in items_data:
            product = line["product"]
            quantity = Decimal(line["quantity"])
            unit_price = (
                Decimal(line["unit_price"])
                if line.get("unit_price") is not None
                else product.sell_price
            )
            line_total = (quantity * unit_price).quantize(Decimal("0.01"))
            subtotal += line_total
            line_payloads.append(
                {
                    "product": product,
                    "batch_id": line.get("batch"),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

        if discount > subtotal:
            raise serializers.ValidationError(
                {"discount": "Chegirma jami summadan oshmasligi kerak."}
            )

        total = (subtotal - discount).quantize(Decimal("0.01"))
        paid = sum((Decimal(p["amount"]) for p in payments_data), Decimal("0"))
        change = (paid - total).quantize(Decimal("0.01"))

        stock_conflict = False
        if allow_offline:
            for lp in line_payloads:
                available = get_product_quantity_at_branch(
                    organization.id, branch.id, lp["product"].id
                )
                if available < lp["quantity"]:
                    stock_conflict = True
                    break

        sale = Sale.objects.create(
            organization=organization,
            branch=branch,
            cashier=request.user,
            debtor=debtor,
            subtotal=subtotal,
            discount=discount,
            total=total,
            paid=paid,
            change=change,
            status=Sale.Status.COMPLETED,
            sold_at=sold_at,
            client_uuid=client_uuid,
            stock_conflict=stock_conflict,
            note=note,
        )

        for lp in line_payloads:
            sale_item = SaleItem.objects.create(
                sale=sale,
                product=lp["product"],
                batch_id=lp["batch_id"],
                quantity=lp["quantity"],
                unit_price=lp["unit_price"],
                line_total=lp["line_total"],
            )
            movement = StockMovement.objects.create(
                organization=organization,
                branch=branch,
                product=sale_item.product,
                batch=sale_item.batch,
                movement_type=StockMovement.MovementType.OUT,
                quantity=sale_item.quantity,
                unit_cost=Decimal("0"),
                ref_type="sale",
                ref_id=sale.id,
                created_by=request.user,
            )
            if allow_offline:
                StockMovement.objects.filter(pk=movement.pk).update(created_at=sold_at)

        for pay in payments_data:
            Payment.objects.create(
                sale=sale,
                method=pay["method"],
                amount=pay["amount"],
                paid_at=sold_at,
                transaction_ref=pay.get("transaction_ref", ""),
            )

        Sale.objects.filter(pk=sale.pk).update(sold_at=sold_at, created_at=sold_at)

        sale.refresh_from_db()

        return sale


class DebtorSerializer(serializers.ModelSerializer):
    balance_due = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    first_credit_at = serializers.SerializerMethodField()
    last_credit_at = serializers.SerializerMethodField()
    last_payment_at = serializers.SerializerMethodField()

    class Meta:
        model = Debtor
        fields = [
            "id",
            "name",
            "phone",
            "note",
            "due_date",
            "is_active",
            "total_credit",
            "total_paid",
            "balance_due",
            "first_credit_at",
            "last_credit_at",
            "last_payment_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "total_credit",
            "total_paid",
            "balance_due",
            "first_credit_at",
            "last_credit_at",
            "last_payment_at",
            "created_at",
            "updated_at",
        ]

    def _stats(self, obj):
        cached = self.context.get("stats_by_id")
        if cached is not None:
            return cached.get(obj.id, {})
        membership = self.context.get("membership")
        if not membership:
            return {}
        return debtors_stats_bulk(membership.organization_id, [obj.id]).get(obj.id, {})

    def get_balance_due(self, obj):
        return self._stats(obj).get("balance_due", Decimal("0"))

    def get_total_credit(self, obj):
        return self._stats(obj).get("total_credit", Decimal("0"))

    def get_total_paid(self, obj):
        return self._stats(obj).get("total_paid", Decimal("0"))

    def get_first_credit_at(self, obj):
        return self._stats(obj).get("first_credit_at")

    def get_last_credit_at(self, obj):
        return self._stats(obj).get("last_credit_at")

    def get_last_payment_at(self, obj):
        return self._stats(obj).get("last_payment_at")


class DebtorWriteSerializer(serializers.ModelSerializer):
    client_uuid = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Debtor
        fields = ["name", "phone", "note", "due_date", "client_uuid"]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Ism kiritilishi shart.")
        return value


class DebtPaymentReadSerializer(serializers.ModelSerializer):
    debtor_name = serializers.CharField(source="debtor.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DebtPayment
        fields = [
            "id",
            "debtor",
            "debtor_name",
            "branch",
            "branch_name",
            "amount",
            "method",
            "note",
            "received_by",
            "received_by_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_received_by_name(self, obj):
        if not obj.received_by:
            return None
        return obj.received_by.full_name or obj.received_by.username


class DebtPaymentCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(
        choices=DebtPayment.Method.choices, default=DebtPayment.Method.CASH
    )
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        membership = self.context.get("membership")
        debtor = self.context.get("debtor")
        if membership is None or debtor is None:
            raise serializers.ValidationError("Kontekst aniqlanmadi.")

        branch = attrs["branch"]
        if branch.organization_id != membership.organization_id:
            raise serializers.ValidationError(
                {"branch": "Filial ushbu tashkilotga tegishli emas."}
            )
        if debtor.organization_id != membership.organization_id:
            raise serializers.ValidationError({"debtor": "Qarzdor ushbu tashkilotga tegishli emas."})

        balance = debtor_balance_due(membership.organization_id, debtor.id)
        amount = Decimal(attrs["amount"])
        if amount > balance:
            raise serializers.ValidationError(
                {"amount": f"Qarz summasi {balance} so'mdan oshmasligi kerak."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        membership = self.context["membership"]
        debtor = self.context["debtor"]
        request = self.context["request"]
        return DebtPayment.objects.create(
            organization=membership.organization,
            branch=validated_data["branch"],
            debtor=debtor,
            amount=validated_data["amount"],
            method=validated_data["method"],
            note=validated_data.get("note", "") or "",
            received_by=request.user,
        )
