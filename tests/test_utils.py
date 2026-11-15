from decimal import Decimal
from utils import cod_advance
def test_cod_advance_standard():
    assert cod_advance(Decimal("999")) == (Decimal("50.00"), Decimal("949.00"))
def test_cod_advance_caps_at_total():
    assert cod_advance(Decimal("30")) == (Decimal("30.00"), Decimal("0.00"))
