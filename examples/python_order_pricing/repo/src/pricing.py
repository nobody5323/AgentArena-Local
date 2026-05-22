from __future__ import annotations


COUPONS = {
    "SAVE10": 0.10,
    "VIP20": 0.20,
}


def calculate_total(items, coupon_code=None, vip=False, shipping=8.0, tax_rate=0.08):
    subtotal = sum(item["price"] * item.get("quantity", 1) for item in items)
    discount = 0.0

    if coupon_code in COUPONS:
        discount = subtotal * COUPONS[coupon_code]

    if vip:
        discount = subtotal * 0.05

    discounted = subtotal - discount
    shipping_fee = 0.0 if subtotal > 100 else shipping
    taxed = (discounted + shipping_fee) * tax_rate
    return round(discounted + shipping_fee + taxed, 2)

