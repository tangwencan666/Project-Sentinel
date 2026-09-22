"""Payment amount normalization, separate from transport and persistence."""


def normalize_amount(amount):
    return float(amount)
