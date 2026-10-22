"""
tools/pipeline_tools.py
Connects: search -> calls -> extract_info -> email.

Idea: the AI never copies transcripts or prices around.
Our code SAVES every search result and call, then reads them back itself.
"""
import os
import re
import smtplib
from email.message import EmailMessage

import pandas as pd

import tools.tools as base
from tools.extract_info import extract_all

TEAM_NUMBER = 13
RECIPIENT = os.getenv("RESULT_EMAIL", "hackathon@techto.org")  # change when they give the email

ADDRESSES = {}   # hotel name -> address (saved from search)
CALL_LOG = []    # every finished call (saved from calls)
BEST = {}        # the winner (saved by get_best_quote)


def _e164(phone):
    """'+1 555-123-4567' -> '+15551234567' (ElevenLabs needs this)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:          # North American number without the 1
        digits = "1" + digits
    return "+" + digits


# ---------- 1. Search: same as before, but remember addresses ----------
def search_and_save(city, start_date, end_date, bedrooms=None, how_many=2):
    hotels = base.search_stays(city, start_date, end_date, bedrooms=bedrooms, how_many=how_many)
    for h in hotels:
        h["phone"] = _e164(h["phone"])
        ADDRESSES[h["name"]] = h["address"]
    return hotels


# ---------- 2. Call: same as before, but remember the result ----------
def call_and_save(building_id, company_name, phone_number, start_date, end_date, guest_count):
    result = base.call_accommodation(
        building_id=building_id, company_name=company_name,
        phone_number=_e164(phone_number), start_date=start_date,
        end_date=end_date, guest_count=guest_count,
    )
    result["phone"] = _e164(phone_number)
    CALL_LOG.append(result)
    # Give the AI a short answer, not the whole transcript (saves tokens).
    return {"company_name": company_name, "call_status": result.get("call_status"),
            "error": result.get("error")}


# ---------- 3. Extract: run extract_info on ALL saved calls, pick cheapest ----------
def get_best_quote():
    if not CALL_LOG:
        return {"status": "no_calls", "message": "No calls have been made yet."}

    calls = [{"conversation_id": c.get("call_id") or c.get("building_id"),
              "transcript": c.get("transcript") or ""} for c in CALL_LOG]
    table = extract_all(calls)

    # Trust what WE dialed over what the AI heard.
    table["hotel_name"] = [c.get("company_name") for c in CALL_LOG]
    table["phone"] = [c.get("phone") for c in CALL_LOG]
    table["hotel_address"] = [ADDRESSES.get(c.get("company_name")) or a
                              for c, a in zip(CALL_LOG, table["hotel_address"])]
    table = table.astype(object).where(pd.notna(table), None)   # NaN -> None
    print(table.to_string(index=False))

    priced = [r for r in table.to_dict("records") if r["final_price"] is not None]
    if not priced:
        return {"status": "no_price", "message": "No call confirmed a price.",
                "calls": table.to_dict("records")}

    BEST.clear()
    BEST.update(min(priced, key=lambda r: r["final_price"]))
    return {"status": "success", "best": BEST}


# ---------- 4. Email: uses the saved winner, never numbers typed by the AI ----------
def send_confirmation_email(start_date, end_date):
    if not BEST:
        return {"success": False, "error": "Run get_best_quote first."}

    sender = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not sender or not password:
        return {"success": False, "error": "SMTP_USER / SMTP_PASSWORD missing in .env"}

    msg = EmailMessage()
    msg["Subject"] = f"Team # {TEAM_NUMBER} - Hotel Reservation Confirmed!"
    msg["From"] = sender
    msg["To"] = RECIPIENT
    msg.set_content(
        f"Hotel Name: {BEST['hotel_name']}\n"
        f"Address: {BEST['hotel_address'] or 'Not available'}\n"
        f"Phone: {BEST['phone']}\n"
        f"Reservation #: {BEST['reservation_number'] or 'Not provided'}\n"
        f"Reservation Date: {start_date} to {end_date}\n"
        f"Price: {BEST['final_price']}\n"
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(sender, password)
            server.send_message(msg)
        return {"success": True, "sent_to": RECIPIENT, "hotel": BEST["hotel_name"]}
    except (smtplib.SMTPException, OSError) as exc:
        return {"success": False, "error": str(exc)}


# ---------- 5. Download recording: same as before (saves the call audio as .mp3) ----------
def download_lowest_price_conversation(conversation_id, output_dir="recordings"):
    return base.download_lowest_price_conversation(conversation_id, output_dir)
