import json


APPROVAL_PROMPT = """You are a VP-level invoice approval agent. Review this invoice and decide
whether to approve or reject it.

Invoice: {invoice}
Validation result: {validation}
Requires extra scrutiny (over $10K): {high_value}

Consider: any unknown items or insufficient stock are strong reasons to reject.
Minor formatting oddities alone are not reasons to reject.

Return ONLY valid JSON in this shape, no other text:
{{"decision": "approved" or "rejected", "reasoning": string}}
"""

CRITIQUE_PROMPT = """You made this initial decision on an invoice:
{initial_decision}

Original invoice: {invoice}
Validation result: {validation}

Critically review your own decision. Check specifically:
- Did you correctly account for every validation flag?
- Does the reasoning actually support the decision (e.g. don't approve if there are unresolved flags)?
- Is there anything you missed?

Return ONLY valid JSON, revised if needed: {{"decision": "approved" or "rejected", "reasoning": string}}
"""


def approve_invoice(invoice, validation, client, model="grok-4-fast"):
    high_value = invoice["total"] is not None and invoice["total"] > 10000

    initial_response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": APPROVAL_PROMPT.format(invoice=invoice, validation=validation, high_value=high_value),
        }],
        response_format={"type": "json_object"},
    )
    initial_decision = json.loads(initial_response.choices[0].message.content)

    critique_response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": CRITIQUE_PROMPT.format(
                initial_decision=initial_decision, invoice=invoice, validation=validation
            ),
        }],
        response_format={"type": "json_object"},
    )
    final_decision = json.loads(critique_response.choices[0].message.content)

    return {
        "decision": final_decision["decision"],
        "reasoning": final_decision["reasoning"],
        "high_value_review": high_value,
        "initial_decision": initial_decision,  
    }