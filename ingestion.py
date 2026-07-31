import os
import json
import csv
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

Pay close attention to these three amount fields, they often appear under different labels:
- "subtotal": the pre-tax total, may be labeled "Subtotal", "Amt", or similar
- "tax": the tax amount, may be labeled "Tax", "Tax (X%)", or similar. If truly no tax is
  mentioned anywhere, use 0, not null.
- "total": the final amount due, may be labeled "Total", "Grand Total", "Total Amount",
  "Amount Due", or similar
If subtotal or tax genuinely do not appear anywhere in the text, use null for that field only.
Do not skip a field just because it appears in a table or near other numbers, scan the full text.

Return ONLY valid JSON in exactly this shape, no other text:
{{
  "invoice_number": string or null,
  "vendor": string or null,
  "date": string or null,
  "due_date": string or null,
  "items": [{{"item": string, "qty": number, "unit_price": number}}],
  "subtotal": number or null,
  "tax": number or null,
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
    elif ext == ".xml":
        return parse_xml(filepath)
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
        "subtotal": data.get("subtotal"),
        "tax": data.get("tax_amount"),
        "payment_terms": data.get("payment_terms"),
    }

def parse_csv(filepath):
    """Tries the known field/value CSV layout first (cheap, no LLM). If the CSV uses a
    different layout (e.g. a wide table with one row per item), falls back to LLM
    extraction on the raw text, same approach as txt/pdf/xml."""
    try:
        return parse_csv_field_value(filepath)
    except (KeyError, ValueError):
        with open(filepath, "r") as f:
            raw_text = f.read()
        return extract_via_llm(raw_text)

def parse_csv_field_value(filepath):
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
        "subtotal": float(fields["subtotal"]) if "subtotal" in fields else None,
        "tax": float(fields["tax"]) if "tax" in fields else None,
        "payment_terms": fields.get("payment_terms"),
    }

def extract_via_llm(raw_text):
    """Shared LLM extraction used by any format too unstructured for direct parsing (txt, pdf, xml)."""
    response = client.chat.completions.create(
        model="grok-4-fast",
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=raw_text)}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    data["raw_text"] = raw_text
    return data

def parse_txt(filepath):
    with open(filepath, "r") as f:
        raw_text = f.read()
    return extract_via_llm(raw_text)

def extract_pdf_text(filepath):
    with pdfplumber.open(filepath) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text

def parse_pdf(filepath):
    raw_text = extract_pdf_text(filepath)
    return extract_via_llm(raw_text)

def parse_xml(filepath):
    with open(filepath, "r") as f:
        raw_text = f.read()
    return extract_via_llm(raw_text)