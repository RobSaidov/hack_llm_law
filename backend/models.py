"""
LoadShield — Shared Pydantic Models
THE CONTRACT: All modules import from here. Do not duplicate schemas elsewhere.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import date


# ─── Enums ────────────────────────────────────────────────────────────────────

class DamageType(str, Enum):
    WATER = "water"
    CRUSH = "crush"
    TEMPERATURE = "temperature"
    THEFT = "theft"
    SHORTAGE = "shortage"
    CONTAMINATION = "contamination"
    OTHER = "other"


class RecommendedPosition(str, Enum):
    DISPUTE_FULL = "DISPUTE_FULL"
    DISPUTE_PARTIAL = "DISPUTE_PARTIAL"
    PAY = "PAY"


class DefenseStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NOT_APPLICABLE = "not_applicable"


# ─── Document Parsing Models (parser teammate outputs these) ──────────────────

class PartyInfo(BaseModel):
    name: str
    address: Optional[str] = None


class CarrierInfo(BaseModel):
    name: str
    mc_number: Optional[str] = None
    address: Optional[str] = None


class SignatureInfo(BaseModel):
    shipper_signed: bool = False
    carrier_signed: bool = False
    consignee_signed: bool = False


class BOLData(BaseModel):
    """Bill of Lading — extracted from uploaded document or demo scenario."""
    bol_number: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
    shipper: PartyInfo
    carrier: CarrierInfo
    consignee: Optional[PartyInfo] = None
    origin: str
    destination: str
    commodity_description: str
    weight_lbs: float
    num_pieces: Optional[int] = None
    declared_value: Optional[float] = None
    released_value_notation: Optional[str] = None  # e.g. "$2.00 per pound"
    released_value_per_lb: Optional[float] = None   # e.g. 2.00
    slc_notation: bool = False  # Shipper Load & Count
    special_instructions: Optional[str] = None
    hazmat: bool = False
    signatures: SignatureInfo = SignatureInfo()
    noted_exceptions_at_pickup: Optional[str] = None
    raw_text: Optional[str] = None


class ClaimData(BaseModel):
    """Cargo claim — extracted from uploaded document or demo scenario."""
    claimant: str
    claim_date: str  # YYYY-MM-DD
    claim_amount: float
    bol_reference: Optional[str] = None
    delivery_date: Optional[str] = None  # YYYY-MM-DD
    damage_description: str
    damage_type: Optional[DamageType] = None
    items_damaged: Optional[int] = None
    items_total: Optional[int] = None
    packaging_description: Optional[str] = None
    inspection_notes: Optional[str] = None
    supporting_docs_mentioned: list[str] = []
    raw_text: Optional[str] = None


# ─── Carmack Engine Models (engine outputs these) ────────────────────────────

class TimelinessCheck(BaseModel):
    days_to_file: int
    deadline_days: int = 270  # 9 months
    is_timely: bool
    detail: str


class ReleasedValueCheck(BaseModel):
    found: bool
    notation: Optional[str] = None
    amount_per_pound: Optional[float] = None
    weight_lbs: float
    max_liability: Optional[float] = None  # released_value_per_lb * weight
    detail: str


class SLCCheck(BaseModel):
    notation_found: bool
    applicable: bool
    detail: str


class CarmackDefense(BaseModel):
    id: int
    name: str
    applies: bool
    strength: DefenseStrength
    evidence: str
    case_cite: Optional[str] = None


class LiabilityCalculation(BaseModel):
    claim_amount: float
    without_defense: float  # what carrier owes if no defenses
    with_defense: float     # what carrier owes after defenses applied
    reduction: float        # dollars saved
    recommended_position: RecommendedPosition
    confidence: float = Field(ge=0, le=1)


class CarmackAnalysis(BaseModel):
    """Full Carmack analysis output from the engine."""
    timeliness: TimelinessCheck
    released_value: ReleasedValueCheck
    slc: SLCCheck
    defenses: list[CarmackDefense]
    liability: LiabilityCalculation
    summary: str


# ─── Letter Generator Models ─────────────────────────────────────────────────

class DisputeLetter(BaseModel):
    letter_text: str
    citations: list[str]
    recommended_position: RecommendedPosition


# ─── API Request/Response Models ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    bol_data: BOLData
    claim_data: ClaimData
    shipment_date: Optional[str] = None  # YYYY-MM-DD (if different from bol.date)
    delivery_date: str  # YYYY-MM-DD — required for timeliness calc


class AnalyzeResponse(BaseModel):
    bol_data: BOLData
    claim_data: ClaimData
    analysis: CarmackAnalysis


class GenerateLetterRequest(BaseModel):
    analysis: CarmackAnalysis
    bol_data: BOLData
    claim_data: ClaimData
    carrier_contact_name: Optional[str] = None


class GenerateLetterResponse(BaseModel):
    letter: DisputeLetter


class DemoScenarioResponse(BaseModel):
    bol_data: BOLData
    claim_data: ClaimData
    delivery_date: str


class FullAnalysisResponse(BaseModel):
    """Complete response for the frontend — everything in one payload."""
    bol_data: BOLData
    claim_data: ClaimData
    analysis: CarmackAnalysis
    letter: DisputeLetter


# ─── Pre-Screen Models ──────────────────────────────────────────────────────

class PreScreenWarning(BaseModel):
    field: str
    status: str  # "green" | "amber" | "red"
    message: str
    recommendation: str


class PreScreenResult(BaseModel):
    risk_level: str  # "low" | "medium" | "high"
    warnings: list[PreScreenWarning]
    summary: str


class PreScreenRequest(BaseModel):
    bol_data: BOLData


class PreScreenResponse(BaseModel):
    result: PreScreenResult
