# AI Hotel Booking Agent

An AI travel agent that finds the cheapest hotel in a city by **actually phoning hotels**.
It searches Google Hotels, calls the cheapest places with an AI voice agent, reads the
call transcripts to find the lowest confirmed price, and emails the result.

Built for the TechTO hackathon (Team 13).

## How it works

```
User request ("cheapest hotel in Calgary, Nov 13–15, 1 guest")
   │
   ▼
Backboard AI agent ── decides which tool to use next
   │
   ├─ 1. search_stays            → SerpApi (Google Hotels): cheapest places with a phone number
   ├─ 2. call_accommodation      → ElevenLabs voice agent phones each hotel, saves the transcript
   ├─ 3. get_best_quote          → Claude Haiku reads every transcript, picks the lowest confirmed price
   └─ 4. send_confirmation_email → Gmail sends the winning hotel, dates and price
```

The AI never runs code itself. On each round it asks for a tool; `Agent/agent.py` runs it
and sends the result back, until the AI says it is done (max 15 rounds).

Transcripts and prices stay in Python and never go through the AI, so it can't mistype a price.
`get_best_quote` also rejects any price that doesn't actually appear in the transcript.

## Project structure

| Path | What it does |
|---|---|
| `Agent/agent.py` | Entry point. Creates the Backboard agent, sends the request, runs the tool loop. |
| `tools/tool_descriptions.json` | The tool "menu" the AI sees: names, descriptions, inputs. |
| `tools/pipeline_tools.py` | The functions the AI's tools map to. They save results between steps. |
| `tools/tools.py` | The real work: SerpApi search, ElevenLabs calls, recording download. |
| `tools/extract_info.py` | Uses Claude Haiku to extract hotel, price and reservation # from transcripts. |
| `tools/tool_parsing.py` | Loads `tool_descriptions.json`. |

## About this repo

Built at the TechTO hackathon (October 2026) by a team of five. Two of us wrote the code:
**Maryam Issakhani** and **Kevin Bryce**. The other three teammates shaped the idea, set up
and configured ElevenLabs and Twilio, got the API keys, shared resources in a team folder,
pushed code to GitHub and tested the system.

This is my (Maryam's) copy of the project. I pushed it as a single commit, with cleanup and
fixes I've made since the event. The original repo was maintained by one teammate, so its
commit history doesn't show who wrote what. The table below does.

### Who did what

| Part | Where | Written by |
|---|---|---|
| Hotel search (SerpApi) | `search_stays` and its helpers in `tools/tools.py` | Maryam |
| Reading transcripts with Claude Haiku | `tools/extract_info.py` | Maryam |
| Earlier rule-based price finder | `extract_lowest_quote` in `tools/tools.py` | Maryam |
| Confirmation email | `send_confirmation_email` in `tools/pipeline_tools.py` | Maryam |
| This README | `README.md` | Maryam |
| Pipeline (saves results, picks the cheapest quote) | rest of `tools/pipeline_tools.py` | Mostly Kevin, partly Maryam |
| Agent setup and tool loop | `Agent/agent.py` | Kevin |
| Tool definitions and loading | `tools/tool_descriptions.json`, `tools/tool_parsing.py`, `tool_caller/tool_calls.py` | Kevin |
| Phone calls (ElevenLabs) | `call_accommodation` in `tools/tools.py` | Kevin |
| Call recording download | `download_lowest_price_conversation` in `tools/tools.py` | Kevin, with help from the team |

### Changes since the hackathon

All by Maryam:

- Moved the secret keys out of the code and into `Agent/.env` (template: `Agent/.env.example`).
- Fixed mismatches between the tool names the AI sees (`tools/tool_descriptions.json`) and
  the Python functions they run (`tool_map` in `Agent/agent.py`).

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp Agent/.env.example Agent/.env
```

Then fill in `Agent/.env`:

| Key | Where to get it |
|---|---|
| `BACKBOARD_API_KEY` | [backboard.io](https://backboard.io) |
| `SERP_API_KEY` | [serpapi.com](https://serpapi.com) |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_PHONE_NUMBER_ID` | ElevenLabs Conversational AI. You need an agent plus a phone number with outbound calling enabled. |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `SMTP_USER`, `SMTP_PASSWORD` | A Gmail address plus a [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `RESULT_EMAIL` | *(optional)* Who receives the result. Default is `hackathon@techto.org`. |

## Run

From the project root:

```bash
python -m Agent.agent
```

To change the city, dates or guests, edit the request in `Agent/agent.py` (the `"content"` of
the first message). To call more hotels, change `how_many` in `search_and_save`
(`tools/pipeline_tools.py`). It is 2 by default; each extra hotel costs one more
SerpApi lookup and one more phone call.

## Notes

- **This places real phone calls** to real businesses. Test with a small `how_many`.
- Each call can take up to 6 minutes, and calls run one after another.
- Call results are kept in memory, so they are lost when the script stops.
