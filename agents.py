import os
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from tools import check_inventory, check_total_math

load_dotenv()

grok_llm = LLM(
    model="xai/grok-4-fast",  
    api_key=os.environ.get("GROK_API_KEY", ""),
)

def kickoff_with_retry(crew, max_attempts=3, delay_seconds=5):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return crew.kickoff()
        except ValueError as e:
            last_error = e
            if attempt < max_attempts:
                time.sleep(delay_seconds)
    raise last_error

def build_validation_crew(invoice):
    validator = Agent(
        role="Invoice Validation Specialist",
        goal="Check every line item against inventory and verify the invoice math is correct",
        backstory="You are meticulous and never approve an invoice without checking every item and every number.",
        tools=[check_inventory, check_total_math],
        llm=grok_llm,
        verbose=True,
    )

    items_list = "\n".join(f"{idx+1}. item_name=\"{i['item']}\", requested_qty={i['qty']}" for idx, i in enumerate(invoice["items"]))
    num_items = len(invoice["items"])

    task = Task(
        description=f"""Validate this invoice by calling your tools. Follow these steps exactly, in order:

{items_list}

Step-by-step instructions:
- Call check_inventory exactly ONCE for each of the {num_items} items listed above, using its exact item_name and requested_qty.
- Never call check_inventory twice with the same item_name, each call must be for a DIFFERENT item from the list.
- After you have called check_inventory for all {num_items} items, call check_total_math ONCE with
  subtotal={invoice.get('subtotal')}, tax={invoice.get('tax')}, stated_total={invoice.get('total')}.
  If subtotal or tax is None, skip this call and note that the math check was skipped.
- Only after all tool calls above are complete, give your Final Answer.

CRITICAL RULE: You must NEVER state that an item's stock is sufficient, insufficient, found, or not found
unless you actually called check_inventory for that exact item and are reporting its real returned output.
Making up or guessing a tool's result instead of calling it is a serious error. If you are about to write
"Inventory check: OK" or similar for an item you have not called check_inventory on, stop and call the tool
first. There are {num_items} required check_inventory calls in this task, count them before answering.

Your Final Answer must summarize every item's status and the math check result, then give an overall PASS or FAIL verdict with reasons.""",
        expected_output="A summary listing each item's status and the total math check result, followed by an overall PASS or FAIL verdict with reasons.",
        agent=validator,
    )

    return Crew(agents=[validator], tasks=[task], verbose=True)

def run_validation(invoice):
    crew = build_validation_crew(invoice)
    result = kickoff_with_retry(crew)
    return str(result)

def build_approval_crew(invoice, validation_summary, ground_truth):
    approver = Agent(
        role="VP Approval Agent",
        goal="Decide whether to approve or reject invoices based on validation results and business rules",
        backstory="You are a VP who approves invoices. You reject anything with unresolved validation issues. "
                   "Invoices over $10,000 require extra scrutiny before approval.",
        llm=grok_llm,
        verbose=True,
    )

    critic = Agent(
        role="Approval Critic",
        goal="Catch mistakes in approval decisions before they're finalized",
        backstory="You are a skeptical second reviewer. You re-check the validation summary against the "
                   "decision that was made, and you are not afraid to overturn a decision if it's wrong.",
        llm=grok_llm,
        verbose=True,
    )

    ground_truth_text = "PASSED (no issues found)." if ground_truth["passed"] else "FAILED with these issues:\n" + "\n".join(
        f"- {f['item'] or 'invoice'}: {f['issue']} — {f['detail']}" for f in ground_truth["flags"]
    )

    decide_task = Task(
        description=f"""Decide whether to approve or reject this invoice.

Invoice: {invoice}

GROUND TRUTH VALIDATION (computed directly by the system, guaranteed accurate): {ground_truth_text}

Validation agent's narrative summary (for context only, may occasionally be incomplete): {validation_summary}

IMPORTANT: The GROUND TRUTH VALIDATION above is authoritative. If it conflicts with the narrative summary,
trust the GROUND TRUTH. Base your decision primarily on the GROUND TRUTH result.

Invoices over $10,000 require extra scrutiny. Any unresolved validation issue
(unknown item, insufficient stock, invalid quantity, total mismatch) is a strong
reason to reject. Minor formatting oddities alone are not.

State your decision (APPROVED or REJECTED) and your reasoning.""",
        expected_output="A decision (APPROVED or REJECTED) with clear reasoning.",
        agent=approver,
    )

    critique_task = Task(
        description=f"""Review the approval decision above. Check specifically:
- Does the GROUND TRUTH VALIDATION ({ground_truth_text}) actually support this decision?
- Was every issue in the ground truth accounted for?
- Is there anything the approver missed?

If the decision holds up, confirm it. If not, overturn it and explain why.
State your FINAL decision (APPROVED or REJECTED) and reasoning.""",
        expected_output="A final decision (APPROVED or REJECTED) with reasoning, confirming or overturning the prior decision.",
        agent=critic,
        context=[decide_task],
    )

    return Crew(agents=[approver, critic], tasks=[decide_task, critique_task], verbose=True)

def run_approval(invoice, validation_summary, ground_truth):
    crew = build_approval_crew(invoice, validation_summary, ground_truth)
    result = kickoff_with_retry(crew)
    return str(result)