from openai import OpenAI
from ingestion import ingest_invoice
from validation import validate_invoice
from approval import approve_invoice
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.environ["GROK_API_KEY"], base_url="https://api.x.ai/v1")

invoice = ingest_invoice("data/invoices/invoice_1001.txt")
validation = validate_invoice(invoice)
result = approve_invoice(invoice, validation, client)
print(result)