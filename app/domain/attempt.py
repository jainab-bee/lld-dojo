from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class Attempt:
    id: str
    problem_id: str
    attempt_number: int
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def create(
        cls,
        problem_id: str,
        attempt_number: int,
        attempt_id: str | None = None,
    ) -> "Attempt":
        return cls(
            id=attempt_id or str(uuid.uuid4()),
            problem_id=problem_id,
            attempt_number=attempt_number,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "problem_id": self.problem_id,
            "attempt_number": self.attempt_number,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Attempt":
        return cls(
            id=data["id"],
            problem_id=data["problem_id"],
            attempt_number=int(data["attempt_number"]),
            created_at=data.get("created_at", ""),
        )
