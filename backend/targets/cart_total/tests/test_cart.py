import pytest

from cart import total


def test_empty_cart_is_zero():
    assert total([]) == 0


def test_subtotal():
    assert total([(10.0, 2), (5.0, 1)]) == 25.0


def test_applies_tax():
    assert total([(100.0, 1)], tax_rate=0.1) == 110.0


def test_rounds_to_cents():
    assert total([(0.1, 3)]) == 0.3


def test_tax_rounds_to_cents():
    assert total([(9.99, 1)], tax_rate=0.07) == 10.69


def test_negative_quantity_rejected():
    with pytest.raises(ValueError):
        total([(1.0, -1)])
