from decimal import Decimal

from django.db.models import DecimalField, Max, Sum, Value
from django.db.models.functions import Coalesce

from sales.models import DebtPayment, Sale


def _empty_stats():
    return {
        "total_credit": Decimal("0"),
        "total_paid": Decimal("0"),
        "balance_due": Decimal("0"),
        "first_credit_at": None,
        "last_credit_at": None,
        "last_payment_at": None,
    }


def debtor_balance_due(organization_id: int, debtor_id: int) -> Decimal:
    stats = debtors_stats_bulk(organization_id, [debtor_id]).get(debtor_id) or _empty_stats()
    return stats["balance_due"]


def debtors_stats_bulk(organization_id: int, debtor_ids: list[int]) -> dict[int, dict]:
    ids = [int(i) for i in debtor_ids if i]
    if not ids:
        return {}

    out = {did: _empty_stats() for did in ids}

    sales = Sale.objects.filter(
        organization_id=organization_id,
        debtor_id__in=ids,
        status=Sale.Status.COMPLETED,
    ).values("debtor_id", "total", "paid", "sold_at")

    for row in sales:
        did = row["debtor_id"]
        if did not in out:
            continue
        portion = max(
            Decimal("0"),
            Decimal(row["total"] or 0) - Decimal(row["paid"] or 0),
        )
        if portion <= 0:
            continue
        st = out[did]
        st["total_credit"] += portion
        sold_at = row["sold_at"]
        if st["first_credit_at"] is None or sold_at < st["first_credit_at"]:
            st["first_credit_at"] = sold_at
        if st["last_credit_at"] is None or sold_at > st["last_credit_at"]:
            st["last_credit_at"] = sold_at

    pay_agg = (
        DebtPayment.objects.filter(organization_id=organization_id, debtor_id__in=ids)
        .values("debtor_id")
        .annotate(
            paid_sum=Coalesce(
                Sum("amount", output_field=DecimalField(max_digits=14, decimal_places=2)),
                Value(Decimal("0")),
            ),
            last_at=Max("created_at"),
        )
    )
    for row in pay_agg:
        did = row["debtor_id"]
        if did not in out:
            continue
        out[did]["total_paid"] = Decimal(row["paid_sum"] or 0).quantize(Decimal("0.01"))
        if row["last_at"]:
            out[did]["last_payment_at"] = row["last_at"]

    for did, st in out.items():
        st["total_credit"] = st["total_credit"].quantize(Decimal("0.01"))
        st["balance_due"] = max(
            Decimal("0"), (st["total_credit"] - st["total_paid"]).quantize(Decimal("0.01"))
        )

    return out
