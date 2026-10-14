import re
from app.domain.evaluation import CriterionResult
from app.domain.problem import Problem
from app.domain.rubric import Rubric
from app.domain.submission import Submission
from app.evaluators.base import Evaluator


class RuleBasedEvaluator(Evaluator):
    """Deterministic evaluator running rule checks without an LLM.
    
    Verifies section completeness, presence of class definitions,
    explicit relationships, tradeoff discussions, and problem keywords.
    """

    RELATIONSHIP_KEYWORDS = [
        "has-a", "is-a", "inherits", "implements", "extends",
        "composed of", "composition", "aggregation", "associates",
        "references", "contains", "aggregates", "depends on",
        "1 to many", "one-to-many", "many-to-many", "->", "dependency"
    ]

    TRADEOFF_KEYWORDS = [
        "tradeoff", "trade-off", "tradeoffs", "pros", "cons",
        "instead of", "alternative", "chose", "chosen", "versus", "vs",
        "better than", "sacrifice", "overhead", "simplicity"
    ]

    def evaluate(
        self,
        submission: Submission,
        rubric: Rubric,
        problem: Problem | None = None,
    ) -> list[CriterionResult]:
        doc = submission.design_document
        results: list[CriterionResult] = []

        # 1. Requirement Coverage check
        results.append(self._check_requirement_coverage(doc, problem))

        # 2. Class Responsibilities check
        results.append(self._check_class_responsibilities(doc))

        # 3. Coupling and Cohesion check
        results.append(self._check_relationships(doc))

        # 4. Extensibility check
        results.append(self._check_extensibility(doc, problem))

        # 5. Edge Cases & Testability check
        results.append(self._check_edge_cases(doc, problem))

        return results

    def _check_requirement_coverage(
        self, doc, problem: Problem | None
    ) -> CriterionResult:
        full_text = doc.as_text().lower()

        if not doc.key_flow.strip():
            return CriterionResult(
                criterion="Requirement Coverage",
                score=1,
                evidence="Key flow section is completely empty.",
                concern="No execution flow described to verify functional requirements.",
                suggestion="Document the step-by-step sequence of operations for the main user flow.",
                confidence="high",
                source="rule",
            )

        if problem and problem.requirements:
            # Extract distinctive keywords from requirements
            stopwords = {
                "the", "and", "for", "with", "based", "upon", "per", "type",
                "types", "allow", "system", "support", "when", "that", "only"
            }
            req_words = set()
            for r in problem.requirements:
                words = re.findall(r"[a-zA-Z]{4,}", r.lower())
                req_words.update(w for w in words if w not in stopwords)

            matched = [w for w in req_words if w in full_text]
            ratio = len(matched) / max(len(req_words), 1)

            if ratio < 0.2:
                return CriterionResult(
                    criterion="Requirement Coverage",
                    score=1,
                    evidence=f"Matched only {len(matched)} requirement keywords out of {len(req_words)} expected terms.",
                    concern="Submission barely mentions the problem requirements.",
                    suggestion="Review the problem requirements list and explicitly address each capability in your classes and flow.",
                    confidence="high",
                    source="rule",
                )
            elif ratio < 0.5:
                return CriterionResult(
                    criterion="Requirement Coverage",
                    score=2,
                    evidence=f"Matched terms: {', '.join(matched[:5])}",
                    concern="Several requirement keywords appear to be omitted from the design.",
                    suggestion="Verify that all core functional requirements have corresponding classes or methods.",
                    confidence="medium",
                    source="rule",
                )

        sample = doc.key_flow.strip()[:60]
        return CriterionResult(
            criterion="Requirement Coverage",
            score=3,
            evidence=f'Key flow mentions: "{sample}..."',
            concern="",
            suggestion="Verify that secondary requirements and state transitions are also satisfied.",
            confidence="medium",
            source="rule",
        )

    def _check_class_responsibilities(self, doc) -> CriterionResult:
        classes_text = doc.classes_and_responsibilities.strip()
        if not classes_text:
            return CriterionResult(
                criterion="Class Responsibilities",
                score=0,
                evidence="Classes and responsibilities section is empty.",
                concern="No classes defined in submission.",
                suggestion="Identify the key domain entities and document each class with its responsibilities.",
                confidence="high",
                source="rule",
            )

        # Look for explicit PascalCase identifiers or 'class X' tokens
        pascal_candidates = set(re.findall(r"\b[A-Z][a-zA-Z0-9_]{2,}\b", classes_text))
        # Filter common non-class words
        filtered = [
            w for w in pascal_candidates
            if w not in {"The", "This", "Each", "All", "When", "User", "With", "Classes", "Section"}
        ]

        if not filtered:
            return CriterionResult(
                criterion="Class Responsibilities",
                score=1,
                evidence="No clear PascalCase class names detected in classes section.",
                concern="Missing explicit class definitions.",
                suggestion="Use clear class names (e.g. ParkingLot, ParkingSpot, Ticket) and list distinct responsibilities for each.",
                confidence="high",
                source="rule",
            )

        if len(filtered) < 2:
            return CriterionResult(
                criterion="Class Responsibilities",
                score=2,
                evidence=f"Only one candidate class found: {filtered[0]}",
                concern="Single class risks becoming a God object handling too many concerns.",
                suggestion="Decompose behavior into smaller classes with single responsibilities.",
                confidence="medium",
                source="rule",
            )

        return CriterionResult(
            criterion="Class Responsibilities",
            score=3,
            evidence=f"Identified candidate classes: {', '.join(filtered[:4])}",
            concern="",
            suggestion="Ensure methods inside each class directly pertain to that class's sole responsibility.",
            confidence="medium",
            source="rule",
        )

    def _check_relationships(self, doc) -> CriterionResult:
        rel_text = doc.relationships.strip()
        if not rel_text:
            return CriterionResult(
                criterion="Coupling and Cohesion",
                score=0,
                evidence="Relationships section is completely empty.",
                concern="No class relationships specified.",
                suggestion="Define how classes interact, using composition (has-a) and inheritance (is-a).",
                confidence="high",
                source="rule",
            )

        rel_lower = rel_text.lower()
        matched = [kw for kw in self.RELATIONSHIP_KEYWORDS if kw in rel_lower]

        if not matched:
            return CriterionResult(
                criterion="Coupling and Cohesion",
                score=1,
                evidence=f'Relationships section text: "{rel_text[:50]}..."',
                concern="No structural relationship keywords (composition, inheritance, has-a, implements) found.",
                suggestion="Explicitly state relationships such as 'ParkingLot has-a list of ParkingFloors' or 'Car inherits from Vehicle'.",
                confidence="high",
                source="rule",
            )

        return CriterionResult(
            criterion="Coupling and Cohesion",
            score=3,
            evidence=f"Found relationship patterns: {', '.join(matched[:3])}",
            concern="",
            suggestion="Ensure coupling remains loose by introducing interfaces where implementations may vary.",
            confidence="medium",
            source="rule",
        )

    def _check_extensibility(self, doc, problem: Problem | None) -> CriterionResult:
        tradeoffs_text = doc.tradeoffs.strip()
        if not tradeoffs_text:
            return CriterionResult(
                criterion="Extensibility",
                score=0,
                evidence="Tradeoffs section is completely empty.",
                concern="No tradeoffs or extensibility rationale provided.",
                suggestion="Document why you chose this design and how it accommodates future requirement shifts.",
                confidence="high",
                source="rule",
            )

        tradeoffs_lower = tradeoffs_text.lower()
        matched_tradeoffs = [kw for kw in self.TRADEOFF_KEYWORDS if kw in tradeoffs_lower]

        if not matched_tradeoffs and len(tradeoffs_text) < 40:
            return CriterionResult(
                criterion="Extensibility",
                score=1,
                evidence=f'Tradeoffs text: "{tradeoffs_text[:40]}"',
                concern="Tradeoffs section is too brief and does not analyze alternatives.",
                suggestion="Discuss alternative design choices, such as Strategy pattern vs polymorphism, and explain why your choice scales better.",
                confidence="high",
                source="rule",
            )

        sample = tradeoffs_text[:60]
        return CriterionResult(
            criterion="Extensibility",
            score=3,
            evidence=f'Tradeoffs statement: "{sample}..."',
            concern="",
            suggestion="Consider how the design responds if the change request twist is introduced.",
            confidence="medium",
            source="rule",
        )

    def _check_edge_cases(self, doc, problem: Problem | None) -> CriterionResult:
        assumptions_text = doc.assumptions.strip()
        if not assumptions_text:
            return CriterionResult(
                criterion="Edge Cases and Testability",
                score=0,
                evidence="Assumptions section is empty.",
                concern="No assumptions or boundary handling documented.",
                suggestion="Document system assumptions, capacity limits, and edge conditions.",
                confidence="high",
                source="rule",
            )

        full_text = doc.as_text().lower()
        edge_words = ["null", "empty", "full", "timeout", "error", "exception", "concurrent", "limit", "invalid", "fail"]
        matched_edge = [w for w in edge_words if w in full_text]

        if not matched_edge:
            return CriterionResult(
                criterion="Edge Cases and Testability",
                score=2,
                evidence="No standard edge case terms (error, full, empty, concurrent, invalid) found across design.",
                concern="Boundary conditions and failure recovery appear unaddressed.",
                suggestion="Detail how the system behaves when capacities are reached or invalid inputs are provided.",
                confidence="medium",
                source="rule",
            )

        return CriterionResult(
            criterion="Edge Cases and Testability",
            score=3,
            evidence=f"Edge case considerations detected: {', '.join(matched_edge[:4])}",
            concern="",
            suggestion="Ensure methods return clear error states or exceptions to facilitate unit testing.",
            confidence="medium",
            source="rule",
        )
