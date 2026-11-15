from decimal import Decimal, ROUND_HALF_UP
def money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
def cod_advance(total, configured=Decimal("50.00")):
    total=money(total); advance=min(total,money(configured))
    return advance, money(total-advance)
