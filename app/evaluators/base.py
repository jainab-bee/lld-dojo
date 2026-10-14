# Abstract base class that lets us swap or combine deterministic rules and LLM evaluation without changing callers.
from abc import ABC, abstractmethod

from app.domain.evaluation import CriterionResult
from app.domain.problem import Problem
from app.domain.rubric import Rubric
from app.domain.submission import Submission


class Evaluator(ABC):
    """Base interface for all evaluators."""

    @abstractmethod
    def evaluate(
        self,
        submission: Submission,
        rubric: Rubric,
        problem: Problem | None = None,
    ) -> list[CriterionResult]:
        """Evaluates a submission against a rubric and returns criterion results."""
        pass
