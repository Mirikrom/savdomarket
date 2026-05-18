from decimal import Decimal

from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce

from inventory.models import StockMovement

SIGNED_QTY_EXPR = Case(
    When(movement_type=StockMovement.MovementType.IN, then=F("quantity")),
    When(movement_type=StockMovement.MovementType.RETURN, then=F("quantity")),
    When(movement_type=StockMovement.MovementType.OUT, then=-F("quantity")),
    When(movement_type=StockMovement.MovementType.ADJUST, then=F("quantity")),
    default=Value(Decimal("0")),
    output_field=DecimalField(max_digits=14, decimal_places=3),
)


def get_product_quantity_at_branch(organization_id, branch_id, product_id):
    """Filialdagi joriy qoldiq (StockMovement jamlanmasi)."""
    agg = (
        StockMovement.objects.filter(
            organization_id=organization_id,
            branch_id=branch_id,
            product_id=product_id,
        )
        .aggregate(total=Coalesce(Sum(SIGNED_QTY_EXPR), Decimal("0")))
    )
    return agg["total"] or Decimal("0")
