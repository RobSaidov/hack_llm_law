# LoadShield — Freight Legal Intelligence

## Overview
Web app that analyzes freight cargo claims using the Carmack Amendment (49 U.S.C. § 14706). A carrier uploads a Bill of Lading + cargo claim → system runs deterministic legal analysis → identifies defenses → calculates liability → generates a dispute letter. Built at Stanford LLM x Law Hackathon #6 (April 12, 2026).

## Architecture

```
hack_llm_law/
├── CLAUDE.md
├── backend/
│   ├── main.py                # FastAPI app — 4 endpoints, CORS, wires everything together
│   ├── models.py              # Pydantic models — THE SHARED CONTRACT between all modules
│   ├── carmack_engine.py      # Deterministic Carmack analysis — NO LLM, pure Python rules
│   ├── document_parser.py     # [TEAMMATE BUILDS THIS] Claude-powered doc extraction
│   ├── letter_generator.py    # Claude-powered dispute letter generation
│   ├── demo_scenarios.py      # 3 hardcoded demo scenarios for testing + demo button
│   ├── requirements.txt
│   └── .env                   # ANTHROPIC_API_KEY (not committed)
└── frontend/
    └── index.html             # Single-file React app (CDN imports, no build step)
```

## Data Flow

```
[File Upload / Demo Button]
        │
        ▼
  document_parser.py          ← Teammate builds (Claude LLM extracts structured fields)
  Returns: BOLData, ClaimData    (Pydantic models from models.py)
        │
        ▼
  carmack_engine.py            ← I build (deterministic Python — NO LLM)
  Input:  BOLData + ClaimData
  Output: CarmackAnalysis
        │
        ▼
  letter_generator.py          ← Teammate builds (Claude LLM generates formal letter)
  Input:  CarmackAnalysis + BOLData + ClaimData
  Output: DisputeLetter
        │
        ▼
  main.py                      ← I build (FastAPI, serves everything)
  Returns full response to frontend
        │
        ▼
  frontend/index.html          ← I build (React via CDN, dark dashboard UI)
  Displays: extraction → analysis animation → liability calc → letter
```

## What I'm building (vs teammate)

**I build:**
- `models.py` — all Pydantic models (shared contract)
- `carmack_engine.py` — the legal decision tree (pure Python, NO LLM)
- `main.py` — FastAPI server with all endpoints
- `demo_scenarios.py` — hardcoded test data
- `frontend/index.html` — the dashboard UI

**Teammate builds:**
- `document_parser.py` — must export this function:
```python
async def parse_document(
    file_bytes: bytes,
    file_type: str,        # "pdf" | "image" | "text"
    document_type: str     # "bol" | "claim"
) -> dict:                 # Returns dict matching BOLData or ClaimData from models.py
```
- `letter_generator.py` — must export this function:
```python
async def generate_dispute_letter(
    analysis: CarmackAnalysis,
    bol: BOLData,
    claim: ClaimData,
    carrier_contact_name: str | None = None,
) -> DisputeLetter:
```
- Both use Claude claude-sonnet-4-20250514 via Anthropic SDK
- Their code imports models from `models.py` for validation
- Until their modules are ready, main.py catches NotImplementedError and returns placeholders

## Critical implementation rules

### 1. Carmack engine is DETERMINISTIC — no LLM
`carmack_engine.py` must be pure Python. The legal logic is a decision tree:
- Check claim timeliness (filed within 9 months / 270 days of delivery?)
- Check released value notation on BOL (caps liability if present)
- Check SL&C notation (shifts burden to shipper)
- Evaluate 5 common-law carrier defenses
- Calculate liability with and without defenses
- Output recommended position: DISPUTE_FULL / DISPUTE_PARTIAL / PAY

This MUST be predictable, testable, and produce the same output every time for the same input. Never call an LLM from this module.

### 2. LLM usage is limited to two modules
- `document_parser.py` — Claude extracts structured data from documents (teammate)
- `letter_generator.py` — Claude generates the dispute letter from analysis results (me)
- Model: `claude-sonnet-4-20250514` via `anthropic` Python SDK
- Always use structured output / JSON mode where possible

### 3. All legal citations must be real
Verified citations — use ONLY these:
- **49 U.S.C. § 14706** — Carmack Amendment (carrier liability for interstate cargo)
- **Missouri Pacific R.R. Co. v. Elmore & Stahl, 377 U.S. 134 (1964)** — establishes shipper's prima facie burden: good condition at origin, damaged at destination, amount of damages
- **Southeastern Express Co. v. Pastime Amusement Co., 299 U.S. 28 (1935)** — shipper packaging responsibility
- **Rini v. United Van Lines, 104 F.3d 502 (1st Cir. 1997)** — federal preemption of state law claims
- **Nemf v. AAMCO Transmissions, 135 F.3d 57 (2d Cir. 1998)** — released value / limitation of liability

The 5 Carmack carrier defenses:
1. Act of God (natural disaster, weather extreme)
2. Public Enemy (theft, terrorism, war)
3. Act of Shipper / Shipper Negligence (improper packaging, loading, labeling)
4. Public Authority (government seizure, customs hold)
5. Inherent Vice / Nature of Goods (perishable decay, fragile items, hazmat leakage)

### 4. Frontend design
- Dark Bloomberg-terminal aesthetic, NOT a chatbot
- Background: #0a0a0f | Surfaces: #12121a | Borders: #1e1e2e
- Green (#00ff88): defense found, claim disputed, money saved
- Amber (#ffaa00): warning, partial risk
- Red (#ff3344): full exposure, no defense, liability
- Text: #f0f0f0 primary, #888899 secondary
- Fonts: JetBrains Mono (data/numbers), system sans-serif (body)
- The "$X → $Y" liability reduction must be the biggest visual element
- Include a "Load Demo" button that bypasses upload with hardcoded scenario
- Always show disclaimer: "LoadShield provides legal intelligence, not legal advice."

### 5. API design
All endpoints accept and return JSON. CORS enabled for localhost frontend.

```
POST /api/analyze-claim
  - Accepts: { bol_data: BOLData, claim_data: ClaimData }
  - Returns: { analysis: CarmackAnalysis }

POST /api/generate-letter
  - Accepts: { analysis: CarmackAnalysis, bol_data: BOLData, claim_data: ClaimData }
  - Returns: { letter: str, citations: list[str] }

POST /api/parse-document
  - Accepts: multipart/form-data (file + document_type)
  - Returns: BOLData or ClaimData
  - [This endpoint calls teammate's parser]

GET /api/demo-scenario/{scenario_id}
  - Returns: { bol_data: BOLData, claim_data: ClaimData }
  - scenario_id: "a" | "b" | "c"
```

## Running

```bash
# Backend
cd backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env  # add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000

# Frontend
# Just open frontend/index.html in a browser
# OR serve with: python -m http.server 3000 --directory frontend
```

## The Carmack Decision Tree (full reference)

```
STEP 1: CLAIM TIMELINESS
  days_since_delivery = claim_date - delivery_date
  IF days_since_delivery > 270:
    → Claim is TIME-BARRED. Carrier owes $0. DISPUTE_FULL.
    → Cite: 49 U.S.C. § 14706(e)(1)

STEP 2: RELEASED VALUE
  IF bol.released_value_per_lb exists AND bol.released_value_per_lb > 0:
    max_liability = released_value_per_lb × weight_lbs
    → Carrier liability CAPPED at max_liability regardless of actual damage
    → IF max_liability < claim_amount: DISPUTE_PARTIAL (pay max_liability only)
    → Cite: Nemf v. AAMCO, released value doctrine
  ELSE:
    max_liability = claim_amount (full exposure)

STEP 3: PRIMA FACIE CASE — SL&C CHECK
  Shipper must prove: (a) goods in good condition at origin,
                       (b) damaged at destination, (c) damages amount
  IF bol.slc_notation == True:
    → Shipper loaded the truck themselves. Carrier never verified condition.
    → This WEAKENS element (a) — shipper cannot easily prove good condition
    → Strong defense: carrier can argue damage was pre-existing or caused by shipper loading
    → Cite: Missouri Pacific v. Elmore & Stahl (prima facie burden)

STEP 4: EVALUATE 5 DEFENSES
  For each defense, check damage_description and commodity for keyword signals:

  DEFENSE 1 — Act of God:
    Triggers: "flood", "hurricane", "tornado", "earthquake", "lightning", "wildfire"
    Strength: STRONG if natural disaster clearly caused the damage

  DEFENSE 2 — Public Enemy:
    Triggers: "stolen", "theft", "hijack", "robbery", "piracy"
    Strength: STRONG if cargo was stolen/destroyed by criminal act

  DEFENSE 3 — Act of Shipper / Shipper Negligence:
    Triggers: "packaging", "cardboard", "no padding", "no shrink wrap",
              "improperly secured", "shipper loaded", "inadequate",
              "no moisture barrier", "no waterproofing"
    Also triggered by: slc_notation == True
    Also triggered by: commodity is fragile/electronic BUT packaging is "standard"
    Strength: STRONG — this is the most common successful defense
    Cite: Southeastern Express v. Pastime Amusement

  DEFENSE 4 — Public Authority:
    Triggers: "seized", "customs", "quarantine", "government", "confiscated"
    Strength: STRONG if government action caused loss

  DEFENSE 5 — Inherent Vice / Nature of Goods:
    Triggers: commodity contains "perishable", "food", "produce", "flowers",
              "live animals", "chemicals", "temperature sensitive"
    AND damage is "spoil", "rot", "decay", "melt", "ferment", "evaporate"
    Strength: MODERATE — must show damage was due to nature of goods, not carrier negligence

STEP 5: CALCULATE LIABILITY
  strong_defenses = [d for d in defenses if d.applies and d.strength == "strong"]
  moderate_defenses = [d for d in defenses if d.applies and d.strength == "moderate"]

  IF claim is time-barred:
    liability_with_defense = 0
    position = DISPUTE_FULL
  ELIF len(strong_defenses) > 0:
    liability_with_defense = 0
    position = DISPUTE_FULL
  ELIF released_value_cap < claim_amount:
    liability_with_defense = released_value_cap
    position = DISPUTE_PARTIAL
  ELIF len(moderate_defenses) > 0:
    liability_with_defense = claim_amount * 0.5  # partial reduction estimate
    position = DISPUTE_PARTIAL
  ELSE:
    liability_with_defense = claim_amount
    position = PAY

  exposure_reduction = claim_amount - liability_with_defense
```

## Don'ts
- Don't use LLM for Carmack logic — must be deterministic Python
- Don't hallucinate case citations — only use verified ones above
- Don't build a chatbot — this is a dashboard with structured analysis
- Don't handle state law — Carmack preempts state law for interstate freight
- Don't add auth, databases, user accounts — hackathon demo
- Don't create a separate build step for frontend — use CDN imports (React, Tailwind, etc.)
- Don't wait for parser teammate — use demo_scenarios.py to test everything independently