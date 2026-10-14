from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid

from app.domain.design_document import DesignDocument


class SubmissionStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InvalidStateTransitionError(Exception):
    """Raised when an illegal status change is attempted on a submission."""
    pass


# Map of current_status -> set of allowed next statuses
ALLOWED_TRANSITIONS: dict[SubmissionStatus, set[SubmissionStatus]] = {
    SubmissionStatus.SUBMITTED: {SubmissionStatus.EVALUATING},
    SubmissionStatus.EVALUATING: {SubmissionStatus.COMPLETED, SubmissionStatus.FAILED},
    SubmissionStatus.FAILED: {SubmissionStatus.EVALUATING},
    SubmissionStatus.COMPLETED: set(),  # Terminal state
}


@dataclass
class Submission:
    id: str
    attempt_id: str
    design_document: DesignDocument
    idempotency_key: str
    status: SubmissionStatus = SubmissionStatus.SUBMITTED
    error_message: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def create(
        cls,
        attempt_id: str,
        design_document: DesignDocument,
        idempotency_key: str,
        submission_id: str | None = None,
    ) -> "Submission":
        # Validate the design document before creation
        design_document.validate()
        return cls(
            id=submission_id or str(uuid.uuid4()),
            attempt_id=attempt_id,
            design_document=design_document,
            idempotency_key=idempotency_key,
            status=SubmissionStatus.SUBMITTED,
        )

    def transition_to(
        self,
        new_status: SubmissionStatus,
        error_message: str | None = None,
    ) -> None:
        """Enforces legal status transitions according to the state machine."""
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition submission {self.id} from {self.status.value} to {new_status.value}. "
                f"Allowed transitions: {[s.value for s in allowed] or 'None (terminal state)'}."
            )
        self.status = new_status
        if new_status == SubmissionStatus.FAILED:
            self.error_message = error_message or "Evaluation failed."
        elif new_status == SubmissionStatus.EVALUATING:
            self.error_message = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "attempt_id": self.attempt_id,
            "design_document": self.design_document.to_dict(),
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Submission":
        return cls(
            id=data["id"],
            attempt_id=data["attempt_id"],
            design_document=DesignDocument.from_dict(data["design_document"]),
            idempotency_key=data["idempotency_key"],
            status=SubmissionStatus(data["status"]),
            error_message=data.get("error_message"),
            created_at=data.get("created_at", ""),
        )
