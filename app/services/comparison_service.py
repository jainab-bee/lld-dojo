from dataclasses import dataclass, field
import difflib

from app.domain.attempt import Attempt
from app.domain.evaluation import CriterionResult, Evaluation


@dataclass
class CriterionDiff:
    criterion: str
    score_a: int
    score_b: int
    score_delta: int
    concern_a: str
    concern_b: str


@dataclass
class ComparisonResult:
    problem_id: str
    attempt_a_number: int
    attempt_b_number: int
    criterion_diffs: list[CriterionDiff] = field(default_factory=list)
    resolved_concerns: list[dict[str, str]] = field(default_factory=list)
    still_open_concerns: list[dict[str, str]] = field(default_factory=list)
    new_concerns: list[dict[str, str]] = field(default_factory=list)
    total_score_delta: int = 0


class ComparisonService:
    """Compares two evaluated attempts for the same problem.
    
    Identifies score deltas per criterion and classifies concerns as
    resolved, still open, or newly introduced.
    """

    SIMILARITY_THRESHOLD = 0.55

    def compare(
        self,
        attempt_a: Attempt,
        eval_a: Evaluation,
        attempt_b: Attempt,
        eval_b: Evaluation,
    ) -> ComparisonResult:
        criterion_diffs: list[CriterionDiff] = []
        resolved_concerns: list[dict[str, str]] = []
        still_open_concerns: list[dict[str, str]] = []
        new_concerns: list[dict[str, str]] = []

        results_a = {r.criterion.lower(): r for r in eval_a.results}
        results_b = {r.criterion.lower(): r for r in eval_b.results}

        # Union of all criteria names preserves standard rubric order
        all_criteria_keys = list(results_a.keys())
        for k in results_b.keys():
            if k not in all_criteria_keys:
                all_criteria_keys.append(k)

        total_delta = 0

        for key in all_criteria_keys:
            res_a = results_a.get(key)
            res_b = results_b.get(key)

            criterion_name = (res_b or res_a).criterion
            score_a = res_a.score if res_a else 0
            score_b = res_b.score if res_b else 0
            delta = score_b - score_a
            total_delta += delta

            concern_a = (res_a.concern or "").strip() if res_a else ""
            concern_b = (res_b.concern or "").strip() if res_b else ""

            criterion_diffs.append(
                CriterionDiff(
                    criterion=criterion_name,
                    score_a=score_a,
                    score_b=score_b,
                    score_delta=delta,
                    concern_a=concern_a,
                    concern_b=concern_b,
                )
            )

            # Classify concerns
            self._classify_concerns(
                criterion_name=criterion_name,
                concern_a=concern_a,
                concern_b=concern_b,
                score_a=score_a,
                score_b=score_b,
                resolved=resolved_concerns,
                still_open=still_open_concerns,
                new_list=new_concerns,
            )

        return ComparisonResult(
            problem_id=attempt_a.problem_id,
            attempt_a_number=attempt_a.attempt_number,
            attempt_b_number=attempt_b.attempt_number,
            criterion_diffs=criterion_diffs,
            resolved_concerns=resolved_concerns,
            still_open_concerns=still_open_concerns,
            new_concerns=new_concerns,
            total_score_delta=total_delta,
        )

    def _classify_concerns(
        self,
        criterion_name: str,
        concern_a: str,
        concern_b: str,
        score_a: int,
        score_b: int,
        resolved: list[dict[str, str]],
        still_open: list[dict[str, str]],
        new_list: list[dict[str, str]],
    ) -> None:
        if concern_a and not concern_b:
            resolved.append({"criterion": criterion_name, "concern": concern_a})
            return

        if not concern_a and concern_b:
            new_list.append({"criterion": criterion_name, "concern": concern_b})
            return

        if concern_a and concern_b:
            # Check text similarity
            similarity = difflib.SequenceMatcher(
                None, concern_a.lower(), concern_b.lower()
            ).ratio()

            if similarity >= self.SIMILARITY_THRESHOLD:
                # Same concern persisted
                still_open.append({"criterion": criterion_name, "concern": concern_b})
            else:
                # Different concern. If score improved, old concern resolved and new one emerged
                resolved.append({"criterion": criterion_name, "concern": concern_a})
                new_list.append({"criterion": criterion_name, "concern": concern_b})
