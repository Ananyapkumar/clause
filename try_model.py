"""Test whether a model works and has quota left. Costs ONE request.

Free-tier daily quotas differ enormously between Gemini models. Before
committing a 7-document eval run to a model, spend one request finding out
whether it answers at all.

Run:
    py try_model.py gemini-2.5-flash-lite
    py try_model.py gemini-2.5-flash

If it succeeds, put the winner in .env:
    GEMINI_MODEL=gemini-2.5-flash-lite
"""

import sys
import time

from dotenv import load_dotenv
from google import genai

from schema import build_json_schema

load_dotenv()

if len(sys.argv) < 2:
    print(__doc__)
    raise SystemExit(1)

model_name = sys.argv[1]

# A tiny datasheet. Small enough to cost almost nothing, real enough that a
# working model returns something recognisable.
TEST_DOC = """ACME TEST LUMINAIRE
Order code: TEST-001
System wattage        20 W
Luminous flux         2000 lm
Colour temperature    4000 K
CRI                   Ra 80
Beam angle            60 degrees
IP rating             IP20
Rated life L80/B10    50000 h
Dimming               Non-dimmable"""

print(f"Testing: {model_name}")
print("Cost: 1 request\n")

client = genai.Client()
started = time.perf_counter()

try:
    interaction = client.interactions.create(
        model=model_name,
        input="Extract the fields from this datasheet.\n\n" + TEST_DOC,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": build_json_schema(True),
        },
    )
except Exception as err:
    message = str(err)
    print("FAILED\n")
    if "429" in message or "quota" in message.lower():
        print("  Rate limited or out of quota on this model.")
        print("  Either the daily allowance is spent, or this model has a")
        print("  low free-tier limit. Try a different one.")
    elif "404" in message or "not found" in message.lower():
        print(f"  Model '{model_name}' does not exist or is unavailable to")
        print("  your key. Check the exact name at:")
        print("  https://ai.google.dev/gemini-api/docs/models")
    else:
        print(f"  {message[:400]}")
    raise SystemExit(1)

elapsed = int((time.perf_counter() - started) * 1000)
usage = interaction.usage

print("WORKS\n")
print(f"  latency        {elapsed} ms")
if usage:
    print(f"  input tokens   {usage.total_input_tokens}")
    print(f"  output tokens  {usage.total_output_tokens}")
print(f"\n  response: {interaction.output_text[:200]}")
print(f"\nTo use it, add this line to .env:")
print(f"  GEMINI_MODEL={model_name}")
