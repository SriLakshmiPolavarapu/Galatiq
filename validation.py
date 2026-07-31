import sqlite3


def normalize(name):
    """Strip spaces and lowercase, so 'Widget A' and 'WidgetA' match."""
    return name.replace(" ", "").lower()


def load_inventory(db_path="inventory.db"):
    """Returns {normalized_name: (original_name, stock)} for every item in the DB."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT item, stock FROM inventory").fetchall()
    conn.close()
    return {normalize(item): (item, stock) for item, stock in rows}


def validate_invoice(invoice, db_path="inventory.db"):
    """Checks each line item against inventory. Returns a list of flags, plus a pass/fail summary."""
    inventory = load_inventory(db_path)
    flags = []

    for line in invoice["items"]:
        item_name = line["item"]
        qty = line["qty"]
        key = normalize(item_name)

        if qty < 0:
            flags.append({"item": item_name, "issue": "invalid_quantity", "detail": f"Negative quantity: {qty}"})
            continue

        if key not in inventory:
            flags.append({"item": item_name, "issue": "unknown_item", "detail": "Item not found in inventory"})
            continue

        db_name, stock = inventory[key]
        if qty > stock:
            flags.append({
                "item": item_name,
                "issue": "insufficient_stock",
                "detail": f"Requested {qty}, only {stock} in stock",
            })

    return {
        "passed": len(flags) == 0,
        "flags": flags,
    }