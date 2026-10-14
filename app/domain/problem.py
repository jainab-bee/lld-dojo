from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    difficulty: str
    summary: str
    requirements: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    common_pitfalls: list[str] = field(default_factory=list)
    change_request: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Problem":
        return cls(
            id=data["id"],
            title=data["title"],
            difficulty=data.get("difficulty", "Medium"),
            summary=data.get("summary", ""),
            requirements=list(data.get("requirements", [])),
            edge_cases=list(data.get("edge_cases", [])),
            common_pitfalls=list(data.get("common_pitfalls", [])),
            change_request=data.get("change_request", ""),
        )

    @classmethod
    def load_all_from_file(cls, filepath: Path | str) -> list["Problem"]:
        path = Path(filepath)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [cls.from_dict(item) for item in data]
