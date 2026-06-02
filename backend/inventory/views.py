from decimal import Decimal

from django.db import transaction
from django.db.models import (
    Case,
    DecimalField,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from core.permissions import (
    IsOrganizationMember,
    RolePermissionRequired,
    StockMovementScopePermission,
    SubscriptionFeatureRequired,
)
from core.tenant import get_membership
from inventory.models import ProductBatch, StockMovement
from shops.models import Branch
from inventory.serializers import (
    ProductBatchSerializer,
    StockInBulkSerializer,
    StockLevelSerializer,
    StockMovementSerializer,
    StockMovementWriteSerializer,
)


SIGNED_QTY_EXPR = Case(
    When(movement_type=StockMovement.MovementType.IN, then=F("quantity")),
    When(movement_type=StockMovement.MovementType.RETURN, then=F("quantity")),
    When(movement_type=StockMovement.MovementType.OUT, then=-F("quantity")),
    When(movement_type=StockMovement.MovementType.ADJUST, then=F("quantity")),
    default=Value(Decimal("0")),
    output_field=DecimalField(max_digits=14, decimal_places=3),
)


class ProductBatchViewSet(viewsets.ModelViewSet):
    queryset = ProductBatch.objects.select_related("product").all().order_by("-id")
    serializer_class = ProductBatchSerializer
    permission_classes = [
        IsOrganizationMember,
        RolePermissionRequired,
        SubscriptionFeatureRequired,
    ]
    required_permission = "inventory.manage"
    required_feature = "batch_tracking"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return ProductBatch.objects.none()
        return self.queryset.filter(product__organization=membership.organization)


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = (
        StockMovement.objects.select_related(
            "organization", "branch", "product", "batch", "created_by"
        )
        .all()
        .order_by("-id")
    )
    permission_classes = [IsOrganizationMember, StockMovementScopePermission]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return StockMovementWriteSerializer
        return StockMovementSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["membership"] = get_membership(self.request)
        return ctx

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return StockMovement.objects.none()

        qs = self.queryset.filter(organization=membership.organization)
        params = self.request.query_params

        branch_id = params.get("branch")
        product_id = params.get("product")
        movement_type = params.get("movement_type")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        if product_id:
            qs = qs.filter(product_id=product_id)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(
            organization=membership.organization,
            created_by=self.request.user,
        )

    def create(self, request, *args, **kwargs):
        membership = get_membership(request)
        client_uuid = request.data.get("client_uuid")
        if client_uuid and membership:
            existing = StockMovement.objects.filter(
                organization=membership.organization,
                client_uuid=client_uuid,
            ).first()
            if existing:
                read_serializer = StockMovementSerializer(existing)
                return Response(read_serializer.data, status=status.HTTP_200_OK)

        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)
        instance = write_serializer.instance
        read_serializer = StockMovementSerializer(instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="bulk-in")
    def bulk_in(self, request):
        """Bir nechta mahsulotni bir vaqtning o‘zida kirim qilish."""
        membership = get_membership(request)
        serializer = StockInBulkSerializer(
            data=request.data, context={"membership": membership}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        created = []
        with transaction.atomic():
            for line in data["items"]:
                movement = StockMovement.objects.create(
                    organization=membership.organization,
                    branch=data["branch"],
                    product=line["product"],
                    movement_type=StockMovement.MovementType.IN,
                    quantity=line["quantity"],
                    unit_cost=line.get("unit_cost") or Decimal("0"),
                    note=data.get("note", ""),
                    created_by=request.user,
                )
                created.append(movement)

        out = StockMovementSerializer(created, many=True).data
        return Response({"created": len(created), "items": out}, status=status.HTTP_201_CREATED)


class StockLevelView(APIView):
    """Joriy qoldiqlar — (product, branch) bo‘yicha jamlangan."""

    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Tashkilot konteksti yo‘q."}, status=403)

        params = request.query_params
        branch_id = params.get("branch")
        search = (params.get("search") or "").strip()
        only_low = params.get("only_low") in ("1", "true", "True")

        movements = StockMovement.objects.filter(organization=membership.organization)
        if branch_id:
            movements = movements.filter(branch_id=branch_id)

        agg = (
            movements.values("product_id", "branch_id")
            .annotate(quantity=Coalesce(Sum(SIGNED_QTY_EXPR), Decimal("0")))
        )

        # product/branch nomlarini olish uchun lookup tayyorlaymiz.
        product_qs = Product.objects.filter(
            organization=membership.organization, is_active=True
        ).select_related("category")
        if search:
            product_qs = product_qs.filter(
                Q(name__icontains=search)
                | Q(sku__icontains=search)
                | Q(barcode__icontains=search)
            )
        product_map = {p.id: p for p in product_qs}

        branch_map = {
            b.id: b
            for b in Branch.objects.filter(organization=membership.organization, is_active=True)
        }

        rows = []
        # Mavjud harakatlar uchun yozuvlar
        seen = set()
        for entry in agg:
            pid = entry["product_id"]
            bid = entry["branch_id"]
            product = product_map.get(pid)
            if not product:
                continue
            branch = branch_map.get(bid)
            qty = entry["quantity"] or Decimal("0")
            is_low = qty <= (product.min_stock or 0)
            if only_low and not is_low:
                continue
            rows.append(
                {
                    "product": pid,
                    "product_name": product.name,
                    "product_sku": product.sku or "",
                    "product_unit": product.unit,
                    "category_id": product.category_id,
                    "category_name": product.category.name if product.category else None,
                    "branch": bid,
                    "branch_name": branch.name if branch else None,
                    "quantity": qty,
                    "min_stock": product.min_stock or Decimal("0"),
                    "is_low": is_low,
                    "sell_price": product.sell_price or Decimal("0"),
                }
            )
            seen.add((pid, bid))

        # Hech qachon kirim qilinmagan mahsulotlarni ham ko‘rsatamiz (qoldiq = 0).
        if not branch_id:
            for pid, product in product_map.items():
                if not any(p == pid for (p, _b) in seen):
                    is_low = (product.min_stock or 0) > 0
                    if only_low and not is_low:
                        continue
                    rows.append(
                        {
                            "product": pid,
                            "product_name": product.name,
                            "product_sku": product.sku or "",
                            "product_unit": product.unit,
                            "category_id": product.category_id,
                            "category_name": product.category.name
                            if product.category
                            else None,
                            "branch": None,
                            "branch_name": None,
                            "quantity": Decimal("0"),
                            "min_stock": product.min_stock or Decimal("0"),
                            "is_low": is_low,
                            "sell_price": product.sell_price or Decimal("0"),
                        }
                    )
        else:
            for pid, product in product_map.items():
                if (pid, int(branch_id)) in seen:
                    continue
                is_low = (product.min_stock or 0) > 0
                if only_low and not is_low:
                    continue
                rows.append(
                    {
                        "product": pid,
                        "product_name": product.name,
                        "product_sku": product.sku or "",
                        "product_unit": product.unit,
                        "category_id": product.category_id,
                        "category_name": product.category.name if product.category else None,
                        "branch": int(branch_id),
                        "branch_name": branch_map.get(int(branch_id)).name
                        if branch_map.get(int(branch_id))
                        else None,
                        "quantity": Decimal("0"),
                        "min_stock": product.min_stock or Decimal("0"),
                        "is_low": is_low,
                        "sell_price": product.sell_price or Decimal("0"),
                    }
                )

        rows.sort(key=lambda r: (not r["is_low"], r["product_name"].lower()))
        data = StockLevelSerializer(rows, many=True).data

        low_count = sum(1 for r in rows if r["is_low"])
        total_quantity = sum((r["quantity"] for r in rows), Decimal("0"))
        return Response(
            {
                "results": data,
                "summary": {
                    "products_count": len(rows),
                    "low_stock_count": low_count,
                    "total_quantity": total_quantity,
                },
            }
        )
