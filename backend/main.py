"""
LoadShield — FastAPI Server
Wires together: parser → engine → letter generator
Serves the frontend and API endpoints.
"""

import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from models import (
    BOLData, ClaimData, DisputeLetter,
    AnalyzeRequest, AnalyzeResponse,
    GenerateLetterRequest, GenerateLetterResponse,
    DemoScenarioResponse, FullAnalysisResponse,
    PreScreenRequest, PreScreenResponse,
)
from carmack_engine import analyze_claim, pre_screen_bol
from letter_generator import generate_dispute_letter
from document_parser import parse_document
from demo_scenarios import get_scenario

load_dotenv()

app = FastAPI(
    title="LoadShield",
    description="Freight Legal Intelligence — Carmack Amendment Analysis",
    version="0.1.0",
)

# CORS — allow frontend on any localhost port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Demo Scenario Endpoint ──────────────────────────────────────────────────

@app.get("/api/demo-scenario/{scenario_id}")
async def demo_scenario(scenario_id: str) -> DemoScenarioResponse:
    """Load a pre-built demo scenario. scenario_id: 'a', 'b', or 'c'."""
    try:
        scenario = get_scenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return DemoScenarioResponse(
        bol_data=scenario["bol_data"],
        claim_data=scenario["claim_data"],
        delivery_date=scenario["delivery_date"],
    )


# ─── Carmack Analysis Endpoint ───────────────────────────────────────────────

@app.post("/api/analyze-claim")
async def analyze_claim_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run Carmack analysis on BOL + claim data. Returns analysis with defenses and liability."""
    analysis = analyze_claim(
        bol=request.bol_data,
        claim=request.claim_data,
        delivery_date=request.delivery_date,
    )
    return AnalyzeResponse(
        bol_data=request.bol_data,
        claim_data=request.claim_data,
        analysis=analysis,
    )


# ─── Letter Generation Endpoint ──────────────────────────────────────────────

@app.post("/api/generate-letter")
async def generate_letter_endpoint(request: GenerateLetterRequest) -> GenerateLetterResponse:
    """Generate a formal Carmack dispute letter from analysis results."""
    try:
        letter = await generate_dispute_letter(
            analysis=request.analysis,
            bol=request.bol_data,
            claim=request.claim_data,
            carrier_contact_name=request.carrier_contact_name,
        )
    except NotImplementedError:
        letter = DisputeLetter(
            letter_text="Letter generation pending — teammate implementing this module.",
            citations=[],
            recommended_position=request.analysis.liability.recommended_position,
        )
    return GenerateLetterResponse(letter=letter)


# ─── Document Parse Endpoint (uses teammate's parser) ────────────────────────

@app.post("/api/parse-document")
async def parse_document_endpoint(
    file: UploadFile = File(...),
    document_type: str = Form(...),  # "bol" or "claim"
):
    """Parse an uploaded BOL or claim document into structured data."""
    file_bytes = await file.read()

    # Determine file type from content type
    content_type = file.content_type or ""
    if "pdf" in content_type:
        file_type = "pdf"
    elif "image" in content_type:
        file_type = "image"
    else:
        file_type = "text"

    try:
        parsed = await parse_document(file_bytes, file_type, document_type)
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Document parser not yet implemented. Use /api/demo-scenario/{id} instead."
        )
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Strip extra fields the parser adds that aren't in our Pydantic models
    parsed.pop("parse_confidence", None)

    # Clean up null nested objects that would fail Pydantic validation
    # (parser may return {"name": null} for optional party fields)
    if document_type == "bol":
        for party_field in ("consignee", "shipper", "carrier"):
            val = parsed.get(party_field)
            if isinstance(val, dict) and not val.get("name"):
                if party_field in ("shipper", "carrier"):
                    # Required fields — set a placeholder
                    val["name"] = "Unknown"
                else:
                    # Optional — set to None
                    parsed[party_field] = None

    # Validate through Pydantic
    try:
        if document_type == "bol":
            validated = BOLData(**parsed)
        else:
            validated = ClaimData(**parsed)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parsed data failed validation: {e}")

    return validated.model_dump()


# ─── Full Pipeline Endpoint (demo button convenience) ────────────────────────

@app.post("/api/full-analysis")
async def full_analysis(request: AnalyzeRequest) -> FullAnalysisResponse:
    """
    Run the complete pipeline: analyze + generate letter.
    Convenience endpoint for the frontend demo button.
    """
    # Step 1: Carmack analysis
    analysis = analyze_claim(
        bol=request.bol_data,
        claim=request.claim_data,
        delivery_date=request.delivery_date,
    )
    
    # Step 2: Generate dispute letter (graceful fallback if not implemented yet)
    try:
        letter = await generate_dispute_letter(
            analysis=analysis,
            bol=request.bol_data,
            claim=request.claim_data,
        )
    except NotImplementedError:
        letter = DisputeLetter(
            letter_text="Letter generation pending — teammate implementing this module.",
            citations=[],
            recommended_position=analysis.liability.recommended_position,
        )

    return FullAnalysisResponse(
        bol_data=request.bol_data,
        claim_data=request.claim_data,
        analysis=analysis,
        letter=letter,
    )


# ─── Pre-Screen Endpoint ────────────────────────────────────────────────────

@app.post("/api/pre-screen")
async def pre_screen_endpoint(request: PreScreenRequest) -> PreScreenResponse:
    """Pre-screen a BOL for risk factors before accepting a load."""
    result = pre_screen_bol(request.bol_data)
    return PreScreenResponse(result=result)


# ─── Health Check ────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "loadshield"}


# ─── Serve Frontend ─────────────────────────────────────────────────────────

import pathlib

FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{path:path}")
async def serve_static(path: str):
    file = FRONTEND_DIR / path
    if file.exists() and file.is_file():
        return FileResponse(file)
    return FileResponse(FRONTEND_DIR / "index.html")
