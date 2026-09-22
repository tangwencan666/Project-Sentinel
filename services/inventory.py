"""Catalog record normalization, separate from storage and cache policy."""


def normalize_product(product):
    return {**product, 'price': float(product['price'])}
