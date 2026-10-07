"""Versioned contract used unchanged by analysis, persistence and UI."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from backend.taxonomy import LABELS, canonical_label


class Contract(BaseModel):
    model_config = {'extra': 'forbid'}


class Page(Contract):
    page_number: int = Field(ge=1)
    text: str


class RuleMatch(Contract):
    rule: str
    category: str
    pattern: str
    matched_text: str
    start_offset: int
    end_offset: int
    rule_strength: float = Field(default=1.0, ge=0, le=1)


class Finding(Contract):
    category: str
    severity: Literal['low', 'medium', 'high', 'critical']
    evidence_strength: float = Field(ge=0, le=1)
    detection_method: Literal['rule', 'model', 'hybrid']
    explanation: str
    recommendation: str


class Clause(Contract):
    clause_id: int
    page_number: int | None
    text: str
    start_offset: int | None = None
    end_offset: int | None = None
    predicted_label: str = 'no_risk'
    model_label: str | None = None
    model_confidence: float | None = Field(default=None, ge=0, le=1)
    class_probabilities: dict[str, float] = Field(default_factory=dict)
    rule_matches: list[RuleMatch] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    detection_method: Literal['rule', 'model', 'hybrid', 'safe'] = 'safe'
    severity: Literal['low', 'medium', 'high', 'critical'] = 'low'
    disagreement: bool = False
    explanation: str = ''
    recommendation: str = ''

    @field_validator('predicted_label', 'model_label')
    @classmethod
    def validate_label(cls, value):
        return canonical_label(value) if value is not None else None

    @field_validator('class_probabilities')
    @classmethod
    def validate_probabilities(cls, value):
        if value and (set(value) != set(LABELS) or any(not 0 <= x <= 1 for x in value.values()) or abs(sum(value.values())-1) > .001):
            raise ValueError('Probabilities must cover the complete taxonomy and sum to one')
        return value


class ModelStatus(Contract):
    mode: Literal['hybrid', 'rule_only', 'legacy_unverified'] = 'rule_only'
    model_loaded: bool = False
    model_name: str | None = None
    base_model: str = 'ProsusAI/finbert'
    version: str | None = None
    dataset_version: str | None = None
    labels: list[str] = Field(default_factory=lambda: list(LABELS))
    device: str = 'cpu'
    load_error: str | None = 'No RiskLens classifier configured'


class DocumentClassification(Contract):
    document_type: Literal['loan','credit_card','insurance','investment','lease','other_financial','unknown'] = 'unknown'
    classification_strength: float = Field(default=0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    method: str = 'rule'


class ScoreBreakdown(Contract):
    formula_version: str = 'risklens-triage-v1'
    strongest_evidence: float = 0
    top_three_mean: float = 0
    category_diversity: float = 0
    category_contributions: dict[str, float] = Field(default_factory=dict)
    score: float = Field(default=0, ge=0, le=100)


class AnalysisResult(Contract):
    schema_version: int = 1
    document_id: int | None = None
    filename: str
    sha256: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    classification: DocumentClassification
    page_count: int
    text_page_count: int
    clause_count: int
    clauses: list[Clause]
    model_status: ModelStatus
    mode: Literal['hybrid','rule_only','legacy_unverified']
    risk_score: float = Field(ge=0, le=100)
    overall_risk: Literal['Low','Moderate','High','Critical']
    scoring: ScoreBreakdown
    severity_distribution: dict[str, int]
    category_distribution: dict[str, int]
    health: dict[str, float | None]
    executive_summary: str
    recommended_actions: list[str]
    disclaimer: str = 'RiskLens provides informational analysis, not legal, insurance, lending or investment advice.'
    legacy_unverified: bool = False
