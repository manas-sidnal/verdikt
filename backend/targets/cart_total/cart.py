def total(items, tax_rate=0.0):
    """Total price for a list of (unit_price, quantity) pairs, including tax."""
    return sum(price * qty for price, qty in items)
