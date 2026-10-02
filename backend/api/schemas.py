"""
backend/api/schemas.py
──────────────────────
Pydantic v2 schemas for NyayaAI API request and response bodies.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ClauseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    clause_number: int
    heading: Optional[str] = None
    text: str
    clause_type: Optional[str] = None
    page: Optional[int] = None


class ContractSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    doc_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    created_at: datetime
    document_id: Optional[int] = None
    clauses_count: Optional[int] = 0


class ContractDetailSchema(ContractSummarySchema):
    clauses: list[ClauseSchema] = []


class IngestTextRequest(BaseModel):
    text: str
    title: Optional[str] = "Untitled Contract"
    filename: Optional[str] = "contract.txt"
    jurisdiction: Optional[str] = "india"


class IngestionResponse(BaseModel):
    document_id: int
    contract_id: int
    title: str
    doc_type: Optional[str] = None
    filename: str
    file_type: str
    clauses_count: int
    message: str


class SectionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    section_number: str
    heading: Optional[str] = None
    text: str
    notes: Optional[str] = None
    citation_str: Optional[str] = None


class LegalSourceSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    short_name: Optional[str] = None
    source_type: str
    jurisdiction: str
    status: str
    citation: Optional[str] = None
    retrieved_on: Optional[str] = None
    sections_count: Optional[int] = 0


class LegalSourceDetailSchema(LegalSourceSummarySchema):
    sections: list[SectionSchema] = []
