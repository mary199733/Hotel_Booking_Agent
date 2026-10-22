import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from tools.tool_parsing import TOOL_DEFINITIONS
from tool_caller.tool_calls import *
import tools.tools as tools

API_KEY = os.getenv("BACKBOARD_API_KEY")
if not API_KEY:
    raise RuntimeError("BACKBOARD_API_KEY is missing from Agent/.env")
BASE_URL = "https://app.backboard.io/api"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

TRAVEL_AGENT_SYSTEM_PROMPT = """
You are a travel agent finding the cheapest stay in the city the user asks about.
Always use the tools, in this order:

1. search_stays: search the city for the user's dates. It returns a short list of places,
   each with a name and phone number.
2. call_accommodation: call EVERY place from step 1, one call per place. Use the place's
   name as company_name, its exact phone number, the user's dates and guest count, and a
   short ID like "1", "2" as building_id. You will only get back the call status, not the
   transcript; that is expected.
3. get_best_quote: after all calls are done, call it once (no inputs). It reads all call
   transcripts and picks the lowest confirmed price.
4. send_confirmation_email: if get_best_quote found a price, call it with the user's
   start_date and end_date. It emails the winning hotel, dates and price.

Rules:
- Dates are always YYYY-MM-DD.
- If one call fails, keep calling the other places. Only stop early if search_stays
  returns no places, or every call fails.
- Never make up prices, hotel names or phone numbers; only use what the tools return.
- If get_best_quote finds no price, do not send the email; say no hotel confirmed a price.
- When done, reply with a short summary: which hotel won, the price, and whether the
  email was sent. If a step failed, say which tool failed and why.
"""
import tools.pipeline_tools as pipe

tool_map = {
    "search_stays": pipe.search_and_save,
    "call_accommodation": pipe.call_and_save,
    "get_best_quote": pipe.get_best_quote,
    "send_confirmation_email": pipe.send_confirmation_email,
    "download_lowest_price_conversation": pipe.download_lowest_price_conversation,
}

agent = requests.post(
    f"{BASE_URL}/assistants",
    headers=HEADERS,
    json={
        "name": "Travel Agent",
        "system_prompt": TRAVEL_AGENT_SYSTEM_PROMPT,
        "tools": TOOL_DEFINITIONS,
    }
)

agent.raise_for_status()
assistant = agent.json()
assistant_id = assistant["assistant_id"]
print("do you make it here?")

query_response = requests.post(
    f"{BASE_URL}/threads/messages",
    headers=HEADERS,
    json={
        "assistant_id": assistant_id,
        "content": "Find the cheapest hotel in Calgary, Alberta for 1 guest, "
                   "checking in 2026-11-13 and checking out 2026-11-15 (2 nights)."
    },
)
result = query_response.json()
# query_response.raise_for_status()
# result = query_response.json()
# print(result["content"])
# print("Created travel agent:", assistant_id)



thread_id = result["thread_id"]
print("Created travel agent:", assistant_id)
print("Thread ID:", thread_id)

MAX_ROUNDS = 15

for round_number in range(MAX_ROUNDS):
    print(f"\n--- Agent round {round_number + 1} ---")
    print("Status:", result.get("status"))

    # The model has finished.
    if result.get("status") == "COMPLETED":
        print("\nFINAL ANSWER:")
        print(result.get("content") or "")
        break

    if result.get("status") == "FAILED":
        raise RuntimeError(f"Backboard run failed: {result}")

    # The model wants us to execute tools.
    if result.get("status") != "REQUIRES_ACTION":
        raise RuntimeError(
            f"Unexpected status: {result.get('status')}. "
            f"Full response: {result}"
        )

    tool_calls = result.get("tool_calls", [])

    if not tool_calls:
        raise RuntimeError("No tool calls found in REQUIRES_ACTION response.")

    tool_outputs = []

    for tool_call in tool_calls:
        function = tool_call["function"]
        tool_name = function["name"]
        arguments = function["arguments"]

        if isinstance(arguments, str):
            arguments = json.loads(arguments)

        print(f"\nCalling tool: {tool_name}")
        print("Arguments:", arguments)

        try:
            tool = tool_map.get(tool_name)

            if tool is None:
                raise ValueError(f"Unknown tool: {tool_name}")

            output = tool(**arguments)

        except Exception as exc:
            output = {
                "success": False,
                "tool": tool_name,
                "error": str(exc),
            }

        print("Tool output:", output)

        tool_outputs.append({
            "tool_call_id": tool_call["id"],
            "output": json.dumps(output, default=str),
        })

    # Send results back so Backboard can continue reasoning.
    continuation = requests.post(
        f"{BASE_URL}/threads/tool-outputs",
        headers=HEADERS,
        json={
            "thread_id": thread_id,
            "tool_outputs": tool_outputs,
        },
        timeout=120,
    )

    continuation.raise_for_status()
    result = continuation.json()

else:
    raise RuntimeError(
        f"Agent did not finish within {MAX_ROUNDS} rounds."
    )
