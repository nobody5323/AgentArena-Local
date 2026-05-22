from examples.python_order_pricing.repo.src.pricing import calculate_total


def test_existing_order_without_coupon_keeps_shipping_and_tax():
    total = calculate_total(
        [{"price": 20.0, "quantity": 2}],
        shipping=8.0,
        tax_rate=0.08,
    )

    assert total == 51.84


def test_unknown_coupon_is_ignored():
    total = calculate_total(
        [{"price": 60.0, "quantity": 1}],
        coupon_code="MISSING",
        shipping=8.0,
        tax_rate=0.08,
    )

    assert total == 73.44

