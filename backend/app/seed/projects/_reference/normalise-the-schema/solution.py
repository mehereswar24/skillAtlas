def normalise(rows: list[dict]) -> dict:
    customers: dict[str, dict] = {}
    products: dict[str, dict] = {}
    items: list[dict] = []

    for row in rows:
        name = row["customer"]
        if name not in customers:
            customers[name] = {"id": len(customers) + 1, "name": name}

        product = row["product"]
        if product not in products:
            products[product] = {
                "id": len(products) + 1,
                "name": product,
                "unit_price": row["unit_price"],
            }

        items.append(
            {
                "order_id": row["order_id"],
                "customer_id": customers[name]["id"],
                "product_id": products[product]["id"],
                "quantity": row["quantity"],
            }
        )

    return {
        "customers": list(customers.values()),
        "products": list(products.values()),
        "order_items": items,
    }
