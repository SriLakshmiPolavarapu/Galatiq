import streamlit as st
import tempfile
import os
from ingestion import ingest_invoice
from agents import run_validation, run_approval
from payment import process_payment
from main import parse_decision

st.set_page_config(page_title="Invoice Processing Agent", layout="centered")

st.title("Invoice Processing System")
st.caption("Automated multi-agent invoice ingestion, validation, approval, and payment.")

uploaded_file = st.file_uploader(
    "Upload an invoice",
    type=["txt", "json", "csv", "pdf", "xml"],
)

if uploaded_file is not None:
    if st.button("Process Invoice", type="primary"):
        # Save the uploaded file to a temp path so our existing file-based functions work unchanged
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            with st.status("Processing invoice...", expanded=True) as status:
                st.write("**Step 1/4 — Ingesting**")
                invoice = ingest_invoice(tmp_path)
                st.write(f"Parsed: `{invoice['invoice_number']}` from **{invoice['vendor']}**, total **${invoice['total']:,.2f}**" if invoice['total'] else "Parsed invoice, but total could not be extracted.")

                st.write("**Step 2/4 — Validation Agent**")
                validation_summary = run_validation(invoice)
                st.write(validation_summary)

                st.write("**Step 3/4 — Approval Agent (with critic review)**")
                approval_text = run_approval(invoice, validation_summary)
                approval = parse_decision(approval_text)

                st.write("**Step 4/4 — Payment**")
                payment = process_payment(invoice, approval)

                status.update(label="Processing complete", state="complete")

            # Final result, front and center
            if approval["decision"] == "approved":
                st.success(f"✅ APPROVED — Payment of ${invoice['total']:,.2f} sent to {invoice['vendor']}" if invoice['total'] else "✅ APPROVED")
            else:
                st.error("❌ REJECTED — No payment sent")

            with st.expander("Full approval reasoning"):
                st.write(approval["reasoning"])

            with st.expander("Extracted invoice data"):
                st.json({k: v for k, v in invoice.items() if k != "raw_text"})

        finally:
            os.unlink(tmp_path)
else:
    st.info("Upload an invoice file to begin.")