"""A hand-written tool-calling loop. No framework.

Day 3.

The idea: the model cannot DO anything. It can only ask you to do things.
You run the tool, hand back the result, and ask it what to do next.
That back-and-forth is the loop. Every "AI agent" is this underneath.

Run:
    py agent.py
    py agent.py --verbose
"""

import json
import sys
from datetime import datetime

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = "gemini-3.6-flash"
MAX_TURNS = 5          # safety cap so a confused model cannot loop forever

VERBOSE = "--verbose" in sys.argv


# =============================================================
# TOOL 1 - LOOK SOMETHING UP
# =============================================================
# A DICTIONARY stores labelled values: {"label": value, "label": value}.
# Same shape as JSON. Here: customer name -> their details.
# In a real system this would be a database query.

CUSTOMERS = {
    "acme corp": {
        "plan": "Enterprise",
        "monthly_value": 4200,
        "open_tickets": 3,
        "account_manager": "Priya",
    },
    "globex": {
        "plan": "Starter",
        "monthly_value": 99,
        "open_tickets": 0,
        "account_manager": "Manish",
    },
}


def lookup_customer(name: str) -> str:
    """Find a customer. Returns text the model can read."""
    # .lower() so "ACME Corp" and "acme corp" both match.
    record = CUSTOMERS.get(name.lower())

    # .get() returns None instead of crashing when the key is missing.
    if record is None:
        return f"No customer found named '{name}'. Known customers: {list(CUSTOMERS)}"

    return json.dumps(record)


# =============================================================
# TOOL 2 - DO SOMETHING
# =============================================================
# Tool 1 only reads. This one changes the world - it writes a file.
# That distinction matters: a tool that acts needs more care than one
# that only looks.

def log_note(text: str) -> str:
    """Append a note to notes_log.txt."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # "a" = append (add to the end). "w" would erase the file first.
    with open("notes_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {text}\n")

    return f"Note logged at {stamp}"

def list_customers() -> str:
    """Return every customer name we know about."""
    return json.dumps(list(CUSTOMERS.keys()))

# =============================================================
# TELLING THE MODEL WHAT TOOLS EXIST
# =============================================================
# The model never sees your Python. It sees these descriptions.
# The description is the instruction manual - a vague one means the
# model picks the wrong tool. This is real engineering work.

TOOLS = [
    {
        "type": "function",
        "name": "lookup_customer",
        "description": (
            "Look up a customer's account details: plan, monthly value, "
            "open ticket count, and account manager. Use when asked about "
            "a specific customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The customer's company name, e.g. 'Acme Corp'",
                }
            },
            "required": ["name"],
        },
    },
    {
        "type": "function",
        "name": "log_note",
        "description": (
            "Write a note to the permanent log file. Use when asked to "
            "record, log, or save something."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The note to record",
                }
            },
            "required": ["text"],
        },
    },
    {
    "type": "function",
    "name": "list_customers",
    "description": "List every customer name in the system. Use when asked which customers exist.",
    "parameters": {"type": "object", "properties": {}},
},
]


# =============================================================
# THE DISPATCHER
# =============================================================
# The model asks for a tool BY NAME. This turns that name into an
# actual function call. Note it never runs arbitrary code - only the
# two functions listed here. That is deliberate.

def run_tool(name: str, arguments: dict) -> str:
    if name == "lookup_customer":
        return lookup_customer(arguments["name"])
    if name == "log_note":
        return log_note(arguments["text"])
    if name == "list_customers":
        return list_customers()
    return f"Unknown tool: {name}"


# =============================================================
# THE LOOP
# =============================================================
# 1. Send the question, with the list of available tools
# 2. Look at the reply. Did it ask for a tool?
#      no  -> it answered. Done.
#      yes -> run the tool, send the result back, go to step 2
# 3. Stop after MAX_TURNS no matter what

client = genai.Client()


def agent(question: str, verbose: bool = VERBOSE) -> str:
    print(f"\nQUESTION: {question}\n")

    # THE CONVERSATION HISTORY.
    # The API has no memory between calls. Every turn we send the whole
    # conversation so far. It starts with the user's question and grows
    # as the model thinks, requests tools, and reads the results.
    history = [
        {"type": "user_input", "content": [{"type": "text", "text": question}]}
    ]

    for turn in range(1, MAX_TURNS + 1):

        interaction = client.interactions.create(
            model=MODEL,
            input=history,
            tools=TOOLS,
        )

        if verbose:
            print(f"--- turn {turn}: raw steps ---")
            for step in interaction.steps:
                print(f"    {step}")
            print("--- end raw ---")

        # Append everything the model produced this turn - including its
        # 'thought' steps. Those carry a signature the model needs to see
        # again on the next turn, so they must not be dropped.
        history.extend(interaction.steps)

        # Collect any tool requests from this reply.
        # A LIST COMPREHENSION: "give me every step whose type is function_call"
        calls = [s for s in interaction.steps if getattr(s, "type", None) == "function_call"]

        # No tool requested means the model is finished.
        if not calls:
            answer = interaction.output_text
            print(f"[turn {turn}] model answered directly")
            return answer

        # Otherwise run each requested tool and add its result to history.
        for call in calls:
            print(f"[turn {turn}] model wants: {call.name}({call.arguments})")
            output = run_tool(call.name, call.arguments)
            print(f"[turn {turn}] tool returned: {output}")

            # call_id must match the id from the request, so the model
            # knows which of its questions this answers.
            history.append({
                "type": "function_result",
                "call_id": call.id,
                "name": call.name,
                "result": output,
            })

    return f"Stopped after {MAX_TURNS} turns without a final answer."


# =============================================================
# TRY IT
# =============================================================

if __name__ == "__main__":
    print("=" * 60)
    answer = agent("What plan is Acme Corp on, and how many open tickets do they have?")
    print(f"\nANSWER: {answer}")

    print("\n" + "=" * 60)
    answer = agent("Which customers do we have, and which one is worth more per month?")
    print(f"\nANSWER: {answer}")
