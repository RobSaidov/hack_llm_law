"""
LoadShield — Dispute Letter Generator
Uses Claude claude-sonnet-4-20250514 to generate a formal Carmack dispute letter.

Input:  CarmackAnalysis + BOLData + ClaimData
Output: DisputeLetter (letter text + citations list)
"""

import os
import anthropic
from dotenv import load_dotenv
from models import (
    CarmackAnalysis, BOLData, ClaimData, DisputeLetter, RecommendedPosition,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ─── Verified citations — only these may appear in letters ───────────────────

VERIFIED_CITATIONS = [
    "49 U.S.C. § 14706",
    "Missouri Pacific R.R. Co. v. Elmore & Stahl, 377 U.S. 134 (1964)",
    "Southeastern Express Co. v. Pastime Amusement Co., 299 U.S. 28 (1935)",
    "Rini v. United Van Lines, 104 F.3d 502 (1st Cir. 1997)",
    "Nemf v. AAMCO Transmissions, 135 F.3d 57 (2d Cir. 1998)",
]

SYSTEM_PROMPT = """You are a senior transportation attorney specializing in Carmack Amendment (49 U.S.C. § 14706) cargo claim disputes. Write a formal dispute letter from the carrier to the claimant. The letter must be professional, cite specific legal provisions, and be ready to send without edits.

Rules:
- ONLY cite these verified cases, do not invent others:
  * 49 U.S.C. § 14706 (Carmack Amendment)
  * Missouri Pacific R.R. Co. v. Elmore & Stahl, 377 U.S. 134 (1964)
  * Southeastern Express Co. v. Pastime Amusement Co., 299 U.S. 28 (1935)
  * Rini v. United Van Lines, 104 F.3d 502 (1st Cir. 1997)
  * Nemf v. AAMCO Transmissions, 135 F.3d 57 (2d Cir. 1998)
- Only cite cases that are relevant to the defenses being invoked
- Format as a proper business letter with date, addresses, re: line, body, closing
- Be firm but professional
- Include the specific dollar figures and calculations
- Do NOT invent any case citations beyond the five listed above
- Write the letter text only — no commentary or meta-text before or after"""


def _build_user_prompt(
    analysis: CarmackAnalysis,
    bol: BOLData,
    claim: ClaimData,
    carrier_contact_name: str | None,
) -> str:
    lib = analysis.liability
    pos = lib.recommended_position

    lines = [
        "Generate a formal Carmack Amendment dispute letter using the following case data:",
        "",
        "=== PARTIES ===",
        f"Carrier: {bol.carrier.name}" + (f" (MC# {bol.carrier.mc_number})" if bol.carrier.mc_number else ""),
        f"Carrier address: {bol.carrier.address or 'N/A'}",
        f"Carrier contact: {carrier_contact_name or 'Claims Department'}",
        f"Claimant/Shipper: {claim.claimant}",
        f"Shipper address: {bol.shipper.address or 'N/A'}",
        "",
        "=== SHIPMENT ===",
        f"BOL Number: {bol.bol_number or 'N/A'}",
        f"Route: {bol.origin} → {bol.destination}",
        f"Commodity: {bol.commodity_description}",
        f"Weight: {bol.weight_lbs:,.0f} lbs",
        f"Shipment date: {bol.date or 'N/A'}",
        f"Delivery date: {claim.delivery_date or 'N/A'}",
        "",
        "=== CLAIM ===",
        f"Claim date: {claim.claim_date}",
        f"Claim amount: ${lib.claim_amount:,.2f}",
        f"Damage description: {claim.damage_description}",
        f"Packaging: {claim.packaging_description or 'Not described'}",
        "",
        "=== ANALYSIS RESULTS ===",
        f"Recommended position: {pos.value}",
        f"Liability without defenses: ${lib.without_defense:,.2f}",
        f"Liability with defenses: ${lib.with_defense:,.2f}",
        f"Reduction: ${lib.reduction:,.2f}",
        f"Confidence: {lib.confidence:.0%}",
        "",
        "--- Timeliness ---",
        f"Filed {analysis.timeliness.days_to_file} days after delivery (limit: {analysis.timeliness.deadline_days} days)",
        f"Timely: {'Yes' if analysis.timeliness.is_timely else 'No — CLAIM IS TIME-BARRED'}",
        "",
        "--- Released Value ---",
    ]

    rv = analysis.released_value
    if rv.found:
        lines.append(f"Released value notation: \"{rv.notation}\"")
        lines.append(f"Rate: ${rv.amount_per_pound:.2f}/lb × {rv.weight_lbs:,.0f} lbs = ${rv.max_liability:,.2f} cap")
    else:
        lines.append("No released value notation on BOL — full exposure")

    lines.append("")
    lines.append("--- SL&C (Shipper Load & Count) ---")
    lines.append(f"SL&C notation: {'FOUND on BOL — shipper loaded without carrier verification' if analysis.slc.notation_found else 'Not found'}")

    lines.append("")
    lines.append("--- Applicable Defenses ---")
    active_defenses = [d for d in analysis.defenses if d.applies]
    if active_defenses:
        for d in active_defenses:
            lines.append(f"  Defense: {d.name}")
            lines.append(f"  Strength: {d.strength.value.upper()}")
            lines.append(f"  Evidence: {d.evidence}")
            if d.case_cite:
                lines.append(f"  Cite: {d.case_cite}")
            lines.append("")
    else:
        lines.append("  None applicable.")
        lines.append("")

    lines.append("=== INSTRUCTION ===")
    if pos == RecommendedPosition.DISPUTE_FULL:
        lines.append("Write a letter firmly disputing the claim in full and requesting withdrawal.")
    elif pos == RecommendedPosition.DISPUTE_PARTIAL:
        lines.append(f"Write a letter acknowledging limited liability of ${lib.with_defense:,.2f} based on released value, disputing the remainder.")
    else:
        lines.append(f"Write a letter professionally acknowledging the claim and confirming the carrier will process payment of ${lib.with_defense:,.2f}.")

    return "\n".join(lines)


async def generate_dispute_letter(
    analysis: CarmackAnalysis,
    bol: BOLData,
    claim: ClaimData,
    carrier_contact_name: str | None = None,
) -> DisputeLetter:
    """
    Generate a formal dispute letter citing Carmack Amendment provisions.

    Uses Claude claude-sonnet-4-20250514 with a system prompt constraining citations to verified cases only.
    The synchronous Anthropic client is used (called from async context).
    """
    user_prompt = _build_user_prompt(analysis, bol, claim, carrier_contact_name)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.3,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        letter_text = response.content[0].text

        # Find which verified citations actually appear in the letter
        citations = [c for c in VERIFIED_CITATIONS if c in letter_text]

        return DisputeLetter(
            letter_text=letter_text,
            citations=citations,
            recommended_position=analysis.liability.recommended_position,
        )

    except Exception:
        return DisputeLetter(
            letter_text="Letter generation temporarily unavailable. Please try again.",
            citations=[],
            recommended_position=analysis.liability.recommended_position,
        )
