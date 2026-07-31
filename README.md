# Invoice Processing Automation

A multi-agent system that automates end-to-end invoice processing for Acme Corp, a manufacturing company currently losing an estimated $2M per year to manual invoice handling (30% error rate, 5-day processing delays).

This is a working prototype, not a design document. Every invoice that runs through it is genuinely ingested, checked against inventory, reasoned over by real AI agents, and paid or rejected automatically.

## The business case

Manual invoice processing has three costly failure modes: staff misread messy or inconsistent invoice formats, human error lets invalid orders slip through, and multi-day approval chains delay payment and strain vendor relationships. This system removes all three:

- **Format tolerance.** Handles clean and messy invoices across five file types (TXT, JSON, CSV, PDF, XML), including OCR-style typos, abbreviated fields, and invoices buried inside email text.
- **Consistent validation.** Every invoice is checked against live inventory and its own stated math, every time, with no fatigue-driven oversight.
- **Fast, explainable decisions.** Approval or rejection happens in seconds, with a written reason attached, not a multi-day email chain.

## How it works

Every invoice moves through four stages:

1. **Ingestion.** Structured formats (JSON, well-formed CSV) are parsed directly. Anything less structured (TXT, PDF, XML, or an unusual CSV layout) is extracted using Grok, xAI's LLM, which handles typos and inconsistent formatting the way a human reader would.
2. **Validation.** Each line item is checked against a mock inventory database (stock levels, unknown items, invalid quantities), and the invoice's own subtotal, tax, and total are checked against each other to catch tampered or miscalculated totals.
3. **Approval.** A VP Approval Agent applies business rules (invoices over $10,000 get extra scrutiny) and decides to approve or reject. A separate Approval Critic Agent independently reviews that decision and can overturn it before it is final.
4. **Payment.** Approved invoices trigger a mock payment call. Rejected invoices are logged with the specific reason.

## Why this is a real multi-agent system, not a single prompt

The validation and approval stages are handled by three distinct CrewAI agents (Validation Agent, VP Approval Agent, Approval Critic Agent), each with its own role and reasoning, not one prompt doing everything. The Validation Agent does not receive pre-computed results, it calls tools itself (`check_inventory`, `check_total_math`) and reasons over what comes back, deciding on its own which items to check and when it has enough information to conclude.

## A safeguard worth knowing about

During testing, the Validation Agent occasionally skipped an actual tool call and fabricated a plausible-sounding result instead, most often right after a transient API error interrupted its reasoning loop. Since this is a system that authorizes real payments, prompt instructions alone were judged not to be a strong enough guarantee.

The fix: a deterministic Python check (no LLM involved) now runs alongside the agent on every invoice, and the Approval Agent's instructions explicitly state that this deterministic result is authoritative if it ever conflicts with the agent's own narrative. Testing confirmed that even when the Validation Agent hallucinated again on a later invoice, the final decision was still correct, because it deferred to ground truth.

## Setup

```bash
pip install crewai pdfplumber openai python-dotenv streamlit litellm
```

Create a `.env` file in the project root:

```
GROK_API_KEY=your_key_here
```

Build the inventory database (one-time step):

```bash
python setup_inventory.py
```

## Running it

**Command line:**

```bash
python main.py --invoice_path=data/invoices/invoice_1001.txt
```

Works with `.txt`, `.json`, `.csv`, `.pdf`, and `.xml` files.

**Web interface:**

```bash
streamlit run app.py
```

Upload an invoice, click Process Invoice, and watch the four stages run live with an approve or reject result at the end.

## Project structure

| File | Purpose |
|---|---|
| `ingestion.py` | Parses all five invoice formats into one common schema |
| `tools.py` | Inventory and math-check functions exposed as CrewAI tools |
| `agents.py` | The three CrewAI agents: Validation, VP Approval, Approval Critic |
| `validation.py` | Deterministic ground-truth validation (the safeguard described above) |
| `payment.py` | Mock payment logic |
| `main.py` | Command-line entry point, wires all four stages together |
| `app.py` | Streamlit web interface |
| `setup_inventory.py` | One-time script to build `inventory.db` |
| `data/invoices/` | Sample invoices used for testing |

## Tested scenarios

The system has been verified against invoices covering every required edge case: a clean invoice, an order exceeding available stock, a fraudulent zero-stock item, unrecognized items, a negative quantity, a total that does not match its own stated subtotal and tax, and a genuinely messy OCR-style PDF. Each produces the correct approve or reject outcome with a clear, specific reason.

## Design choices worth calling out

- **LLM use is targeted, not blanket.** Structured formats are parsed in plain Python, since that is faster, cheaper, and more reliable than asking an LLM to do something regex already does perfectly. The LLM is reserved for the two places that genuinely need it: reading messy unstructured text, and reasoning through an approval decision.
- **Fallback over failure.** Where a format turned out to have more variation than expected (multiple TXT layouts, multiple CSV layouts), the system tries the fast structured parser first and falls back to LLM extraction rather than crashing on an unfamiliar layout.
- **Verification before trust.** The deterministic ground-truth check exists because agent output was tested adversarially, not just on the happy path, and a real gap was found and closed before this was considered done.
