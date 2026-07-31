def mock_payment(vendor, amount):
    print(f"Paid {amount} to {vendor}")
    return {"status": "success"}


def process_payment(invoice, approval_result):
    if approval_result["decision"] == "approved":
        result = mock_payment(invoice["vendor"], invoice["total"])
        return {"paid": True, "payment_result": result}
    else:
        return {
            "paid": False,
            "rejection_reason": approval_result["reasoning"],
        }