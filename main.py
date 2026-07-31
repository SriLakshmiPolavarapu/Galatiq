import argparse
from ingestion import ingest_invoice
from agents import run_validation, run_approval
from validation import validate_invoice
from payment import process_payment

def parse_decision(approval_text):
    upper = approval_text.upper()
    approved_pos = upper.find("APPROVED")
    rejected_pos = upper.find("REJECTED")

    if approved_pos == -1 and rejected_pos == -1:
        decision = "rejected" 
    elif rejected_pos != -1 and (approved_pos == -1 or rejected_pos < approved_pos):
        decision = "rejected"
    else:
        decision = "approved"

    return {"decision": decision, "reasoning": approval_text.strip()}


def run_pipeline(invoice_path):
    print(f"[1/4] Ingesting: {invoice_path}")
    invoice = ingest_invoice(invoice_path)
    print(f"Parsed: {invoice['invoice_number']} from {invoice['vendor']}, total ${invoice['total']}")

    print("[2/4] Running validation agent + deterministic ground-truth check...")
    validation_summary = run_validation(invoice)
    ground_truth = validate_invoice(invoice)  
    print(f"Agent narrative: {validation_summary}")
    print(f"Ground truth: {'PASSED' if ground_truth['passed'] else 'FAILED - ' + str(ground_truth['flags'])}")

    print("[3/4] Running approval agent (with critic review, grounded in deterministic check)...")
    approval_text = run_approval(invoice, validation_summary, ground_truth)
    approval = parse_decision(approval_text)
    print(f"Decision: {approval['decision'].upper()}")

    print("[4/4] Processing payment...")
    payment = process_payment(invoice, approval)
    if payment["paid"]:
        print(f"Payment sent.")
    else:
        print(f"No payment sent.")

    return {
        "invoice": invoice,
        "validation_summary": validation_summary,
        "ground_truth": ground_truth,
        "approval": approval,
        "payment": payment,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--invoice_path", required=True)
    args = parser.parse_args()

    run_pipeline(args.invoice_path)