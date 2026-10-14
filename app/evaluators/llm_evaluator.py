import json
import re

from app.domain.evaluation import CriterionResult
from app.domain.problem import Problem
from app.domain.rubric import Rubric
from app.domain.submission import Submission
from app.evaluators.base import Evaluator
from app.llm.client import LLMClient


class LLMEvaluationError(Exception):
    """Raised when the LLM response cannot be parsed or lacks required criteria."""
    pass


class LLMEvaluator(Evaluator):
    """Evaluates an LLD submission using an LLMClient with a structured rubric prompt."""

    def __init__(self, client: LLMClient):
        self.client = client

    def evaluate(
        self,
        submission: Submission,
        rubric: Rubric,
        problem: Problem | None = None,
    ) -> list[CriterionResult]:
        prompt = self._build_prompt(submission, rubric, problem)
        raw_response = self.client.complete(prompt)
        return self._parse_response(raw_response, rubric)

    def _build_prompt(
        self,
        submission: Submission,
        rubric: Rubric,
        problem: Problem | None,
    ) -> str:
        req_lines = ""
        pitfall_lines = ""
        twist = ""
        prob_title = "Low-Level Design Problem"

        if problem:
            prob_title = problem.title
            req_lines = "\n".join(f"- {r}" for r in problem.requirements)
            pitfall_lines = "\n".join(f"- {p}" for p in problem.common_pitfalls)
            twist = problem.change_request

        rubric_lines = "\n".join(
            f"- {c.name}: {c.description} (score 0 to 5)"
            for c in rubric.criteria
        )

        return (
            f"You are a principal software engineer reviewing a learner's Low-Level Design (LLD) submission.\n\n"
            f"PROBLEM: {prob_title}\n\n"
            f"REQUIREMENTS:\n{req_lines or 'Not specified'}\n\n"
            f"COMMON PITFALLS TO WATCH FOR:\n{pitfall_lines or 'Not specified'}\n\n"
            f"CHANGE REQUEST TWIST:\n{twist or 'Not specified'}\n\n"
            f"EVALUATION RUBRIC:\n{rubric_lines}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Accept alternative valid designs. Do not enforce a single reference solution.\n"
            f"2. Every piece of feedback must cite evidence from the learner's own submission.\n"
            f"3. If there is no evidence in the submission for a criterion, write 'No explicit evidence found in submission' - do not invent details.\n"
            f"4. Score each criterion between 0 and 5. Never produce a 100-point total score.\n"
            f"5. Output valid JSON ONLY. Do not write introductory or closing text.\n\n"
            f"LEARNER DESIGN SUBMISSION:\n"
            f"{submission.design_document.as_text()}\n\n"
            f"REQUIRED JSON FORMAT:\n"
            f"[\n"
            f"  {{\n"
            f'    "criterion": "Requirement Coverage",\n'
            f'    "score": 4,\n'
            f'    "evidence": "exact quote from learner design",\n'
            f'    "concern": "constructive concern",\n'
            f'    "suggestion": "actionable suggestion",\n'
            f'    "confidence": "high"\n'
            f"  }},\n"
            f"  ...\n"
            f"]"
        )

    def _parse_response(self, raw_text: str, rubric: Rubric) -> list[CriterionResult]:
        cleaned = raw_text.strip()
        # Strip markdown fences if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMEvaluationError(
                f"LLM returned invalid JSON: {exc}. Raw text: {raw_text[:120]}"
            ) from exc

        # Handle case where LLM wraps array in a dictionary object
        if isinstance(data, dict):
            for key in ["criteria", "results", "evaluations", "feedback"]:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break

        if not isinstance(data, list):
            raise LLMEvaluationError(
                f"Expected JSON list of criterion objects, got {type(data).__name__}"
            )

        parsed_by_name: dict[str, dict] = {}
        for item in data:
            if isinstance(item, dict) and "criterion" in item:
                parsed_by_name[item["criterion"].strip().lower()] = item

        expected_names = [c.name for c in rubric.criteria]
        results: list[CriterionResult] = []

        # Validate that all criteria are present
        missing = [
            name for name in expected_names
            if name.lower() not in parsed_by_name
        ]
        if missing:
            raise LLMEvaluationError(
                f"LLM response omitted required rubric criteria: {missing}"
            )

        for crit in rubric.criteria:
            item = parsed_by_name[crit.name.lower()]
            try:
                score = int(item.get("score", 0))
            except (ValueError, TypeError):
                score = 0
            score = max(0, min(5, score))

            conf = str(item.get("confidence", "medium")).lower()
            if conf not in {"low", "medium", "high"}:
                conf = "medium"

            results.append(
                CriterionResult(
                    criterion=crit.name,
                    score=score,
                    evidence=str(item.get("evidence", "No explicit evidence found in submission")),
                    concern=str(item.get("concern", "")),
                    suggestion=str(item.get("suggestion", "")),
                    confidence=conf,
                    source="ai",
                )
            )

        return results
