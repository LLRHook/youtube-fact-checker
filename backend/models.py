from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TaskStatus(str, Enum):  # noqa: UP042 - preserve the specified public enum bases
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"


class ClaimCategory(str, Enum):  # noqa: UP042 - preserve the existing public enum bases
    FACT = "fact"
    OPINION = "opinion"
    UNCLEAR = "unclear"


class CheckRequest(BaseModel):
    youtube_url: str = Field(..., max_length=500)


class Verdict(str, Enum):  # noqa: UP042 - the plan explicitly specifies str, Enum
    TRUE = "true"
    MOSTLY_TRUE = "mostly_true"
    MIXED = "mixed"
    MOSTLY_FALSE = "mostly_false"
    FALSE = "false"
    UNVERIFIABLE = "unverifiable"
    OPINION = "opinion"


def legacy_verdict(category, truth_percentage):
    if category == "opinion":
        return "opinion"
    if category == "unclear":
        return "unverifiable"
    for threshold, verdict in ((85, "true"), (65, "mostly_true"), (40, "mixed"), (20, "mostly_false")):
        if truth_percentage >= threshold:
            return verdict
    return "false"


class Source(BaseModel):
    title: str
    url: str
    snippet: str = ""
    domain: str = ""
    reliability: str = "unknown"
    kind: str = "web"
    rating: str = ""
    stance: str = ""
    quote: str = ""


class Claim(BaseModel):
    id: str
    text: str
    timestamp_seconds: float = 0
    truth_percentage: int = 50
    confidence: float = 0.5
    reasoning: str = ""
    sources: list[Source] = Field(default_factory=list)
    category: ClaimCategory = ClaimCategory.FACT
    verdict: Verdict = Verdict.MIXED

    @model_validator(mode="before")
    @classmethod
    def default_verdict(cls, data):
        if isinstance(data, dict) and not data.get("verdict"):
            data = {**data, "verdict": legacy_verdict(data.get("category", "fact"), data.get("truth_percentage", 50))}
        return data


class CheckResult(BaseModel):
    video_title: str = ""
    video_id: str = ""
    video_duration_seconds: float = 0
    transcript_text: str = ""
    claims: list[Claim] = []
    overall_truth_percentage: int = 0
    summary: str = ""
    processing_time_seconds: float = 0


class PublicVideoSummary(BaseModel):
    id: str
    title: str = ""
    channel: str = ""
    public_score: int = 0
    claim_count: int = 0
    created_at: str = ""
    verdict_counts: dict[str, int] = Field(default_factory=dict)
    published_at: str = ""
    thumbnail_url: str = ""


class PublicClaimDetail(BaseModel):
    index: int = 0
    checkworthiness: int = 0
    quote: str = ""
    speaker: str = ""
    topic: str = ""
    verdict: Verdict
    confidence_label: str = ""
    corrected_claim: str = ""
    relies_on_general_knowledge: bool = False
    feedback: dict = Field(default_factory=lambda: {"helpful": 0, "not_helpful": 0})
    text: str = ""
    timestamp_seconds: float = 0
    truth_percentage: int = 50
    confidence: float = 0.5
    reasoning: str = ""
    category: ClaimCategory = ClaimCategory.FACT
    sources: list[Source] = []


class PublicVideoDetail(BaseModel):
    id: str
    title: str = ""
    channel: str = ""
    youtube_url: str = ""
    duration_seconds: float = 0
    overall_truth_percentage: int = 0
    public_score: int | None = None
    summary: str = ""
    processing_time_seconds: float = 0
    created_at: str = ""
    claims: list[PublicClaimDetail] = Field(default_factory=list)
    channel_id: str = ""
    published_at: str = ""
    key_issues: list[str] = Field(default_factory=list)
    verdict_counts: dict[str, int] = Field(default_factory=dict)
    pipeline_version: int = 1
    model: str = ""
    thumbnail_url: str = ""


class ChannelSummary(BaseModel):
    channel: str
    video_count: int = 0
    avg_score: float = 0


class ChannelDetail(BaseModel):
    channel: str
    video_count: int = 0
    avg_score: float = 0
    videos: list[PublicVideoSummary] = []


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: str = ""
    stage: str = ""
    completed: int = 0
    total: int = 0
    video: dict | None = None
    claims: list[PublicClaimDetail] = Field(default_factory=list)
    data: CheckResult | None = None
    error: str | None = None


def claim_row_to_public(row: dict, feedback: dict | None = None) -> PublicClaimDetail:
    confidence = row.get("confidence", 0.5)
    category = row.get("category", "fact")
    if category not in {"fact", "opinion", "unclear"}:
        category = "fact"
    values = {name: row[name] for name in PublicClaimDetail.model_fields if name in row}
    values.update(
        index=row.get("claim_index", row.get("index", 0)),
        verdict=row.get("verdict") or legacy_verdict(category, row.get("truth_percentage", 50)),
        confidence_label=row.get("confidence_label")
        or ("high" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "low"),
        category=category,
        sources=[Source(**source) for source in row.get("sources", [])],
        feedback=feedback or {"helpful": 0, "not_helpful": 0},
    )
    return PublicClaimDetail(**values)
