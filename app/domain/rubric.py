from dataclasses import dataclass, field


@dataclass(frozen=True)
class Criterion:
    name: str
    description: str
    min_score: int = 0
    max_score: int = 5


@dataclass(frozen=True)
class Rubric:
    criteria: list[Criterion] = field(default_factory=list)

    @classmethod
    def standard_lld_rubric(cls) -> "Rubric":
        return cls(
            criteria=[
                Criterion(
                    name="Requirement Coverage",
                    description="Fulfills the core functional requirements and workflows explicitly described.",
                ),
                Criterion(
                    name="Class Responsibilities",
                    description="Adheres to single responsibility principles, avoiding God objects and bloated entities.",
                ),
                Criterion(
                    name="Coupling and Cohesion",
                    description="Employs loose coupling and high cohesion with appropriate interfaces or abstractions.",
                ),
                Criterion(
                    name="Extensibility",
                    description="Easily accommodates future changes (such as the change request) without modifying core classes.",
                ),
                Criterion(
                    name="Edge Cases and Testability",
                    description="Accounts for boundary conditions and failure states; components can be isolated for unit testing.",
                ),
            ]
        )

    def criterion_names(self) -> list[str]:
        return [c.name for c in self.criteria]
