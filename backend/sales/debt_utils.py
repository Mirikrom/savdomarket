from decimal import Decimal

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from sales.models import DebtPayment, Sale


def debtor_balance_due(organization_id: int, debtor_id: int) -> Decimal:
    """Jami qarz = savdolardagi qoldiq − alohida qoplangan to'lovlar."""
    sales_agg = Sale.objects.filter(
        organization_id=organization_id,
        debtor_id=debtor_id,
        status=Sale.Status.COMPLETED,
    ).aggregate(
        total=Coalesce(
            Sum(F("total") - F("paid"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            Value(Decimal("0")),
        )
    )
    pay_agg = DebtPayment.objects.filter(
        organization_id=organization_id,
        debtor_id=debtor_id,
    ).aggregate(total=Coalesce(Sum("amount"), Value(Decimal("0"))))
    balance = Decimal(sales_agg["total"] or 0) - Decimal(pay_agg["total"] or 0)
    return max(Decimal("0"), balance.quantize(Decimal("0.01")))
