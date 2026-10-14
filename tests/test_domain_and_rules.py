import pytest

from app.domain.design_document import DesignDocument
from app.domain.problem import Problem
from app.domain.rubric import Rubric
from app.domain.submission import (
    InvalidStateTransitionError,
    Submission,
    SubmissionStatus,
)
from app.evaluators.rule_based import RuleBasedEvaluator


def make_valid_doc() -> DesignDocument:
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


def test_valid_design_document_validates_cleanly():
    doc = make_valid_doc()
    doc.validate()
    text = doc.as_text()
    assert "=== 1. ASSUMPTIONS ===" in text
    assert "=== 5. TRADEOFFS ===" in text


def test_empty_section_raises_validation_error():
    doc = make_valid_doc()
    doc.assumptions = ""
    with pytest.raises(ValueError, match="'Assumptions' section is empty"):
        doc.validate()


def test_too_short_section_raises_validation_error():
    doc = make_valid_doc()
    doc.tradeoffs = "Too short"
    with pytest.raises(ValueError, match="'Tradeoffs' is too brief"):
        doc.validate()


def test_legal_status_transitions():
    doc = make_valid_doc()
    sub = Submission.create(
        attempt_id="att-1",
        design_document=doc,
        idempotency_key="key-123",
    )
    assert sub.status == SubmissionStatus.SUBMITTED

    # SUBMITTED -> EVALUATING
    sub.transition_to(SubmissionStatus.EVALUATING)
    assert sub.status == SubmissionStatus.EVALUATING

    # EVALUATING -> COMPLETED
    sub.transition_to(SubmissionStatus.COMPLETED)
    assert sub.status == SubmissionStatus.COMPLETED


def test_failed_transition_and_retry():
    doc = make_valid_doc()
    sub = Submission.create(
        attempt_id="att-1",
        design_document=doc,
        idempotency_key="key-123",
    )
    sub.transition_to(SubmissionStatus.EVALUATING)

    # EVALUATING -> FAILED
    sub.transition_to(SubmissionStatus.FAILED, error_message="LLM timeout")
    assert sub.status == SubmissionStatus.FAILED
    assert sub.error_message == "LLM timeout"

    # FAILED -> EVALUATING (Retry)
    sub.transition_to(SubmissionStatus.EVALUATING)
    assert sub.status == SubmissionStatus.EVALUATING
    assert sub.error_message is None


def test_illegal_status_transitions_raise():
    doc = make_valid_doc()
    sub = Submission.create(
        attempt_id="att-1",
        design_document=doc,
        idempotency_key="key-123",
    )

    # Cannot go directly from SUBMITTED to COMPLETED
    with pytest.raises(InvalidStateTransitionError):
        sub.transition_to(SubmissionStatus.COMPLETED)

    # Cannot go directly from SUBMITTED to FAILED
    with pytest.raises(InvalidStateTransitionError):
        sub.transition_to(SubmissionStatus.FAILED)

    # Move to EVALUATING, then COMPLETED
    sub.transition_to(SubmissionStatus.EVALUATING)
    sub.transition_to(SubmissionStatus.COMPLETED)

    # Terminal state: cannot transition from COMPLETED to anything
    with pytest.raises(InvalidStateTransitionError):
        sub.transition_to(SubmissionStatus.EVALUATING)

    with pytest.raises(InvalidStateTransitionError):
        sub.transition_to(SubmissionStatus.FAILED)


def test_rule_based_evaluator_flags_missing_relationships():
    # Design doc with no relationship keywords
    doc = DesignDocument(
        assumptions="Lot has multiple floors and error handling.",
        classes_and_responsibilities="class ParkingLot handles all logic. class Vehicle holds license plate.",
        relationships="All classes communicate with each other directly in the code.",  # No has-a, is-a, etc.
        key_flow="Vehicle enters, gets ticket, parks, pays fee, leaves.",
        tradeoffs="Tradeoff: simple design vs future changes instead of complex abstractions.",
    )
    sub = Submission(
        id="sub-1",
        attempt_id="att-1",
        design_document=doc,
        idempotency_key="key-1",
        status=SubmissionStatus.EVALUATING,
    )
    rubric = Rubric.standard_lld_rubric()
    evaluator = RuleBasedEvaluator()

    results = evaluator.evaluate(sub, rubric)
    coupling_result = next(r for r in results if r.criterion == "Coupling and Cohesion")
    assert coupling_result.score <= 1
    assert "No structural relationship keywords" in coupling_result.concern


def test_rule_based_evaluator_flags_missing_sections():
    # Create doc with empty relationships
    doc = DesignDocument(
        assumptions="",
        classes_and_responsibilities="No class syntax here at all, just plain words describing things.",
        relationships="",
        key_flow="",
        tradeoffs="",
    )
    sub = Submission(
        id="sub-1",
        attempt_id="att-1",
        design_document=doc,
        idempotency_key="key-1",
        status=SubmissionStatus.EVALUATING,
    )
    rubric = Rubric.standard_lld_rubric()
    evaluator = RuleBasedEvaluator()

    results = evaluator.evaluate(sub, rubric)
    class_res = next(r for r in results if r.criterion == "Class Responsibilities")
    assert class_res.score <= 1
    rel_res = next(r for r in results if r.criterion == "Coupling and Cohesion")
    assert rel_res.score == 0
    assert "Relationships section is completely empty" in rel_res.evidence
