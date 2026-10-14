from pathlib import Path

from app.domain.attempt import Attempt
from app.domain.problem import Problem
from app.repository.attempt_repository import AttemptRepository


class PracticeService:
    """Manages problems, attempt creation, and history aggregation."""

    def __init__(self, repository: AttemptRepository, problems_path: str | Path | None = None):
        self.repository = repository
        if problems_path is None:
            problems_path = Path(__file__).parent.parent / "data" / "problems.json"
        self.problems_path = Path(problems_path)
        self._problems: dict[str, Problem] = {}
        self._load_problems()

    def _load_problems(self) -> None:
        if self.problems_path.exists():
            problems_list = Problem.load_all_from_file(self.problems_path)
            self._problems = {p.id: p for p in problems_list}

    def get_problems(self) -> list[Problem]:
        return list(self._problems.values())

    def get_problem(self, problem_id: str) -> Problem | None:
        return self._problems.get(problem_id)

    def create_attempt(self, problem_id: str) -> Attempt:
        if problem_id not in self._problems:
            raise ValueError(f"Unknown problem '{problem_id}'.")
        attempt_number = self.repository.get_next_attempt_number(problem_id)
        attempt = Attempt.create(problem_id=problem_id, attempt_number=attempt_number)
        self.repository.save_attempt(attempt)
        return attempt

    def get_attempt_with_details(self, attempt_id: str) -> dict | None:
        attempt = self.repository.get_attempt(attempt_id)
        if not attempt:
            return None
        submission = self.repository.get_latest_submission_for_attempt(attempt.id)
        evaluation = self.repository.get_evaluation(submission.id) if submission else None
        problem = self.get_problem(attempt.problem_id)
        return {
            "attempt": attempt,
            "problem": problem,
            "submission": submission,
            "evaluation": evaluation,
        }

    def get_grouped_history(self) -> dict[str, dict]:
        """Returns attempts grouped by problem for the /history page."""
        all_attempts = self.repository.get_all_attempts()
        grouped: dict[str, dict] = {}

        # Initialize with known problems
        for p in self.get_problems():
            grouped[p.id] = {
                "problem": p,
                "attempts": [],
            }

        for attempt in all_attempts:
            if attempt.problem_id not in grouped:
                prob = self.get_problem(attempt.problem_id)
                grouped[attempt.problem_id] = {
                    "problem": prob or Problem(
                        id=attempt.problem_id,
                        title=attempt.problem_id.replace("-", " ").title(),
                        difficulty="N/A",
                        summary="",
                    ),
                    "attempts": [],
                }

            submission = self.repository.get_latest_submission_for_attempt(attempt.id)
            evaluation = self.repository.get_evaluation(submission.id) if submission else None

            scores = {}
            if evaluation:
                for r in evaluation.results:
                    scores[r.criterion] = r.score

            grouped[attempt.problem_id]["attempts"].append(
                {
                    "attempt": attempt,
                    "submission": submission,
                    "evaluation": evaluation,
                    "scores": scores,
                }
            )

        # Sort attempts inside each problem by attempt_number ascending
        for data in grouped.values():
            data["attempts"].sort(key=lambda x: x["attempt"].attempt_number)

        return grouped
