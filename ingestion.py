import os

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