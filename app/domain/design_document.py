from dataclasses import dataclass


@dataclass
class DesignDocument:
    assumptions: str
    classes_and_responsibilities: str
    relationships: str
    key_flow: str
    tradeoffs: str

    MIN_SECTION_LEN: int = 15
    MIN_TOTAL_LEN: int = 120

    def validate(self) -> None:
        """Validate that all sections are populated with enough detail to review.
        
        Raises ValueError with a clear, readable message if any check fails.
        """
        sections = {
            "Assumptions": self.assumptions,
            "Classes & Responsibilities": self.classes_and_responsibilities,
            "Relationships": self.relationships,
            "Key Flow": self.key_flow,
            "Tradeoffs": self.tradeoffs,
        }

        for name, content in sections.items():
            cleaned = (content or "").strip()
            if not cleaned:
                raise ValueError(f"'{name}' section is empty. Please provide your design details.")
            if len(cleaned) < self.MIN_SECTION_LEN:
                raise ValueError(
                    f"'{name}' is too brief (at least {self.MIN_SECTION_LEN} characters needed)."
                )

        total_length = sum(len((c or "").strip()) for c in sections.values())
        if total_length < self.MIN_TOTAL_LEN:
            raise ValueError(
                f"Design document is too short overall ({total_length} characters). "
                f"Please provide at least {self.MIN_TOTAL_LEN} characters across all sections."
            )

    def as_text(self) -> str:
        """Returns the document as plain formatted text.
        
        This encapsulates the format so evaluators only depend on text representation.
        """
        return (
            f"=== 1. ASSUMPTIONS ===\n{self.assumptions.strip()}\n\n"
            f"=== 2. CLASSES AND RESPONSIBILITIES ===\n{self.classes_and_responsibilities.strip()}\n\n"
            f"=== 3. RELATIONSHIPS ===\n{self.relationships.strip()}\n\n"
            f"=== 4. KEY FLOW ===\n{self.key_flow.strip()}\n\n"
            f"=== 5. TRADEOFFS ===\n{self.tradeoffs.strip()}"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "assumptions": self.assumptions,
            "classes_and_responsibilities": self.classes_and_responsibilities,
            "relationships": self.relationships,
            "key_flow": self.key_flow,
            "tradeoffs": self.tradeoffs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "DesignDocument":
        return cls(
            assumptions=data.get("assumptions", ""),
            classes_and_responsibilities=data.get("classes_and_responsibilities", ""),
            relationships=data.get("relationships", ""),
            key_flow=data.get("key_flow", ""),
            tradeoffs=data.get("tradeoffs", ""),
        )
