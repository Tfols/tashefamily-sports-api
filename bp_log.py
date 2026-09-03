"""Inbound SMS endpoint for logging blood pressure readings to a Google Sheet.

Text a reading to the Twilio number and it lands in the sheet. Voice-to-text
friendly: "BP 128 over 82" parses the same as "128/82".

SECURITY: this endpoint is publicly reachable and writes to a health record, so
it enforces two independent checks before accepting anything —

  1. Twilio's request signature (proves the request came from Twilio at all)
  2. A sender allowlist (proves it came from Tom's phone specifically)

Both must pass. Either alone is insufficient: the signature check would still
accept a text from any stranger who found the number, and the sender check
alone could be spoofed by anyone POSTing to the URL directly.

Required environment variables:
  TWILIO_AUTH_TOKEN            - for signature validation
  BP_ALLOWED_SENDER            - E.164 number permitted to log, e.g. +12154602423
  BP_SHEET_ID                  - target Google Sheet ID
  GOOGLE_SERVICE_ACCOUNT_JSON  - service account key, full JSON as a string
  BP_SHEET_RANGE               - optional, defaults to "Readings!A:F"
"""

import json
import os
import re
from datetime import datetime

import pytz
from flask import Blueprint, Response, request

ET = pytz.timezone("America/New_York")

bp_log = Blueprint("bp_log", __name__)

# Matches: "128/82", "BP 128/82", "bp 128 over 82", "128/82 64",
# "128/82 p64", "128/82 pulse 64". Pulse is optional.
READING_RE = re.compile(
    r"(?:bp\s*)?"
    r"(\d{2,3})\s*(?:/|\\|over)\s*(\d{2,3})"
    r"(?:\s*(?:p|pulse)?\s*(\d{2,3}))?",
    re.IGNORECASE,
)

# Ranges chosen to catch transcription errors, not to make clinical judgments.
# A value outside these is far more likely a mis-parse than a real reading.
SYSTOLIC_RANGE = (70, 250)
DIASTOLIC_RANGE = (40, 150)
PULSE_RANGE = (30, 220)


def _twiml(message):
    """Minimal TwiML reply. Avoids a dependency just to build two tags."""
    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>',
        mimetype="application/xml",
    )


def _signature_ok():
    """Verify the request genuinely originated from Twilio."""
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    signature = request.headers.get("X-Twilio-Signature", "")
    if not token or not signature:
        return False
    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        # Fail closed. A missing dependency must never mean "accept anything".
        return False
    # Railway terminates TLS upstream, so Flask sees http:// while Twilio signed
    # the https:// URL. Rebuild the external URL for signature comparison.
    url = request.url.replace("http://", "https://", 1)
    return RequestValidator(token).validate(url, request.form.to_dict(), signature)


def parse_reading(text):
    """Return (systolic, diastolic, pulse|None) or None if unparseable."""
    if not text:
        return None
    match = READING_RE.search(text)
    if not match:
        return None

    systolic, diastolic = int(match.group(1)), int(match.group(2))
    pulse = int(match.group(3)) if match.group(3) else None

    if not (SYSTOLIC_RANGE[0] <= systolic <= SYSTOLIC_RANGE[1]):
        return None
    if not (DIASTOLIC_RANGE[0] <= diastolic <= DIASTOLIC_RANGE[1]):
        return None
    if systolic <= diastolic:
        # Almost certainly a transposition or mis-parse.
        return None
    if pulse is not None and not (PULSE_RANGE[0] <= pulse <= PULSE_RANGE[1]):
        pulse = None

    return systolic, diastolic, pulse


def append_to_sheet(row):
    """Append one row to the configured sheet. Raises on failure."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    service.spreadsheets().values().append(
        spreadsheetId=os.environ["BP_SHEET_ID"],
        range=os.environ.get("BP_SHEET_RANGE", "Readings!A:F"),
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


@bp_log.route("/sms/bp", methods=["POST"])
def sms_bp():
    if not _signature_ok():
        # Deliberately terse: don't tell an unauthenticated caller why it failed.
        return Response("forbidden", status=403)

    sender = request.form.get("From", "")
    allowed = os.environ.get("BP_ALLOWED_SENDER", "")
    if not allowed or sender != allowed:
        # Silent to the sender — no reply body, so a stranger texting the number
        # learns nothing about what this endpoint does.
        return Response("", status=204)

    body = (request.form.get("Body") or "").strip()
    parsed = parse_reading(body)
    if not parsed:
        return _twiml(
            "Couldn't read that. Try: 128/82  or  BP 128 over 82  or  128/82 p64"
        )

    systolic, diastolic, pulse = parsed
    now = datetime.now(ET)
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        systolic,
        diastolic,
        pulse if pulse is not None else "",
        body,  # original text, so a mis-parse can be reconstructed later
    ]

    try:
        append_to_sheet(row)
    except Exception:
        # Echo the reading back so it isn't lost if the sheet write failed —
        # Tom can re-enter it manually. Exception detail is deliberately not
        # returned to the sender.
        return _twiml(
            f"Sheet write FAILED. Reading not saved: {systolic}/{diastolic}"
            + (f" p{pulse}" if pulse else "")
        )

    confirmation = f"Logged {systolic}/{diastolic}"
    if pulse:
        confirmation += f" p{pulse}"
    confirmation += f" at {now.strftime('%-I:%M%p').lower()}"
    return _twiml(confirmation)
