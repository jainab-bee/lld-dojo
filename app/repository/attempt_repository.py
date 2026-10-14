import json
import sqlite3
from pathlib import Path

from app.domain.attempt import Attempt
from app.domain.design_document import DesignDocument
from app.domain.evaluation import CriterionResult, Evaluation
from app.domain.submission import Submission, SubmissionStatus


class AttemptRepository:
    """Encapsulates all SQLite persistence logic for attempts, submissions, and evaluations."""

    def __init__(self, db_path: str | Path = "lld_dojo.db"):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY,
                    problem_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY,
                    attempt_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    assumptions TEXT NOT NULL,
                    classes_and_responsibilities TEXT NOT NULL,
                    relationships TEXT NOT NULL,
                    key_flow TEXT NOT NULL,
                    tradeoffs TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    submission_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_attempts_problem ON attempts(problem_id);
                CREATE INDEX IF NOT EXISTS idx_submissions_attempt ON submissions(attempt_id);
                CREATE INDEX IF NOT EXISTS idx_submissions_idempotency ON submissions(idempotency_key);
                """
            )

    # ------------------ Attempt Methods ------------------

    def save_attempt(self, attempt: Attempt) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO attempts (id, problem_id, attempt_number, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (attempt.id, attempt.problem_id, attempt.attempt_number, attempt.created_at),
            )

    def get_attempt(self, attempt_id: str) -> Attempt | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Attempt(
                id=row["id"],
                problem_id=row["problem_id"],
                attempt_number=row["attempt_number"],
                created_at=row["created_at"],
            )

    def get_attempts_by_problem(self, problem_id: str) -> list[Attempt]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM attempts WHERE problem_id = ? ORDER BY attempt_number ASC",
                (problem_id,),
            )
            return [
                Attempt(
                    id=row["id"],
                    problem_id=row["problem_id"],
                    attempt_number=row["attempt_number"],
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    def get_all_attempts(self) -> list[Attempt]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM attempts ORDER BY created_at DESC")
            return [
                Attempt(
                    id=row["id"],
                    problem_id=row["problem_id"],
                    attempt_number=row["attempt_number"],
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    def get_next_attempt_number(self, problem_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(attempt_number) AS max_num FROM attempts WHERE problem_id = ?",
                (problem_id,),
            )
            row = cursor.fetchone()
            max_num = row["max_num"] if row and row["max_num"] is not None else 0
            return max_num + 1

    # ------------------ Submission Methods ------------------

    def save_submission(self, submission: Submission) -> None:
        doc = submission.design_document
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO submissions (
                    id, attempt_id, idempotency_key, status, error_message,
                    assumptions, classes_and_responsibilities, relationships, key_flow, tradeoffs,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission.id,
                    submission.attempt_id,
                    submission.idempotency_key,
                    submission.status.value,
                    submission.error_message,
                    doc.assumptions,
                    doc.classes_and_responsibilities,
                    doc.relationships,
                    doc.key_flow,
                    doc.tradeoffs,
                    submission.created_at,
                ),
            )

    def update_submission(self, submission: Submission) -> None:
        doc = submission.design_document
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE submissions SET
                    status = ?,
                    error_message = ?,
                    assumptions = ?,
                    classes_and_responsibilities = ?,
                    relationships = ?,
                    key_flow = ?,
                    tradeoffs = ?
                WHERE id = ?
                """,
                (
                    submission.status.value,
                    submission.error_message,
                    doc.assumptions,
                    doc.classes_and_responsibilities,
                    doc.relationships,
                    doc.key_flow,
                    doc.tradeoffs,
                    submission.id,
                ),
            )

    def get_submission(self, submission_id: str) -> Submission | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_submission(row)

    def get_submission_by_idempotency_key(self, key: str) -> Submission | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM submissions WHERE idempotency_key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_submission(row)

    def get_submissions_by_attempt(self, attempt_id: str) -> list[Submission]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM submissions WHERE attempt_id = ? ORDER BY created_at ASC",
                (attempt_id,),
            )
            return [self._row_to_submission(r) for r in cursor.fetchall()]

    def get_latest_submission_for_attempt(self, attempt_id: str) -> Submission | None:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM submissions WHERE attempt_id = ? ORDER BY created_at DESC LIMIT 1",
                (attempt_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_submission(row)

    def _row_to_submission(self, row: sqlite3.Row) -> Submission:
        doc = DesignDocument(
            assumptions=row["assumptions"],
            classes_and_responsibilities=row["classes_and_responsibilities"],
            relationships=row["relationships"],
            key_flow=row["key_flow"],
            tradeoffs=row["tradeoffs"],
        )
        return Submission(
            id=row["id"],
            attempt_id=row["attempt_id"],
            design_document=doc,
            idempotency_key=row["idempotency_key"],
            status=SubmissionStatus(row["status"]),
            error_message=row["error_message"],
            created_at=row["created_at"],
        )

    # ------------------ Evaluation Methods ------------------

    def save_evaluation(self, evaluation: Evaluation) -> None:
        results_data = [r.to_dict() for r in evaluation.results]
        results_json = json.dumps(results_data)
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluations (submission_id, summary, results_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (evaluation.submission_id, evaluation.summary, results_json, now_str),
            )

    def get_evaluation(self, submission_id: str) -> Evaluation | None:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM evaluations WHERE submission_id = ?", (submission_id,))
            row = cursor.fetchone()
            if not row:
                return None
            results_data = json.loads(row["results_json"])
            results = [CriterionResult.from_dict(item) for item in results_data]
            return Evaluation(
                submission_id=row["submission_id"],
                results=results,
                summary=row["summary"],
            )
