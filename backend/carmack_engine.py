"""
LoadShield — Carmack Amendment Analysis Engine
DETERMINISTIC. NO LLM CALLS. Pure Python decision tree.

Input:  BOLData + ClaimData + delivery_date
Output: CarmackAnalysis

See CLAUDE.md "The Carmack Decision Tree" for full logic specification.
"""

from datetime import date, datetime
from models import (
    BOLData, ClaimData, CarmackAnalysis,
    TimelinessCheck, ReleasedValueCheck, SLCCheck,
    CarmackDefense, LiabilityCalculation,
    DefenseStrength, RecommendedPosition,
    PreScreenWarning, PreScreenResult,
)

# ─── Legal Citations ────────────────────────────────────────────────────────

CITE_CARMACK = "49 U.S.C. § 14706"
CITE_ELMORE_STAHL = "Missouri Pacific R.R. Co. v. Elmore & Stahl, 377 U.S. 134 (1964)"
CITE_PASTIME = "Southeastern Express Co. v. Pastime Amusement Co., 299 U.S. 28 (1935)"
CITE_RINI = "Rini v. United Van Lines, 104 F.3d 502 (1st Cir. 1997)"
CITE_NEMF = "Nemf v. AAMCO Transmissions, 135 F.3d 57 (2d Cir. 1998)"

# ─── Keyword Sets ───────────────────────────────────────────────────────────

ACT_OF_GOD_KEYWORDS = [
    "flood", "hurricane", "tornado", "earthquake", "lightning",
    "wildfire", "storm", "hail", "natural disaster",
]

PUBLIC_ENEMY_KEYWORDS = [
    "stolen", "theft", "hijack", "robbery", "piracy",
    "terrorist", "vandalism",
]

SHIPPER_NEGLIGENCE_PACKAGING_KEYWORDS = [
    "standard", "cardboard", "no padding", "no waterproofing",
    "no moisture", "inadequate", "basic", "minimal",
]

PUBLIC_AUTHORITY_KEYWORDS = [
    "seized", "customs", "quarantine", "government",
    "confiscated", "embargo", "regulatory",
]

INHERENT_VICE_COMMODITY_KEYWORDS = [
    "perishable", "food", "produce", "flowers",
    "live", "chemical", "temperature sensitive", "frozen",
]

INHERENT_VICE_DAMAGE_KEYWORDS = [
    "spoil", "rot", "decay", "melt", "ferment",
    "wilt", "decompose", "expire",
]

FRAGILE_COMMODITY_KEYWORDS = [
    "electronic", "laptop", "computer", "monitor", "screen", "display",
    "glass", "ceramic", "porcelain", "crystal", "fragile",
]


# ─── Helpers ────────────────────────────────────────────────────────────────

def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _has_keyword(text: str | None, keywords: list[str]) -> list[str]:
    """Return all keywords found in text (case-insensitive). Empty list if no match."""
    if not text:
        return []
    lower = text.lower()
    return [kw for kw in keywords if kw in lower]


# ─── Step 1: Timeliness ────────────────────────────────────────────────────

def _check_timeliness(claim: ClaimData, delivery_date: str) -> TimelinessCheck:
    d_delivery = _parse_date(delivery_date)
    d_claim = _parse_date(claim.claim_date)
    days = (d_claim - d_delivery).days

    is_timely = days <= 270
    if is_timely:
        detail = (
            f"Claim filed {days} days after delivery (within 270-day deadline). "
            f"Claim is timely under {CITE_CARMACK}."
        )
    else:
        detail = (
            f"Claim filed {days} days after delivery, exceeding the 270-day (9-month) "
            f"statutory deadline. Claim is TIME-BARRED under {CITE_CARMACK}(e)(1). "
            f"Carrier owes $0."
        )

    return TimelinessCheck(
        days_to_file=days,
        deadline_days=270,
        is_timely=is_timely,
        detail=detail,
    )


# ─── Step 2: Released Value ────────────────────────────────────────────────

def _check_released_value(bol: BOLData, claim: ClaimData) -> ReleasedValueCheck:
    if bol.released_value_per_lb and bol.released_value_per_lb > 0:
        max_liability = bol.released_value_per_lb * bol.weight_lbs
        detail = (
            f"BOL contains released value notation: \"{bol.released_value_notation}\". "
            f"Liability capped at ${bol.released_value_per_lb:.2f}/lb × "
            f"{bol.weight_lbs:.0f} lbs = ${max_liability:,.2f}. "
            f"See {CITE_NEMF} (released value doctrine)."
        )
        return ReleasedValueCheck(
            found=True,
            notation=bol.released_value_notation,
            amount_per_pound=bol.released_value_per_lb,
            weight_lbs=bol.weight_lbs,
            max_liability=max_liability,
            detail=detail,
        )

    return ReleasedValueCheck(
        found=False,
        notation=None,
        amount_per_pound=None,
        weight_lbs=bol.weight_lbs,
        max_liability=None,
        detail=(
            "No released value notation on BOL. Carrier faces full exposure "
            f"up to the claimed amount of ${claim.claim_amount:,.2f}."
        ),
    )


# ─── Step 3: SL&C ──────────────────────────────────────────────────────────

def _check_slc(bol: BOLData) -> SLCCheck:
    if bol.slc_notation:
        return SLCCheck(
            notation_found=True,
            applicable=True,
            detail=(
                "Shipper Load & Count (SL&C) notation present on BOL. Shipper loaded the "
                "trailer without carrier verification of cargo condition. This weakens the "
                f"shipper's prima facie case under {CITE_ELMORE_STAHL} — shipper cannot "
                "easily prove goods were in good condition at origin."
            ),
        )

    return SLCCheck(
        notation_found=False,
        applicable=False,
        detail=(
            "No SL&C notation. Carrier accepted cargo and is presumed to have verified "
            "condition at origin."
        ),
    )


# ─── Step 4: Five Defenses ─────────────────────────────────────────────────

def _evaluate_defenses(bol: BOLData, claim: ClaimData) -> list[CarmackDefense]:
    damage = claim.damage_description or ""
    commodity = bol.commodity_description or ""
    packaging = claim.packaging_description or ""

    defenses: list[CarmackDefense] = []

    # Defense 1 — Act of God
    hits = _has_keyword(damage, ACT_OF_GOD_KEYWORDS)
    if hits:
        defenses.append(CarmackDefense(
            id=1, name="Act of God", applies=True,
            strength=DefenseStrength.STRONG,
            evidence=f"Damage description references natural disaster: {', '.join(hits)}.",
            case_cite=CITE_CARMACK,
        ))
    else:
        defenses.append(CarmackDefense(
            id=1, name="Act of God", applies=False,
            strength=DefenseStrength.NOT_APPLICABLE,
            evidence="No natural disaster or extreme weather referenced in damage description.",
        ))

    # Defense 2 — Public Enemy
    hits = _has_keyword(damage, PUBLIC_ENEMY_KEYWORDS)
    if hits:
        defenses.append(CarmackDefense(
            id=2, name="Public Enemy", applies=True,
            strength=DefenseStrength.STRONG,
            evidence=f"Damage description references criminal/hostile act: {', '.join(hits)}.",
            case_cite=CITE_CARMACK,
        ))
    else:
        defenses.append(CarmackDefense(
            id=2, name="Public Enemy", applies=False,
            strength=DefenseStrength.NOT_APPLICABLE,
            evidence="No theft, hijacking, or hostile act referenced in damage description.",
        ))

    # Defense 3 — Shipper Negligence (most common)
    negligence_reasons: list[str] = []

    if bol.slc_notation:
        negligence_reasons.append("SL&C notation present — shipper loaded without carrier verification")

    pkg_hits = _has_keyword(packaging, SHIPPER_NEGLIGENCE_PACKAGING_KEYWORDS)
    if pkg_hits:
        negligence_reasons.append(f"Packaging described as: {', '.join(pkg_hits)}")

    damage_pkg_hits = _has_keyword(damage, ["packaging", "improperly packed", "poorly packed", "inadequate packaging"])
    if damage_pkg_hits:
        negligence_reasons.append(f"Damage description mentions packaging failure: {', '.join(damage_pkg_hits)}")

    fragile_hits = _has_keyword(commodity, FRAGILE_COMMODITY_KEYWORDS)
    basic_pkg_hits = _has_keyword(packaging, ["standard", "cardboard", "basic", "minimal"])
    if fragile_hits and basic_pkg_hits:
        negligence_reasons.append(
            f"Fragile/electronic commodity ({', '.join(fragile_hits)}) "
            f"shipped with basic packaging ({', '.join(basic_pkg_hits)})"
        )

    if negligence_reasons:
        defenses.append(CarmackDefense(
            id=3, name="Act of Shipper / Shipper Negligence", applies=True,
            strength=DefenseStrength.STRONG,
            evidence="; ".join(negligence_reasons) + ".",
            case_cite=CITE_PASTIME,
        ))
    else:
        defenses.append(CarmackDefense(
            id=3, name="Act of Shipper / Shipper Negligence", applies=False,
            strength=DefenseStrength.NOT_APPLICABLE,
            evidence="No evidence of shipper negligence in packaging or loading.",
        ))

    # Defense 4 — Public Authority
    hits = _has_keyword(damage, PUBLIC_AUTHORITY_KEYWORDS)
    if hits:
        defenses.append(CarmackDefense(
            id=4, name="Public Authority", applies=True,
            strength=DefenseStrength.STRONG,
            evidence=f"Damage description references government action: {', '.join(hits)}.",
            case_cite=CITE_CARMACK,
        ))
    else:
        defenses.append(CarmackDefense(
            id=4, name="Public Authority", applies=False,
            strength=DefenseStrength.NOT_APPLICABLE,
            evidence="No government seizure, customs hold, or regulatory action referenced.",
        ))

    # Defense 5 — Inherent Vice / Nature of Goods
    commodity_hits = _has_keyword(commodity, INHERENT_VICE_COMMODITY_KEYWORDS)
    damage_hits = _has_keyword(damage, INHERENT_VICE_DAMAGE_KEYWORDS)

    if commodity_hits and damage_hits:
        defenses.append(CarmackDefense(
            id=5, name="Inherent Vice / Nature of Goods", applies=True,
            strength=DefenseStrength.MODERATE,
            evidence=(
                f"Commodity is susceptible ({', '.join(commodity_hits)}) and damage is "
                f"consistent with natural deterioration ({', '.join(damage_hits)}). "
                "Must demonstrate damage was due to nature of goods, not carrier negligence."
            ),
            case_cite=CITE_CARMACK,
        ))
    else:
        defenses.append(CarmackDefense(
            id=5, name="Inherent Vice / Nature of Goods", applies=False,
            strength=DefenseStrength.NOT_APPLICABLE,
            evidence="Commodity and damage type do not indicate inherent vice.",
        ))

    return defenses


# ─── Step 5: Confidence Scoring ────────────────────────────────────────────

def _score_confidence(
    timeliness: TimelinessCheck,
    released_value: ReleasedValueCheck,
    slc: SLCCheck,
    defenses: list[CarmackDefense],
    position: RecommendedPosition,
) -> float:
    """
    Dynamic confidence based on evidence quality, not just the outcome.

    Starts at a base for the position, then adjusts:
      +  multiple independent evidence signals (SL&C, packaging keywords, etc.)
      +  clear keyword matches in damage/commodity text
      +  released value notation explicitly on BOL
      -  single weak signal, vague descriptions, no corroborating evidence
    """
    strong = [d for d in defenses if d.applies and d.strength == DefenseStrength.STRONG]
    moderate = [d for d in defenses if d.applies and d.strength == DefenseStrength.MODERATE]

    # Time-barred is a bright-line statutory rule — always high confidence
    if not timeliness.is_timely:
        return 0.97

    if position == RecommendedPosition.DISPUTE_FULL:
        # Base: one strong defense found
        score = 0.82

        # Multiple strong defenses reinforce each other
        if len(strong) >= 2:
            score += 0.06

        # SL&C is documentary evidence (on the BOL itself) — very reliable
        if slc.notation_found:
            score += 0.05

        # Count independent evidence signals in the strongest defense
        # More semicolons in evidence = more independent reasons found
        best = max(strong, key=lambda d: d.evidence.count(";")) if strong else None
        if best:
            reason_count = best.evidence.count(";") + 1  # reasons separated by ";"
            if reason_count >= 3:
                score += 0.05
            elif reason_count >= 2:
                score += 0.03

        return min(score, 0.97)

    if position == RecommendedPosition.DISPUTE_PARTIAL:
        # Released value cap is black-and-white — notation is on the BOL
        if released_value.found:
            return 0.93

        # Moderate defenses are inherently less certain
        score = 0.70
        if len(moderate) >= 2:
            score += 0.05
        return min(score, 0.85)

    # PAY — no defenses. Confidence reflects how clearly the carrier is at fault.
    # High confidence here means "we're confident you should pay," which is useful.
    score = 0.80
    # If no defenses apply at all, the case is clear-cut against the carrier
    any_applicable = any(d.applies for d in defenses)
    if not any_applicable:
        score += 0.08
    return min(score, 0.92)


# ─── Step 5: Liability Calculation ─────────────────────────────────────────

def _calculate_liability(
    timeliness: TimelinessCheck,
    released_value: ReleasedValueCheck,
    slc: SLCCheck,
    defenses: list[CarmackDefense],
    claim_amount: float,
) -> LiabilityCalculation:
    without_defense = claim_amount

    strong_defenses = [d for d in defenses if d.applies and d.strength == DefenseStrength.STRONG]
    moderate_defenses = [d for d in defenses if d.applies and d.strength == DefenseStrength.MODERATE]

    # Determine position and liability first, then score confidence
    if not timeliness.is_timely:
        pos = RecommendedPosition.DISPUTE_FULL
        with_defense = 0.0
    elif strong_defenses:
        pos = RecommendedPosition.DISPUTE_FULL
        with_defense = 0.0
    elif released_value.max_liability is not None and released_value.max_liability < claim_amount:
        pos = RecommendedPosition.DISPUTE_PARTIAL
        with_defense = released_value.max_liability
    elif moderate_defenses:
        pos = RecommendedPosition.DISPUTE_PARTIAL
        with_defense = claim_amount * 0.5
    else:
        pos = RecommendedPosition.PAY
        with_defense = claim_amount

    confidence = _score_confidence(timeliness, released_value, slc, defenses, pos)

    return LiabilityCalculation(
        claim_amount=claim_amount,
        without_defense=without_defense,
        with_defense=with_defense,
        reduction=claim_amount - with_defense,
        recommended_position=pos,
        confidence=confidence,
    )


# ─── Step 6: Summary ───────────────────────────────────────────────────────

def _generate_summary(
    timeliness: TimelinessCheck,
    released_value: ReleasedValueCheck,
    slc: SLCCheck,
    defenses: list[CarmackDefense],
    liability: LiabilityCalculation,
) -> str:
    pos = liability.recommended_position
    strong = [d for d in defenses if d.applies and d.strength == DefenseStrength.STRONG]
    moderate = [d for d in defenses if d.applies and d.strength == DefenseStrength.MODERATE]

    if not timeliness.is_timely:
        return (
            f"Claim is TIME-BARRED — filed {timeliness.days_to_file} days after delivery, "
            f"exceeding the 270-day statutory deadline under {CITE_CARMACK}(e)(1). "
            "Carrier liability: $0."
        )

    if pos == RecommendedPosition.DISPUTE_FULL:
        defense_names = ", ".join(d.name for d in strong)
        return (
            f"DISPUTE IN FULL recommended. Strong defense(s) identified: {defense_names}. "
            f"Carrier exposure reduced from ${liability.claim_amount:,.2f} to $0.00."
        )

    if pos == RecommendedPosition.DISPUTE_PARTIAL:
        if released_value.found and released_value.max_liability is not None and released_value.max_liability < liability.claim_amount:
            return (
                f"PARTIAL DISPUTE recommended. Released value notation caps liability at "
                f"${released_value.max_liability:,.2f} (${released_value.amount_per_pound:.2f}/lb × "
                f"{released_value.weight_lbs:.0f} lbs) under {CITE_NEMF}. "
                f"Carrier saves ${liability.reduction:,.2f} of the ${liability.claim_amount:,.2f} claim."
            )
        if moderate:
            defense_names = ", ".join(d.name for d in moderate)
            return (
                f"PARTIAL DISPUTE recommended. Moderate defense(s) identified: {defense_names}. "
                f"Estimated carrier liability reduced to ${liability.with_defense:,.2f} "
                f"(saving ${liability.reduction:,.2f})."
            )

    # PAY
    return (
        f"No viable defenses identified. Carrier is liable for the full claimed amount of "
        f"${liability.claim_amount:,.2f}. Recommend prompt payment to avoid additional exposure."
    )


# ─── Pre-Screen (BOL only, no claim needed) ──────────────────────────────

def pre_screen_bol(bol: BOLData) -> PreScreenResult:
    """Check a BOL for risk factors BEFORE accepting the load."""
    warnings: list[PreScreenWarning] = []

    # 1. Released value
    if bol.released_value_per_lb and bol.released_value_per_lb > 0:
        cap = bol.released_value_per_lb * bol.weight_lbs
        warnings.append(PreScreenWarning(
            field="Released Value",
            status="green",
            message=f"Liability capped at ${bol.released_value_per_lb:.2f}/lb (${cap:,.2f} max)",
            recommendation="Released value notation is present. Your exposure is limited.",
        ))
    else:
        warnings.append(PreScreenWarning(
            field="Released Value",
            status="red",
            message="No released value notation. Your exposure is UNLIMITED on this shipment.",
            recommendation="Negotiate a released value clause before signing this BOL.",
        ))

    # 2. SL&C
    if bol.slc_notation:
        warnings.append(PreScreenWarning(
            field="Shipper Load & Count",
            status="green",
            message="SL&C noted. If shipper loads, you have a strong defense against damage claims.",
            recommendation="SL&C is marked — keep it this way.",
        ))
    else:
        warnings.append(PreScreenWarning(
            field="Shipper Load & Count",
            status="amber",
            message="SL&C not marked on BOL.",
            recommendation="If the shipper is loading the truck, mark SL&C on the BOL before departing.",
        ))

    # 3. Commodity risk
    commodity = bol.commodity_description or ""
    fragile = _has_keyword(commodity, FRAGILE_COMMODITY_KEYWORDS)
    perishable = _has_keyword(commodity, INHERENT_VICE_COMMODITY_KEYWORDS)
    risky = fragile + perishable
    if risky:
        warnings.append(PreScreenWarning(
            field="Commodity Risk",
            status="amber",
            message=f"High-risk commodity detected: {', '.join(risky)}.",
            recommendation="Ensure adequate packaging documentation and photos before departure.",
        ))
    else:
        warnings.append(PreScreenWarning(
            field="Commodity Risk",
            status="green",
            message="Standard commodity risk level.",
            recommendation="No special commodity precautions needed.",
        ))

    # 4. Declared value
    dv = bol.declared_value or 0
    if dv > 50000:
        warnings.append(PreScreenWarning(
            field="Declared Value",
            status="amber",
            message=f"High-value shipment (${dv:,.2f}).",
            recommendation="Consider requiring additional cargo insurance for this load.",
        ))
    else:
        warnings.append(PreScreenWarning(
            field="Declared Value",
            status="green",
            message=f"Declared value within normal range{f' (${dv:,.2f})' if dv else ''}.",
            recommendation="No additional insurance action needed.",
        ))

    # Overall risk level
    red_count = sum(1 for w in warnings if w.status == "red")
    amber_count = sum(1 for w in warnings if w.status == "amber")
    issues = red_count + amber_count

    if red_count > 0:
        risk_level = "high"
    elif amber_count >= 2:
        risk_level = "medium"
    elif amber_count == 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    summary = (f"{issues} issue{'s' if issues != 1 else ''} found — "
               f"address before accepting this load" if issues > 0
               else "No issues found — BOL looks good to sign")

    return PreScreenResult(risk_level=risk_level, warnings=warnings, summary=summary)


# ─── Main Entry Point ──────────────────────────────────────────────────────

def analyze_claim(bol: BOLData, claim: ClaimData, delivery_date: str) -> CarmackAnalysis:
    """
    Run full Carmack Amendment analysis on a cargo claim.

    Deterministic: same input → same output, every time.
    No LLM calls: pure Python logic.

    Args:
        bol: Parsed Bill of Lading data
        claim: Parsed cargo claim data
        delivery_date: Date goods were delivered (YYYY-MM-DD)

    Returns:
        CarmackAnalysis with timeliness, released value, SL&C,
        defenses, liability calculation, and summary
    """
    timeliness = _check_timeliness(claim, delivery_date)
    released_value = _check_released_value(bol, claim)
    slc = _check_slc(bol)
    defenses = _evaluate_defenses(bol, claim)
    liability = _calculate_liability(timeliness, released_value, slc, defenses, claim.claim_amount)
    summary = _generate_summary(timeliness, released_value, slc, defenses, liability)

    return CarmackAnalysis(
        timeliness=timeliness,
        released_value=released_value,
        slc=slc,
        defenses=defenses,
        liability=liability,
        summary=summary,
    )
