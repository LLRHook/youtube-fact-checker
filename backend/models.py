from pydantic import BaseModel
from enum import Enum


class TaskStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"


class ClaimCategory(str, Enum):
    FACT = "fact"
    OPINION = "opinion"
    UNCLEAR = "unclear"


class CheckRequest(BaseModel):
    youtube_url: str


class Source(BaseModel):
    title: str
    url: str
    snippet: str = ""


class Claim(BaseModel):
    id: str
    text: str
    timestamp_seconds: float = 0
    truth_percentage: int = 50
    confidence: float = 0.5
    reasoning: str = ""
    sources: list[Source] = []
    category: ClaimCategory = ClaimCategory.FACT


class CheckResult(BaseModel):
    video_title: str = ""
    video_id: str = ""
    video_duration_seconds: float = 0
    transcript_text: str = ""
    claims: list[Claim] = []
    overall_truth_percentage: int = 0
    summary: str = ""
    processing_time_seconds: float = 0


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: str = ""
    data: CheckResult | None = None
    error: str | None = None


# --- Public models ---


class PublicVideoSummary(BaseModel):
    id: str
    title: str = ""
    channel: str = ""
    public_score: int = 0
    claim_count: int = 0
    created_at: str = ""


class PublicClaimDetail(BaseModel):
    text: str = ""
    timestamp_seconds: float = 0
    truth_percentage: int = 50
    confidence: float = 0.5
    reasoning: str = ""
    category: str = "fact"
    sources: list[Source] = []


class PublicVideoDetail(BaseModel):
    id: str
    title: str = ""
    channel: str = ""
    youtube_url: str = ""
    duration_seconds: float = 0
    overall_truth_percentage: int = 0
    public_score: int = 0
    summary: str = ""
    processing_time_seconds: float = 0
    created_at: str = ""
    claims: list[PublicClaimDetail] = []


class ChannelSummary(BaseModel):
    channel: str
    video_count: int = 0
    avg_score: float = 0


class ChannelDetail(BaseModel):
    channel: str
    video_count: int = 0
    avg_score: float = 0
    videos: list[PublicVideoSummary] = []


