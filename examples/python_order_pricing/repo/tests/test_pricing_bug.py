from examples.python_order_pricing.repo.src.pricing import calculate_total


def test_coupon_is_trimmed_and_case_insensitive():
    total = calculate_total(
        [{"price": 50.0, "quantity": 2}],
        coupon_code=" save10 ",
        shipping=8.0,
        tax_rate=0.08,
    )

    assert total == 105.84


def test_vip_discount_stacks_after_coupon_discount():
    total = calculate_total(
        [{"price": 120.0, "quantity": 1}],
        coupon_code="SAVE10",
        vip=True,
        shipping=8.0,
        tax_rate=0.08,
    )

    assert total == 110.81

