import logging
from typing import Any

from app.domain.design_document import DesignDocument
from app.domain.evaluation import CriterionResult, Evaluation
from app.domain.problem import Problem
from app.domain.rubric import Rubric
from app.domain.submission import Submission, SubmissionStatus
from app.evaluators.base import Evaluator

logger = logging.getLogger(__name__)


class EvaluationService:
    """Orchestrates submission saving, lifecycle transitions, evaluator execution,
    and result persistence.
    """

    def __init__(
        self,
        repository: Any,
        evaluators: list[Evaluator],
        rubric: Rubric | None = None,
        problems: dict[str, Problem] | None = None,
    ):
        self.repository = repository
        self.evaluators = evaluators
        self.rubric = rubric or Rubric.standard_lld_rubric()
        self.problems = problems or {}

    def submit_design(
        self,
        attempt_id: str,
        design_document: DesignDocument,
        idempotency_key: str,
    ) -> tuple[Submission, bool]:
        """Creates and saves a submission.
        
        Returns (submission, is_new).
        If idempotency_key was already used, returns existing submission without re-evaluating.
        """
        existing = self.repository.get_submission_by_idempotency_key(idempotency_key)
        if existing:
            return existing, False

        # Validate design document before saving
        design_document.validate()

        submission = Submission.create(
            attempt_id=attempt_id,
            design_document=design_document,
            idempotency_key=idempotency_key,
        )
        # Step 1: Save submission first
        self.repository.save_submission(submission)
        return submission, True

    def process_evaluation(self, submission_id: str) -> Evaluation:
        """Processes the evaluation pipeline for a submission:
        1. Verifies submission exists
        2. Transitions to EVALUATING
        3. Runs evaluators (keeping rule-based results safely)
        4. Merges outputs
        5. Saves evaluation and marks COMPLETED (or FAILED if an evaluator errored).
        """
        submission = self.repository.get_submission(submission_id)
        if not submission:
            raise ValueError(f"Submission {submission_id} not found.")

        # Check if already completed
        if submission.status == SubmissionStatus.COMPLETED:
            existing_eval = self.repository.get_evaluation(submission_id)
            if existing_eval:
                return existing_eval

        # Step 2: Mark EVALUATING
        if submission.status != SubmissionStatus.EVALUATING:
            submission.transition_to(SubmissionStatus.EVALUATING)
            self.repository.update_submission(submission)

        # Lookup problem
        attempt = self.repository.get_attempt(submission.attempt_id)
        problem = self.problems.get(attempt.problem_id) if attempt else None

        collected_results: list[CriterionResult] = []
        rule_results: list[CriterionResult] = []
        evaluation_failed = False
        error_msg = ""

        # Step 3: Run all evaluators
        for evaluator in self.evaluators:
            try:
                results = evaluator.evaluate(submission, self.rubric, problem=problem)
                # Keep separate record of rule-based results
                if any(r.source == "rule" for r in results):
                    rule_results.extend([r for r in results if r.source == "rule"])
                collected_results.extend(results)
            except Exception as exc:
                logger.exception("Evaluator %s failed: %s", type(evaluator).__name__, exc)
                evaluation_failed = True
                error_msg = str(exc)
                break

        # Step 4 & 5: Handle failure vs success
        if evaluation_failed:
            # Keep rule-based results so the learner still gets deterministic feedback
            fallback_results = rule_results or collected_results
            summary = (
                f"Evaluation failed during advanced review ({error_msg}). "
                "Deterministic rule checks have been preserved below. You may retry evaluation."
            )
            evaluation = Evaluation(
                submission_id=submission.id,
                results=fallback_results,
                summary=summary,
            )
            self.repository.save_evaluation(evaluation)
            submission.transition_to(
                SubmissionStatus.FAILED,
                error_message=f"Evaluation encountered an issue: {error_msg}. Rule checks preserved. Click Retry.",
            )
            self.repository.update_submission(submission)
            return evaluation

        # Merge results: when multiple evaluators run, prefer AI review for depth,
        # but keep severe rule flags if any
        merged_results = self._merge_results(collected_results)
        summary = self._generate_summary(merged_results)
        evaluation = Evaluation(
            submission_id=submission.id,
            results=merged_results,
            summary=summary,
        )

        self.repository.save_evaluation(evaluation)
        submission.transition_to(SubmissionStatus.COMPLETED)
        self.repository.update_submission(submission)
        return evaluation

    def retry_evaluation(self, submission_id: str) -> Evaluation:
        """Retries a failed evaluation."""
        submission = self.repository.get_submission(submission_id)
        if not submission:
            raise ValueError(f"Submission {submission_id} not found.")

        if submission.status != SubmissionStatus.FAILED:
            raise ValueError(
                f"Cannot retry submission in status {submission.status.value}. Only FAILED can be retried."
            )

        submission.transition_to(SubmissionStatus.EVALUATING)
        self.repository.update_submission(submission)
        return self.process_evaluation(submission_id)

    def _merge_results(self, results: list[CriterionResult]) -> list[CriterionResult]:
        """Merges results across evaluators by criterion."""
        merged: dict[str, CriterionResult] = {}
        for r in results:
            key = r.criterion.lower()
            if key not in merged:
                merged[key] = r
            else:
                existing = merged[key]
                # If existing is rule and incoming is AI, prefer AI review
                if existing.source == "rule" and r.source == "ai":
                    # If rule noted a critical missing component, adjust or preserve note
                    if existing.score <= 1:
                        r.concern = f"{r.concern} (Rule check warning: {existing.concern})".strip()
                    merged[key] = r
                elif existing.source == "ai" and r.source == "ai":
                    merged[key] = r

        # Ensure all rubric criteria are in standard order
        ordered: list[CriterionResult] = []
        for crit in self.rubric.criteria:
            key = crit.name.lower()
            if key in merged:
                ordered.append(merged[key])
            else:
                ordered.append(
                    CriterionResult(
                        criterion=crit.name,
                        score=3,
                        evidence="No direct feedback generated.",
                        concern="Criteria could not be fully assessed.",
                        suggestion="Provide additional details in your design.",
                        confidence="low",
                        source="rule",
                    )
                )
        return ordered

    def _generate_summary(self, results: list[CriterionResult]) -> str:
        if not results:
            return "No feedback generated."
        avg_score = sum(r.score for r in results) / len(results)
        strengths = [r.criterion for r in results if r.score >= 4]
        improvements = [r.criterion for r in results if r.score <= 2]

        parts = [f"Average rubric score: {avg_score:.1f} / 5.0."]
        if strengths:
            parts.append(f"Strong points: {', '.join(strengths)}.")
        if improvements:
            parts.append(f"Key areas to refine: {', '.join(improvements)}.")
        else:
            parts.append("Good coverage across all standard criteria.")
        return " ".join(parts)
