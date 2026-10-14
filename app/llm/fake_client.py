import json
import re

from app.llm.client import LLMClient


class FakeLLMClient(LLMClient):
    """Canned LLM implementation for local development and deterministic testing."""

    def __init__(
        self,
        should_fail: bool = False,
        return_invalid_json: bool = False,
        missing_criteria: bool = False,
        failure_message: str = "Simulated LLM network timeout or rate limit error.",
    ):
        self.should_fail = should_fail
        self.return_invalid_json = return_invalid_json
        self.missing_criteria = missing_criteria
        self.failure_message = failure_message
        self.call_count = 0

    def complete(self, prompt: str) -> str:
        self.call_count += 1

        if self.should_fail:
            raise RuntimeError(self.failure_message)

        if self.return_invalid_json:
            return "This is not valid JSON at all: {broken, 'syntax': error}"

        # Extract real phrases from the prompt to use as genuine evidence
        classes_match = re.search(r"CLASSES AND RESPONSIBILITIES ===\s*(.+?)(?=\n===|\Z)", prompt, re.DOTALL)
        relationships_match = re.search(r"RELATIONSHIPS ===\s*(.+?)(?=\n===|\Z)", prompt, re.DOTALL)
        tradeoffs_match = re.search(r"TRADEOFFS ===\s*(.+?)(?=\n===|\Z)", prompt, re.DOTALL)
        flow_match = re.search(r"KEY FLOW ===\s*(.+?)(?=\n===|\Z)", prompt, re.DOTALL)
        assumptions_match = re.search(r"ASSUMPTIONS ===\s*(.+?)(?=\n===|\Z)", prompt, re.DOTALL)

        classes_sample = classes_match.group(1).strip()[:80] if classes_match else "class declarations in submission"
        rel_sample = relationships_match.group(1).strip()[:80] if relationships_match else "relationships in submission"
        tradeoffs_sample = tradeoffs_match.group(1).strip()[:80] if tradeoffs_match else "tradeoffs discussion"
        flow_sample = flow_match.group(1).strip()[:80] if flow_match else "main workflow steps"
        assumptions_sample = assumptions_match.group(1).strip()[:80] if assumptions_match else "assumptions provided"

        canned = [
            {
                "criterion": "Requirement Coverage",
                "score": 4,
                "evidence": f'"{flow_sample}"',
                "concern": "Edge requirements like ticket loss or grace periods are not fully traced in the flow.",
                "suggestion": "Add explicit handling for ticket loss and minimum duration calculations.",
                "confidence": "high",
            },
            {
                "criterion": "Class Responsibilities",
                "score": 4,
                "evidence": f'"{classes_sample}"',
                "concern": "Main controller might accumulate secondary responsibilities over time.",
                "suggestion": "Delegate rate calculations and ticket generation to dedicated helper services.",
                "confidence": "high",
            },
            {
                "criterion": "Coupling and Cohesion",
                "score": 4,
                "evidence": f'"{rel_sample}"',
                "concern": "Classes reference concrete types rather than abstract interfaces.",
                "suggestion": "Introduce an interface or protocol for spot allocation to decouple placement strategy.",
                "confidence": "medium",
            },
            {
                "criterion": "Extensibility",
                "score": 3,
                "evidence": f'"{tradeoffs_sample}"',
                "concern": "Handling the change request (e.g. surge pricing or new payment types) requires modifying existing classes.",
                "suggestion": "Use the Strategy or Decorator pattern for pricing and fee calculation to allow dynamic multipliers.",
                "confidence": "medium",
            },
            {
                "criterion": "Edge Cases and Testability",
                "score": 3,
                "evidence": f'"{assumptions_sample}"',
                "concern": "Concurrent slot allocations at multiple gates might race without a synchronization guard.",
                "suggestion": "Introduce optimistic locking or atomic reservation states when marking spots occupied.",
                "confidence": "high",
            },
        ]

        if self.missing_criteria:
            # Drop the last two criteria to test defensive validation
            canned = canned[:3]

        return json.dumps(canned, indent=2)
