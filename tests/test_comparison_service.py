from app.domain.attempt import Attempt
from app.domain.evaluation import CriterionResult, Evaluation
from app.services.comparison_service import ComparisonService


def test_comparison_marks_fixed_concern_as_resolved_and_unfixed_as_still_open():
    attempt_a = Attempt(id="att-1", problem_id="parking-lot", attempt_number=1, created_at="2026-01-01T00:00:00")
    attempt_b = Attempt(id="att-2", problem_id="parking-lot", attempt_number=2, created_at="2026-01-02T00:00:00")

    eval_a = Evaluation(
        submission_id="sub-1",
        results=[
            CriterionResult(
                criterion="Requirement Coverage",
                score=2,
                evidence="Vehicle enters and exits",
                concern="Missing parking ticket generation and payment fee logic.",
                suggestion="Add Ticket class and fee calculation.",
                source="rule",
            ),
            CriterionResult(
                criterion="Coupling and Cohesion",
                score=2,
                evidence="Classes reference each other",
                concern="Tight coupling between controller and spot types.",
                suggestion="Introduce Spot interface.",
                source="rule",
            ),
        ],
        summary="Initial draft with missing requirements.",
    )

    # In attempt B, Requirement Coverage was fixed (concern resolved),
    # but Coupling concern remains the same (unfixed)
    eval_b = Evaluation(
        submission_id="sub-2",
        results=[
            CriterionResult(
                criterion="Requirement Coverage",
                score=5,
                evidence="Ticket issued with timestamp, fee calculated accurately",
                concern="",  # Concern is resolved!
                suggestion="Looks complete.",
                source="ai",
            ),
            CriterionResult(
                criterion="Coupling and Cohesion",
                score=2,
                evidence="Classes reference concrete spot implementations",
                concern="Tight coupling between controller and spot types.",  # Same concern still open
                suggestion="Introduce Spot interface.",
                source="ai",
            ),
        ],
        summary="Improved attempt with requirements addressed.",
    )

    comparison_service = ComparisonService()
    comparison = comparison_service.compare(attempt_a, eval_a, attempt_b, eval_b)

    # Check resolved concerns
    resolved_criteria = [item["criterion"] for item in comparison.resolved_concerns]
    assert "Requirement Coverage" in resolved_criteria

    # Check still open concerns
    still_open_criteria = [item["criterion"] for item in comparison.still_open_concerns]
    assert "Coupling and Cohesion" in still_open_criteria

    # Check score deltas
    req_diff = next(d for d in comparison.criterion_diffs if d.criterion == "Requirement Coverage")
    assert req_diff.score_delta == 3  # 5 - 2
