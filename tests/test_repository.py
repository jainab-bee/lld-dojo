from pathlib import Path

from app.domain.attempt import Attempt
from app.domain.design_document import DesignDocument
from app.domain.evaluation import CriterionResult, Evaluation
from app.domain.submission import Submission, SubmissionStatus
from app.repository.attempt_repository import AttemptRepository


def test_attempt_history_persists_across_fresh_repository_instance(tmp_path: Path):
    db_file = tmp_path / "test_history.db"

    # Instance 1: write attempt, submission, and evaluation
    repo1 = AttemptRepository(db_file)

    attempt = Attempt.create(problem_id="elevator-system", attempt_number=1, attempt_id="att-100")
    repo1.save_attempt(attempt)

    doc = DesignDocument(
        assumptions="Building has 20 floors and 4 elevator cars.",
        classes_and_responsibilities="class ElevatorController coordinates cars. class ElevatorCar moves between floors.",
        relationships="ElevatorController has-a list of ElevatorCars. Door belongs to ElevatorCar.",
        key_flow="Hall call made -> Controller selects nearest idle car -> Car moves to floor.",
        tradeoffs="Chose LOOK algorithm instead of FCFS to minimize wait times.",
    )
    submission = Submission.create(
        attempt_id=attempt.id,
        design_document=doc,
        idempotency_key="unique-elev-1",
        submission_id="sub-100",
    )
    repo1.save_submission(submission)

    evaluation = Evaluation(
        submission_id=submission.id,
        results=[
            CriterionResult(
                criterion="Requirement Coverage",
                score=4,
                evidence="Controller selects nearest idle car",
                concern="High load capacity not checked",
                suggestion="Add weight sensor logic",
                confidence="high",
                source="ai",
            )
        ],
        summary="Good core design with clear elevator car controls.",
    )
    repo1.save_evaluation(evaluation)

    # Instance 2: fresh repository instance connecting to the same DB file
    repo2 = AttemptRepository(db_file)

    fetched_attempt = repo2.get_attempt("att-100")
    assert fetched_attempt is not None
    assert fetched_attempt.problem_id == "elevator-system"
    assert fetched_attempt.attempt_number == 1

    fetched_sub = repo2.get_submission("sub-100")
    assert fetched_sub is not None
    assert fetched_sub.idempotency_key == "unique-elev-1"
    assert fetched_sub.design_document.assumptions == doc.assumptions

    fetched_eval = repo2.get_evaluation("sub-100")
    assert fetched_eval is not None
    assert fetched_eval.summary == evaluation.summary
    assert len(fetched_eval.results) == 1
    assert fetched_eval.results[0].criterion == "Requirement Coverage"
    assert fetched_eval.results[0].score == 4
