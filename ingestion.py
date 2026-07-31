import os
import json
import csv
import re
import pdfplumber
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("GROK_API_KEY", ""),
    base_url="https://api.x.ai/v1",
)

EXTRACTION_PROMPT = """You are an invoice data extraction agent. Extract structured data
from the raw invoice text below, even if it contains typos, OCR errors, or inconsistent
formatting (e.g. "2O26" means "2026", "Payble" means "Payable", missing spaces in item
names should be corrected if obvious).

Return ONLY valid JSON in exactly this shape, no other text:
{{
  "invoice_number": string or null,
  "vendor": string or null,
  "date": string or null,
  "due_date": string or null,
  "items": [{{"item": string, "qty": number, "unit_price": number}}],
  "total": number or null,
  "payment_terms": string or null
}}

Invoice text:
---
{text}
---
"""


def ingest_invoice(filepath):
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".txt":
        return parse_txt(filepath)
    elif ext == ".json":
        return parse_json(filepath)
    elif ext == ".csv":
        return parse_csv(filepath)
    elif ext == ".pdf":
        return parse_pdf(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def parse_json(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)

    return {
        "invoice_number": data.get("invoice_number"),
        "vendor": data.get("vendor", {}).get("name"),
        "date": data.get("date"),
        "due_date": data.get("due_date"),
        "items": [
            {"item": li["item"], "qty": li["quantity"], "unit_price": li["unit_price"]}
            for li in data.get("line_items", [])
        ],
        "total": data.get("total"),
        "payment_terms": data.get("payment_terms"),
    }


def parse_csv(filepath):
    fields = {}
    items = []
    current_item = {}

    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key, value = row["field"], row["value"]

            if key == "item":
                if current_item:
                    items.append(current_item)
                current_item = {"item": value}
            elif key == "quantity":
                current_item["qty"] = int(value)
            elif key == "unit_price":
                current_item["unit_price"] = float(value)
            else:
                fields[key] = value

        if current_item:
            items.append(current_item)

    return {
        "invoice_number": fields.get("invoice_number"),
        "vendor": fields.get("vendor"),
        "date": fields.get("date"),
        "due_date": fields.get("due_date"),
        "items": items,
        "total": float(fields["total"]) if "total" in fields else None,
        "payment_terms": fields.get("payment_terms"),
    }


def parse_txt(filepath):
    with open(filepath, "r") as f:
        lines = f.readlines()

    fields = {}
    items = []
    item_pattern = re.compile(r"(\S+)\s+qty:\s*(\d+)\s+unit price:\s*\$?([\d,]+\.?\d*)")

    for line in lines:
        line = line.strip()
        if not line or line == "INVOICE" or line == "Items:":
            continue

        item_match = item_pattern.match(line)
        if item_match:
            name, qty, price = item_match.groups()
            items.append({
                "item": name,
                "qty": int(qty),
                "unit_price": float(price.replace(",", "")),
            })
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

    total_raw = fields.get("Total Amount", "").replace("$", "").replace(",", "")

    return {
        "invoice_number": fields.get("Invoice Number"),
        "vendor": fields.get("Vendor"),
        "date": fields.get("Date"),
        "due_date": fields.get("Due Date"),
        "items": items,
        "total": float(total_raw) if total_raw else None,
        "payment_terms": fields.get("Payment Terms"),
    }


def extract_pdf_text(filepath):
    with pdfplumber.open(filepath) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text


def parse_pdf(filepath):
    raw_text = extract_pdf_text(filepath)

    response = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=raw_text)}],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    data["raw_text"] = raw_text
    return data