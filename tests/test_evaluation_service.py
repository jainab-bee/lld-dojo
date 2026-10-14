import pytest

from app.domain.attempt import Attempt
from app.domain.design_document import DesignDocument
from app.domain.evaluation import CriterionResult, Evaluation
from app.domain.problem import Problem
from app.domain.rubric import Rubric
from app.domain.submission import Submission, SubmissionStatus
from app.evaluators.base import Evaluator
from app.evaluators.llm_evaluator import LLMEvaluator
from app.evaluators.rule_based import RuleBasedEvaluator
from app.llm.fake_client import FakeLLMClient
from app.services.evaluation_service import EvaluationService


class InMemoryRepository:
    def __init__(self):
        self.attempts: dict[str, Attempt] = {}
        self.submissions: dict[str, Submission] = {}
        self.submissions_by_key: dict[str, Submission] = {}
        self.evaluations: dict[str, Evaluation] = {}

    def save_attempt(self, attempt: Attempt) -> None:
        self.attempts[attempt.id] = attempt

    def get_attempt(self, attempt_id: str) -> Attempt | None:
        return self.attempts.get(attempt_id)

    def save_submission(self, submission: Submission) -> None:
        self.submissions[submission.id] = submission
        self.submissions_by_key[submission.idempotency_key] = submission

    def get_submission(self, submission_id: str) -> Submission | None:
        return self.submissions.get(submission_id)

    def get_submission_by_idempotency_key(self, key: str) -> Submission | None:
        return self.submissions_by_key.get(key)

    def update_submission(self, submission: Submission) -> None:
        self.submissions[submission.id] = submission
        self.submissions_by_key[submission.idempotency_key] = submission

    def save_evaluation(self, evaluation: Evaluation) -> None:
        self.evaluations[evaluation.submission_id] = evaluation

    def get_evaluation(self, submission_id: str) -> Evaluation | None:
        return self.evaluations.get(submission_id)


def create_sample_doc() -> DesignDocument:
    return DesignDocument(
        assumptions="Parking lot has multiple floors. Electric vehicles use special spots. Full lot throws error.",
        classes_and_responsibilities=(
            "class ParkingLot manages floors and tickets. "
            "class ParkingSpot tracks availability. "
            "class Ticket records entry timestamp."
        ),
        relationships=(
            "ParkingLot has-a list of ParkingFloors. "
            "ParkingFloor has-a list of ParkingSpots. "
            "Car is-a Vehicle."
        ),
        key_flow=(
            "1. Vehicle arrives. 2. ParkingLot finds nearest spot. "
            "3. Ticket issued. 4. Spot marked occupied. 5. On exit, fee calculated."
        ),
        tradeoffs=(
            "We chose Strategy pattern instead of hardcoded if/else for spot allocation. "
            "Tradeoff: extra classes vs high extensibility."
        ),
    )


def test_idempotency_key_returns_existing_submission_without_re_evaluation():
    repo = InMemoryRepository()
    attempt = Attempt.create(problem_id="parking-lot", attempt_number=1)
    repo.save_attempt(attempt)

    client = FakeLLMClient()
    service = EvaluationService(
        repository=repo,
        evaluators=[RuleBasedEvaluator(), LLMEvaluator(client)],
    )

    doc = create_sample_doc()
    key = "idem-abc-123"

    # First submission
    sub1, is_new1 = service.submit_design(attempt.id, doc, key)
    assert is_new1 is True
    assert sub1.status == SubmissionStatus.SUBMITTED

    # Process evaluation
    service.process_evaluation(sub1.id)
    assert sub1.status == SubmissionStatus.COMPLETED
    assert client.call_count == 1

    # Second submission with the same idempotency key
    sub2, is_new2 = service.submit_design(attempt.id, doc, key)
    assert is_new2 is False
    assert sub2.id == sub1.id

    # Running process_evaluation again on the completed submission does not call LLM again
    service.process_evaluation(sub2.id)
    assert client.call_count == 1


def test_llm_failure_preserves_rules_and_retry_succeeds():
    repo = InMemoryRepository()
    attempt = Attempt.create(problem_id="parking-lot", attempt_number=1)
    repo.save_attempt(attempt)

    # Client configured to fail
    client = FakeLLMClient(should_fail=True, failure_message="Connection timeout")
    service = EvaluationService(
        repository=repo,
        evaluators=[RuleBasedEvaluator(), LLMEvaluator(client)],
    )

    doc = create_sample_doc()
    sub, _ = service.submit_design(attempt.id, doc, "key-fail-1")

    # Step: evaluate. LLM will fail
    evaluation = service.process_evaluation(sub.id)

    # Submission status must end in FAILED
    saved_sub = repo.get_submission(sub.id)
    assert saved_sub.status == SubmissionStatus.FAILED
    assert "Evaluation encountered an issue" in saved_sub.error_message

    # Rule-based results are preserved in evaluation
    assert len(evaluation.results) > 0
    assert any(r.source == "rule" for r in evaluation.results)

    # Fix the client and retry
    client.should_fail = False
    retry_eval = service.retry_evaluation(sub.id)

    # After retry, status is COMPLETED
    updated_sub = repo.get_submission(sub.id)
    assert updated_sub.status == SubmissionStatus.COMPLETED
    assert any(r.source == "ai" for r in retry_eval.results)


def test_llm_invalid_json_handled_without_crashing():
    repo = InMemoryRepository()
    attempt = Attempt.create(problem_id="parking-lot", attempt_number=1)
    repo.save_attempt(attempt)

    client = FakeLLMClient(return_invalid_json=True)
    service = EvaluationService(
        repository=repo,
        evaluators=[RuleBasedEvaluator(), LLMEvaluator(client)],
    )

    doc = create_sample_doc()
    sub, _ = service.submit_design(attempt.id, doc, "key-bad-json")

    # Should not crash; should handle gracefully and set FAILED
    eval_result = service.process_evaluation(sub.id)
    assert sub.status == SubmissionStatus.FAILED
    assert any(r.source == "rule" for r in eval_result.results)


def test_evaluator_swap_plugs_in_without_changing_service_code():
    repo = InMemoryRepository()
    attempt = Attempt.create(problem_id="parking-lot", attempt_number=1)
    repo.save_attempt(attempt)

    # Custom dummy evaluator
    class DummyNewEvaluator(Evaluator):
        def evaluate(self, submission, rubric, problem=None):
            return [
                CriterionResult(
                    criterion="Requirement Coverage",
                    score=5,
                    evidence="Evidence from custom dummy evaluator",
                    concern="No concerns",
                    suggestion="Keep up the good work",
                    confidence="high",
                    source="rule",
                )
            ]

    # Plug into EvaluationService without changing service code
    service = EvaluationService(
        repository=repo,
        evaluators=[DummyNewEvaluator()],
    )

    doc = create_sample_doc()
    sub, _ = service.submit_design(attempt.id, doc, "key-dummy")
    eval_res = service.process_evaluation(sub.id)

    assert sub.status == SubmissionStatus.COMPLETED
    req_res = eval_res.get_result("Requirement Coverage")
    assert req_res is not None
    assert req_res.score == 5
    assert req_res.evidence == "Evidence from custom dummy evaluator"
