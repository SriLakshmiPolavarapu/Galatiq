import argparse
import os
from dotenv import load_dotenv
from openai import OpenAI

from ingestion import ingest_invoice
from validation import validate_invoice
from approval import approve_invoice
from payment import process_payment

load_dotenv()


def run_pipeline(invoice_path):
    client = OpenAI(api_key=os.environ["GROK_API_KEY"], base_url="https://api.x.ai/v1")

    print(f"[1/4] Ingesting: {invoice_path}")
    invoice = ingest_invoice(invoice_path)
    print(f"      Parsed: {invoice['invoice_number']} from {invoice['vendor']}, total ${invoice['total']}")

    print("[2/4] Validating against inventory...")
    validation = validate_invoice(invoice)
    if validation["passed"]:
        print("      No issues found.")
    else:
        for flag in validation["flags"]:
            print(f"      FLAGGED: {flag['item']} — {flag['issue']}: {flag['detail']}")

    print("[3/4] Running approval agent...")
    approval = approve_invoice(invoice, validation, client)
    print(f"      Decision: {approval['decision'].upper()} — {approval['reasoning']}")

    print("[4/4] Processing payment...")
    payment = process_payment(invoice, approval)
    if payment["paid"]:
        print(f"      Payment sent.")
    else:
        print(f"      No payment sent. Reason: {payment['rejection_reason']}")

    return {
        "invoice": invoice,
        "validation": validation,
        "approval": approval,
        "payment": payment,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--invoice_path", required=True)
    args = parser.parse_args()

    run_pipeline(args.invoice_path)