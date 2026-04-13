"""
document_parser.py
Parses BOL and cargo claim documents (text, PDF, image) into structured JSON.
Returns BOLData or ClaimData matching the exact schema the Carmack engine expects.
"""

import os
import json
import base64
import re
from typing import Literal
import anthropic
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic client ──────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"

# ── Schemas (kept here so parser is self-contained for teammates) ─────────────
BOL_SCHEMA = {
    "bol_number": "string or null",
    "date": "string YYYY-MM-DD or null",
    "shipper": {"name": "string or null", "address": "string or null"},
    "carrier": {"name": "string or null", "mc_number": "string or null"},
    "consignee": {"name": "string or null", "address": "string or null"},
    "origin": "string or null",
    "destination": "string or null",
    "commodity_description": "string or null",
    "weight_lbs": "float or null",
    "num_pieces": "integer or null",
    "declared_value": "float or null",
    "released_value_notation": "string or null — the exact text found on the BOL e.g. '$0.10 per pound'",
    "released_value_per_lb": "float or null — parse the dollar amount from released_value_notation",
    "slc_notation": "boolean — true if ANY of: 'Shipper Load and Count', 'SL&C', 'SLC', 'loaded and counted by shipper', 'shipper packed', 'By Shipper' checked under Freight Counted or Trailer Loaded, 'Freight Counted By Shipper'",
    "special_instructions": "string or null",
    "hazmat": "boolean",
    "signatures": {
        "shipper_signed": "boolean",
        "carrier_signed": "boolean",
        "consignee_signed": "boolean"
    },
    "noted_exceptions_at_pickup": "string or null — any damage/condition notes the driver wrote",
    "raw_text": "string — full extracted text",
    "parse_confidence": "high | medium | low"
}

CLAIM_SCHEMA = {
    "claimant": "string or null",
    "claim_date": "string YYYY-MM-DD or null",
    "claim_amount": "float — MUST have this",
    "bol_reference": "string or null",
    "delivery_date": "string YYYY-MM-DD or null",
    "damage_description": "string or null",
    "damage_type": "one of: water | crush | temperature | theft | shortage | contamination | other | null",
    "items_damaged": "integer or null",
    "items_total": "integer or null",
    "packaging_description": "string or null — any mention of how goods were packaged",
    "inspection_notes": "string or null",
    "supporting_docs_mentioned": "list of strings — e.g. ['photos', 'invoice']",
    "raw_text": "string — full extracted text",
    "parse_confidence": "high | medium | low"
}

# ── System prompts ─────────────────────────────────────────────────────────────
def _bol_system_prompt() -> str:
    return f"""You are a freight document parser specializing in Bills of Lading (BOL).
Extract structured data from the provided document.

CRITICAL FIELDS TO FIND (engine breaks without these):
- released_value_notation: Look for phrases like "released value", "declared value not exceeding",
  "liability limited to $X per pound", "$.10 per pound per article". Often in fine print or
  pre-printed terms. Extract the EXACT text found.
- released_value_per_lb: Parse the dollar amount from released_value_notation. "$0.50 per pound" → 0.50
- slc_notation: Look for ANY of: "Shipper Load and Count", "SL&C", "SLC", "Shipper Load & Count",
  "loaded and counted by shipper", "shipper packed", "By Shipper" checked under Freight Counted or
  Trailer Loaded sections, "Freight Counted By Shipper". Can appear anywhere — body, checkbox, special
  instructions, or signature section. IMPORTANT: On standard printed BOL forms, a checked box [X] next
  to "By Shipper" under "Freight Counted" or "Trailer Loaded" IS a SLC notation — set slc_notation true.
- weight_lbs: Usually in a column labeled "Weight" in lbs or kg. Convert kg to lbs if needed (1 kg = 2.205 lbs).
- noted_exceptions_at_pickup: Any condition/damage notes the driver wrote at pickup, e.g. "damaged packaging",
  "wet boxes", "torn shrink wrap".

IMPORTANT RULES:
- Return ONLY valid JSON matching this exact schema. No preamble, no markdown fences.
- If a field cannot be determined from the document, use null. Do NOT guess or infer.
- A wrong released_value_per_lb would completely break the liability calculation.
- For parse_confidence: "high" = document clearly readable and fields found,
  "medium" = some fields missing or ambiguous, "low" = document garbled or very incomplete.

EXACT SCHEMA TO RETURN:
{json.dumps(BOL_SCHEMA, indent=2)}"""


def _claim_system_prompt() -> str:
    return f"""You are a freight document parser specializing in cargo damage claims.
Extract structured data from the provided document.

CRITICAL FIELDS TO FIND:
- claim_amount: The dollar amount being claimed. MUST extract this.
- claim_date: Date the claim was filed (YYYY-MM-DD).
- delivery_date: Date of delivery (YYYY-MM-DD) — needed to calculate the 9-month filing deadline.
- damage_type: Classify from the description into one of: water, crush, temperature, theft,
  shortage, contamination, other.
- damage_description: Full description of the damage — keywords like "packaging", "moisture",
  "temperature" trigger specific legal defenses.
- packaging_description: If the claim mentions how goods were packaged, extract it.
  "Standard cardboard boxes" for electronics suggests shipper negligence.

IMPORTANT RULES:
- Return ONLY valid JSON matching this exact schema. No preamble, no markdown fences.
- If a field cannot be determined, use null. Do NOT guess or infer.
- For parse_confidence: "high" = clear document with all key fields,
  "medium" = some missing/ambiguous, "low" = very incomplete.

EXACT SCHEMA TO RETURN:
{json.dumps(CLAIM_SCHEMA, indent=2)}"""


# ── Text extraction from PDF ───────────────────────────────────────────────────
def _extract_text_from_pdf(file_bytes: bytes) -> str:
    import io
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


# ── Validation ─────────────────────────────────────────────────────────────────
def _validate_and_fix(data: dict, document_type: str) -> dict:
    """Basic sanity checks. Sets parse_confidence to low if critical fields broken."""
    if document_type == "bol":
        # weight must be positive if present
        if data.get("weight_lbs") is not None and data["weight_lbs"] <= 0:
            data["weight_lbs"] = None
            data["parse_confidence"] = "low"
        # released_value_per_lb must be positive if present
        if data.get("released_value_per_lb") is not None and data["released_value_per_lb"] <= 0:
            data["released_value_per_lb"] = None
            data["parse_confidence"] = "low"
        # slc_notation must be bool
        if not isinstance(data.get("slc_notation"), bool):
            data["slc_notation"] = False
        # hazmat must be bool
        if not isinstance(data.get("hazmat"), bool):
            data["hazmat"] = False
        # signatures defaults
        if not isinstance(data.get("signatures"), dict):
            data["signatures"] = {"shipper_signed": False, "carrier_signed": False, "consignee_signed": False}

    elif document_type == "claim":
        # claim_amount must be positive
        if not data.get("claim_amount") or data["claim_amount"] <= 0:
            data["parse_confidence"] = "low"
        # damage_type must be valid enum
        valid_types = {"water", "crush", "temperature", "theft", "shortage", "contamination", "other"}
        if data.get("damage_type") not in valid_types:
            data["damage_type"] = None
        # supporting_docs_mentioned must be list
        if not isinstance(data.get("supporting_docs_mentioned"), list):
            data["supporting_docs_mentioned"] = []

    return data


# ── JSON parsing ──────────────────────────────────────────────────────────────
def _parse_json_response(raw: str) -> dict:
    """Parse Claude's JSON response, handling common issues."""
    # Strip markdown fences if Claude added them despite instructions
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)

    # First try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fix unescaped newlines inside JSON string values.
    # Walk character by character: when inside a quoted string,
    # replace literal newlines with \\n so json.loads() can handle them.
    fixed = []
    in_string = False
    escape_next = False
    for ch in raw:
        if escape_next:
            fixed.append(ch)
            escape_next = False
            continue
        if ch == '\\' and in_string:
            fixed.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            fixed.append(ch)
            continue
        if in_string and ch == '\n':
            fixed.append('\\n')
            continue
        if in_string and ch == '\r':
            continue
        if in_string and ch == '\t':
            fixed.append('\\t')
            continue
        fixed.append(ch)

    return json.loads("".join(fixed))


# ── Core LLM call ──────────────────────────────────────────────────────────────
def _call_claude_text(system: str, text: str) -> dict:
    """Call Claude with plain text content."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": f"Parse this document:\n\n{text}"}]
    )
    return _parse_json_response(response.content[0].text)


def _call_claude_image(system: str, file_bytes: bytes, media_type: str) -> dict:
    """Call Claude with image content (vision API)."""
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64}
                },
                {"type": "text", "text": "Parse this document and return the JSON schema requested."}
            ]
        }]
    )
    return _parse_json_response(response.content[0].text)


# ── Public interface ───────────────────────────────────────────────────────────
async def parse_document(
    file_bytes: bytes,
    file_type: Literal["pdf", "image", "text"],
    document_type: Literal["bol", "claim"]
) -> dict:
    """
    Parse a BOL or cargo claim document into structured JSON.

    Args:
        file_bytes: Raw bytes of the file (or encoded text as bytes for file_type="text")
        file_type:  "text" | "pdf" | "image"
        document_type: "bol" | "claim"

    Returns:
        dict matching BOLData or ClaimData schema
    """
    system = _bol_system_prompt() if document_type == "bol" else _claim_system_prompt()

    if file_type == "text":
        text = file_bytes.decode("utf-8")
        data = _call_claude_text(system, text)
        if "raw_text" not in data or not data["raw_text"]:
            data["raw_text"] = text

    elif file_type == "pdf":
        text = _extract_text_from_pdf(file_bytes)
        if text.strip():
            # Text-extractable PDF — cheaper and more reliable than vision
            data = _call_claude_text(system, text)
            if "raw_text" not in data or not data["raw_text"]:
                data["raw_text"] = text
        else:
            # Scanned PDF — render first page to image, send to Claude vision
            import io
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_bytes)
            page = pdf[0]
            bitmap = page.render(scale=2)  # 2x for readability
            pil_image = bitmap.to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="JPEG", quality=85)
            data = _call_claude_image(system, buf.getvalue(), "image/jpeg")
            data["raw_text"] = data.get("raw_text", "[scanned PDF — OCR via vision]")

    elif file_type == "image":
        # Detect media type from magic bytes
        if file_bytes[:4] == b'\x89PNG':
            media_type = "image/png"
        elif file_bytes[:2] == b'\xff\xd8':
            media_type = "image/jpeg"
        elif file_bytes[:4] == b'GIF8':
            media_type = "image/gif"
        else:
            media_type = "image/jpeg"  # safe default
        data = _call_claude_image(system, file_bytes, media_type)
        data["raw_text"] = data.get("raw_text", "[image input]")

    else:
        raise ValueError(f"Unknown file_type: {file_type}. Must be 'text', 'pdf', or 'image'.")

    return _validate_and_fix(data, document_type)


# ── Quick smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    # Scenario A BOL: SL&C marked, no released value, $22K declared
    sample_bol = """
    BILL OF LADING — BOL-2026-44821
    Date: 2026-03-15
    Shipper: ABC Electronics Inc., 1200 Commerce Blvd, Los Angeles, CA 90012
    Carrier: FastFreight LLC  MC#: MC-123456
    Consignee: XYZ Retail Corp, 500 Distribution Dr, Dallas, TX 75201
    Origin: Los Angeles, CA   Destination: Dallas, TX
    Commodity: Consumer electronics – laptops, 24 units
    Weight: 800 lbs   Pieces: 24   Declared Value: $22,000.00
    Special Instructions: Keep dry, fragile, do not stack
    [SHIPPER LOAD AND COUNT]
    Shipper signature: ✓    Carrier signature: ✓    Consignee signature: —
    """.strip()

    result = asyncio.run(parse_document(sample_bol.encode(), "text", "bol"))
    print("=== BOL PARSE RESULT ===")
    print(json.dumps(result, indent=2))

    # Scenario A Claim
    sample_claim = """
    CARGO CLAIM NOTICE
    Claimant: ABC Electronics Inc.
    Claim Date: 2026-04-01
    BOL Reference: BOL-2026-44821
    Delivery Date: 2026-03-18
    Claim Amount: $22,000.00
    Description: Water damage to 12 of 24 laptop units. Units found with moisture
    inside packaging upon delivery. Standard cardboard boxes, no waterproofing,
    no moisture barrier used by shipper.
    Damage Type: water
    Supporting Documents: photos, invoice, inspection report
    """.strip()

    result2 = asyncio.run(parse_document(sample_claim.encode(), "text", "claim"))
    print("\n=== CLAIM PARSE RESULT ===")
    print(json.dumps(result2, indent=2))