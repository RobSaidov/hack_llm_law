"""
LoadShield — Demo Scenarios
3 pre-built scenarios for testing the engine and powering the "Load Demo" button.
These bypass the document parser entirely.
"""

from models import BOLData, ClaimData, PartyInfo, CarrierInfo, SignatureInfo


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO A: Full Dispute — $22,000 → $0
# SL&C present, shipper negligence (bad packaging for electronics), no released value
# This is THE MAIN DEMO scenario.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO_A_BOL = BOLData(
    bol_number="BOL-2026-44821",
    date="2026-03-15",
    shipper=PartyInfo(name="ABC Electronics Inc.", address="1200 Commerce Blvd, Los Angeles, CA 90012"),
    carrier=CarrierInfo(name="FastFreight LLC", mc_number="MC-123456"),
    consignee=PartyInfo(name="XYZ Retail Corp", address="500 Distribution Dr, Dallas, TX 75201"),
    origin="Los Angeles, CA",
    destination="Dallas, TX",
    commodity_description="Consumer electronics — laptops, 24 units",
    weight_lbs=800,
    num_pieces=24,
    declared_value=22000.00,
    released_value_notation=None,
    released_value_per_lb=None,
    slc_notation=True,  # KEY: Shipper Load & Count is marked
    special_instructions="FRAGILE — Keep dry, do not stack",
    hazmat=False,
    signatures=SignatureInfo(shipper_signed=True, carrier_signed=True, consignee_signed=False),
    noted_exceptions_at_pickup=None,
)

SCENARIO_A_CLAIM = ClaimData(
    claimant="ABC Electronics Inc.",
    claim_date="2026-04-01",
    claim_amount=22000.00,
    bol_reference="BOL-2026-44821",
    delivery_date="2026-03-18",
    damage_description=(
        "Water damage to 12 of 24 laptop units. Units found with moisture inside "
        "sealed packaging upon delivery at Dallas distribution center. Visible corrosion "
        "on circuit boards, non-functional LCD screens, and water staining on exterior "
        "cartons. Damage consistent with exposure to moisture during transit."
    ),
    damage_type="water",
    items_damaged=12,
    items_total=24,
    packaging_description="Standard cardboard boxes, no waterproofing, no moisture barriers",
    inspection_notes="Independent inspection report confirms water intrusion damage",
    supporting_docs_mentioned=["photos", "invoice", "inspection report", "delivery receipt"],
)

SCENARIO_A_DELIVERY_DATE = "2026-03-18"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO B: Partial Dispute — $15,000 → $1,000
# Released value caps liability at $0.50/lb × 2000 lbs = $1,000
# No SL&C, no strong defenses, but released value saves the carrier $14,000
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO_B_BOL = BOLData(
    bol_number="BOL-2026-55102",
    date="2026-02-20",
    shipper=PartyInfo(name="HomeStyle Furniture Co.", address="800 Oak Ave, Grand Rapids, MI 49503"),
    carrier=CarrierInfo(name="MidWest Haulers Inc.", mc_number="MC-789012"),
    consignee=PartyInfo(name="Designer Living Stores", address="2100 Elm St, Nashville, TN 37201"),
    origin="Grand Rapids, MI",
    destination="Nashville, TN",
    commodity_description="Household furniture — dining sets, 8 units",
    weight_lbs=2000,
    num_pieces=8,
    declared_value=15000.00,
    released_value_notation="Released value not exceeding $0.50 per pound per article",
    released_value_per_lb=0.50,  # KEY: This caps liability
    slc_notation=False,
    special_instructions="Handle with care, no stacking",
    hazmat=False,
    signatures=SignatureInfo(shipper_signed=True, carrier_signed=True, consignee_signed=False),
    noted_exceptions_at_pickup=None,
)

SCENARIO_B_CLAIM = ClaimData(
    claimant="HomeStyle Furniture Co.",
    claim_date="2026-03-10",
    claim_amount=15000.00,
    bol_reference="BOL-2026-55102",
    delivery_date="2026-02-23",
    damage_description=(
        "Crush damage to 4 of 8 dining table sets. Tables arrived with broken legs "
        "and cracked surfaces. Appears items shifted during transit and were not "
        "properly secured in trailer. Glass table tops shattered."
    ),
    damage_type="crush",
    items_damaged=4,
    items_total=8,
    packaging_description="Professional furniture blankets, corner protectors, shrink wrap",
    inspection_notes=None,
    supporting_docs_mentioned=["photos", "invoice"],
)

SCENARIO_B_DELIVERY_DATE = "2026-02-23"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO C: Must Pay — $8,000 → $8,000
# No defenses. Carrier driver dropped artwork during unloading.
# Carrier is clearly at fault. Tool should recommend PAY.
# (This builds credibility — shows the tool is honest, not always pro-carrier)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO_C_BOL = BOLData(
    bol_number="BOL-2026-67890",
    date="2026-03-01",
    shipper=PartyInfo(name="Gallery West Fine Art", address="450 Art District Blvd, Santa Fe, NM 87501"),
    carrier=CarrierInfo(name="Southwest Express Lines", mc_number="MC-345678"),
    consignee=PartyInfo(name="Metropolitan Art Gallery", address="1500 Museum Way, Denver, CO 80202"),
    origin="Santa Fe, NM",
    destination="Denver, CO",
    commodity_description="Fine art — framed paintings, 6 pieces",
    weight_lbs=500,
    num_pieces=6,
    declared_value=8000.00,
    released_value_notation=None,
    released_value_per_lb=None,
    slc_notation=False,  # Carrier loaded
    special_instructions="FRAGILE ART — Handle with extreme care, climate controlled",
    hazmat=False,
    signatures=SignatureInfo(shipper_signed=True, carrier_signed=True, consignee_signed=True),
    noted_exceptions_at_pickup=None,
)

SCENARIO_C_CLAIM = ClaimData(
    claimant="Gallery West Fine Art",
    claim_date="2026-03-20",
    claim_amount=8000.00,
    bol_reference="BOL-2026-67890",
    delivery_date="2026-03-03",
    damage_description=(
        "Two framed paintings dropped by carrier driver during unloading at destination. "
        "Frames shattered, canvas torn on both pieces. Witnessed by consignee staff. "
        "Driver acknowledged the drop on delivery receipt and noted 'accidental drop "
        "during hand-off.' Paintings were properly crated and cushioned by shipper."
    ),
    damage_type="crush",
    items_damaged=2,
    items_total=6,
    packaging_description="Professional art crating with foam inserts, corner protectors, and 'FRAGILE' markings",
    inspection_notes="Driver signed delivery receipt acknowledging damage caused during unloading",
    supporting_docs_mentioned=["photos", "delivery receipt with driver note", "appraisal"],
)

SCENARIO_C_DELIVERY_DATE = "2026-03-03"


# ─── Accessor ─────────────────────────────────────────────────────────────────

SCENARIOS = {
    "a": {
        "bol_data": SCENARIO_A_BOL,
        "claim_data": SCENARIO_A_CLAIM,
        "delivery_date": SCENARIO_A_DELIVERY_DATE,
        "label": "Full Dispute — $22,000 → $0 (SL&C + Shipper Negligence)",
    },
    "b": {
        "bol_data": SCENARIO_B_BOL,
        "claim_data": SCENARIO_B_CLAIM,
        "delivery_date": SCENARIO_B_DELIVERY_DATE,
        "label": "Partial Dispute — $15,000 → $1,000 (Released Value Cap)",
    },
    "c": {
        "bol_data": SCENARIO_C_BOL,
        "claim_data": SCENARIO_C_CLAIM,
        "delivery_date": SCENARIO_C_DELIVERY_DATE,
        "label": "Must Pay — $8,000 → $8,000 (Carrier At Fault)",
    },
}


def get_scenario(scenario_id: str) -> dict:
    """Get a demo scenario by ID ('a', 'b', or 'c')."""
    scenario = SCENARIOS.get(scenario_id.lower())
    if not scenario:
        raise ValueError(f"Unknown scenario: {scenario_id}. Use 'a', 'b', or 'c'.")
    return scenario
