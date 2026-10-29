def total(items, tax_rate=0.0):
    """Total price for a list of (unit_price, quantity) pairs, including tax."""
    subtotal = 0.0
    for price, qty in items:
        if qty < 0:
            raise ValueError("quantity must be non-negative")
        subtotal += price * qty
    return round(subtotal * (1 + tax_rate), 2)
