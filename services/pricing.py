"""Order pricing. This module is the allowlisted patch target."""

def total(price: float, quantity: int, discount: float | None = 0) -> float:
    if price < 0 or quantity < 1:
        raise ValueError("invalid order")
    return round(price * quantity * (1 - discount), 2)
