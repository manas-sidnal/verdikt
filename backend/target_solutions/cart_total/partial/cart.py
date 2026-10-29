def total(items, tax_rate=0.0):
    """Total price for a list of (unit_price, quantity) pairs, including tax."""
    subtotal = sum(price * qty for price, qty in items)
    return round(subtotal * (1 + tax_rate), 2)
