import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from tools import check_inventory, check_total_math

load_dotenv()

grok_llm = LLM(
    model="xai/grok-4-fast",  # native xAI provider prefix, not "openai/"
    api_key=os.environ.get("GROK_API_KEY", ""),
)


def build_validation_crew(invoice):
    validator = Agent(
        role="Invoice Validation Specialist",
        goal="Check every line item against inventory and verify the invoice math is correct",
        backstory="You are meticulous and never approve an invoice without checking every item and every number.",
        tools=[check_inventory, check_total_math],
        llm=grok_llm,
        verbose=True,
    )

    items_list = "\n".join(f"- {i['item']}: qty {i['qty']}" for i in invoice["items"])

    task = Task(
        description=f"""Validate this invoice using your tools.

Items to check (use check_inventory on EACH one):
{items_list}

Also use check_total_math with subtotal={invoice.get('subtotal')}, tax={invoice.get('tax')}, stated_total={invoice.get('total')}.

After checking everything, summarize: is this invoice clean, or does it have issues?
List every issue found. If subtotal or tax is None, skip the math check and note that.""",
        expected_output="A summary listing each item's status and the total math check result, followed by an overall PASS or FAIL verdict with reasons.",
        agent=validator,
    )

    return Crew(agents=[validator], tasks=[task], verbose=True)


def run_validation(invoice):
    crew = build_validation_crew(invoice)
    result = crew.kickoff()
    return str(result)