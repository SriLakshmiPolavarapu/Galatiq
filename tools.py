import sqlite3
from crewai.tools import tool


def normalize(name):
    return name.replace(" ", "").lower()


@tool("check_inventory")
def check_inventory(item_name: str, requested_qty: int) -> str:
    """Check whether an item exists in the inventory database and whether there is enough
    stock to cover the requested quantity. Item name matching ignores spacing and case,
    since extracted invoice text sometimes formats names differently than the database
    (e.g. 'Widget A' vs 'WidgetA'). Returns a plain-language status for this one item."""
    conn = sqlite3.connect("inventory.db")
    rows = conn.execute("SELECT item, stock FROM inventory").fetchall()
    conn.close()

    inventory = {normalize(i): (i, s) for i, s in rows}
    key = normalize(item_name)

    if requested_qty < 0:
        return f"'{item_name}' has an invalid negative quantity: {requested_qty}."

    if key not in inventory:
        return f"'{item_name}' was not found in inventory. This item does not exist in our system."

    db_name, stock = inventory[key]
    if requested_qty > stock:
        return f"'{item_name}' found (matches inventory item '{db_name}'), but only {stock} in stock, requested {requested_qty}. Insufficient stock."

    return f"'{item_name}' found (matches inventory item '{db_name}'), {stock} in stock, sufficient for requested {requested_qty}. OK."


@tool("check_total_math")
def check_total_math(subtotal: float, tax: float, stated_total: float) -> str:
    """Verify that subtotal + tax equals the invoice's stated total. Use this to catch
    invoices where the final total has been tampered with or contains an arithmetic error,
    even if the line items and inventory all check out. Allows $1 tolerance for rounding."""
    expected = subtotal + tax
    if abs(expected - stated_total) > 1.00:
        return (
            f"MISMATCH: subtotal (${subtotal:,.2f}) + tax (${tax:,.2f}) = ${expected:,.2f}, "
            f"but the invoice states a total of ${stated_total:,.2f}. This is a data integrity issue."
        )
    return f"OK: subtotal + tax (${expected:,.2f}) matches the stated total (${stated_total:,.2f})."