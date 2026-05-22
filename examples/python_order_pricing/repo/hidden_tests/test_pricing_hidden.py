from examples.python_order_pricing.repo.src.pricing import calculate_total


def test_free_shipping_threshold_uses_discounted_subtotal_at_100():
    total = calculate_total(
        [{"price": 100.0, "quantity": 1}],
        coupon_code="SAVE10",
        shipping=8.0,
        tax_rate=0.08,
    )

    assert total == 105.84


def test_tax_is_rounded_only_at_the_final_total():
    total = calculate_total(
        [{"price": 19.99, "quantity": 3}],
        coupon_code="SAVE10",
        vip=True,
        shipping=8.0,
        tax_rate=0.0825,
    )

    assert total == 64.16
