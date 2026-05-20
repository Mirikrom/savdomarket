from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsOrganizationMember, RolePermissionRequired
from core.tenant import get_membership
from sales.debt_utils import debtors_stats_bulk
from sales.models import Debtor, DebtPayment, Payment, Sale, SaleItem
from sales.serializers import (
    DebtorSerializer,
    DebtorWriteSerializer,
    DebtPaymentCreateSerializer,
    DebtPaymentReadSerializer,
    PaymentReadSerializer,
    SaleCreateSerializer,
    SaleItemReadSerializer,
    SaleSerializer,
)


class SaleViewSet(viewsets.ModelViewSet):
    queryset = (
        Sale.objects.select_related("organization", "branch", "cashier", "debtor")
        .prefetch_related("items", "items__product", "payments")
        .all()
        .order_by("-sold_at", "-id")
    )
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "sales.manage"

    def get_serializer_class(self):
        if self.action == "create":
            return SaleCreateSerializer
        return SaleSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["membership"] = get_membership(self.request)
        return ctx

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Sale.objects.none()

        qs = self.queryset.filter(organization=membership.organization)
        params = self.request.query_params

        branch_id = params.get("branch")
        status_value = params.get("status")
        cashier_id = params.get("cashier")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        if status_value:
            qs = qs.filter(status=status_value)
        if cashier_id:
            qs = qs.filter(cashier_id=cashier_id)
        if date_from:
            qs = qs.filter(sold_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(sold_at__date__lte=date_to)
        return qs

    def create(self, request, *args, **kwargs):
        membership = get_membership(request)
        write_serializer = SaleCreateSerializer(
            data=request.data,
            context={"request": request, "membership": membership},
        )
        write_serializer.is_valid(raise_exception=True)
        sale = write_serializer.save()
        read_serializer = SaleSerializer(sale)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="today-summary")
    def today_summary(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Tashkilot konteksti yo'q."}, status=403)

        today = timezone.localdate()
        qs = Sale.objects.filter(
            organization=membership.organization,
            sold_at__date=today,
            status=Sale.Status.COMPLETED,
        )
        branch_id = request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        agg = qs.aggregate(
            sales_count=Count("id"),
            total_sum=Sum("total"),
            paid_sum=Sum("paid"),
        )
        my_qs = qs.filter(cashier=request.user)
        my_agg = my_qs.aggregate(
            sales_count=Count("id"),
            total_sum=Sum("total"),
        )

        return Response(
            {
                "today": today.isoformat(),
                "all": {
                    "sales_count": agg["sales_count"] or 0,
                    "total_sum": agg["total_sum"] or Decimal("0"),
                    "paid_sum": agg["paid_sum"] or Decimal("0"),
                },
                "mine": {
                    "sales_count": my_agg["sales_count"] or 0,
                    "total_sum": my_agg["total_sum"] or Decimal("0"),
                },
            }
        )


class SaleItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        SaleItem.objects.select_related("sale", "product", "batch").all().order_by("-id")
    )
    serializer_class = SaleItemReadSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "sales.view"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return SaleItem.objects.none()
        return self.queryset.filter(sale__organization=membership.organization)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related("sale").all().order_by("-id")
    serializer_class = PaymentReadSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "sales.view"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Payment.objects.none()
        return self.queryset.filter(sale__organization=membership.organization)


class DebtorViewSet(viewsets.ModelViewSet):
    queryset = Debtor.objects.filter(is_active=True).order_by("name", "id")
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "sales.manage"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return DebtorWriteSerializer
        return DebtorSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["membership"] = get_membership(self.request)
        return ctx

    def _debtor_stats(self, debtor_ids):
        membership = get_membership(self.request)
        if not membership or not debtor_ids:
            return {}
        return debtors_stats_bulk(membership.organization_id, list(debtor_ids))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        stats = self._debtor_stats(queryset.values_list("id", flat=True))
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset
        serializer = DebtorSerializer(
            items,
            many=True,
            context={**self.get_serializer_context(), "stats_by_id": stats},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        stats = self._debtor_stats([instance.id])
        serializer = DebtorSerializer(
            instance,
            context={**self.get_serializer_context(), "stats_by_id": stats},
        )
        return Response(serializer.data)

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Debtor.objects.none()
        qs = Debtor.objects.filter(
            organization=membership.organization, is_active=True
        ).order_by("name", "id")
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
        return qs

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)

    def create(self, request, *args, **kwargs):
        membership = get_membership(self.request)
        client_uuid = request.data.get("client_uuid")
        if client_uuid:
            existing = Debtor.objects.filter(
                organization=membership.organization, client_uuid=client_uuid
            ).first()
            if existing:
                stats = self._debtor_stats([existing.id])
                read_serializer = DebtorSerializer(
                    existing,
                    context={**self.get_serializer_context(), "stats_by_id": stats},
                )
                return Response(read_serializer.data, status=status.HTTP_200_OK)

        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)
        stats = self._debtor_stats([write_serializer.instance.id])
        read_serializer = DebtorSerializer(
            write_serializer.instance,
            context={**self.get_serializer_context(), "stats_by_id": stats},
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        write_serializer.is_valid(raise_exception=True)
        write_serializer.save()
        stats = self._debtor_stats([instance.id])
        read_serializer = DebtorSerializer(
            instance,
            context={**self.get_serializer_context(), "stats_by_id": stats},
        )
        return Response(read_serializer.data)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_active", "deleted_at", "updated_at"])

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        membership = get_membership(request)
        debtor = self.get_object()
        write_serializer = DebtPaymentCreateSerializer(
            data=request.data,
            context={"request": request, "membership": membership, "debtor": debtor},
        )
        write_serializer.is_valid(raise_exception=True)
        payment = write_serializer.save()
        read_serializer = DebtPaymentReadSerializer(payment)
        stats = debtors_stats_bulk(membership.organization_id, [debtor.id])
        debtor_data = DebtorSerializer(
            debtor, context={"membership": membership, "stats_by_id": stats}
        ).data
        return Response(
            {"payment": read_serializer.data, "debtor": debtor_data},
            status=status.HTTP_201_CREATED,
        )


class DebtPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        DebtPayment.objects.select_related("debtor", "branch", "received_by")
        .all()
        .order_by("-created_at", "-id")
    )
    serializer_class = DebtPaymentReadSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "sales.view"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return DebtPayment.objects.none()
        qs = self.queryset.filter(organization=membership.organization)
        debtor_id = self.request.query_params.get("debtor")
        if debtor_id:
            qs = qs.filter(debtor_id=debtor_id)
        return qs
