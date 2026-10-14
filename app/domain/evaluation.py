from dataclasses import dataclass, field
from typing import Literal


ConfidenceLevel = Literal["low", "medium", "high"]
ResultSource = Literal["rule", "ai"]


@dataclass
class CriterionResult:
    criterion: str
    score: int
    evidence: str
    concern: str
    suggestion: str
    confidence: ConfidenceLevel = "medium"
    source: ResultSource = "rule"

    def to_dict(self) -> dict:
        return {
            "criterion": self.criterion,
            "score": self.score,
            "evidence": self.evidence,
            "concern": self.concern,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CriterionResult":
        return cls(
            criterion=data["criterion"],
            score=int(data["score"]),
            evidence=data.get("evidence", ""),
            concern=data.get("concern", ""),
            suggestion=data.get("suggestion", ""),
            confidence=data.get("confidence", "medium"),
            source=data.get("source", "rule"),
        )


@dataclass
class Evaluation:
    submission_id: str
    results: list[CriterionResult] = field(default_factory=list)
    summary: str = ""

    def get_result(self, criterion_name: str) -> CriterionResult | None:
        for r in self.results:
            if r.criterion.lower() == criterion_name.lower():
                return r
        return None

    def to_dict(self) -> dict:
        return {
            "submission_id": self.submission_id,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Evaluation":
        return cls(
            submission_id=data["submission_id"],
            results=[CriterionResult.from_dict(r) for r in data.get("results", [])],
            summary=data.get("summary", ""),
        )
