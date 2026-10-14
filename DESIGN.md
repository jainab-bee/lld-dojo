# System Design Document

This document explains the architecture and domain design of LLD Dojo. I designed the system for a 2-day assignment, focusing on domain clarity, deterministic fallbacks, and extensibility.

## MVP Scope

The prototype covers the complete core practice loop for a learner:
1. Select a problem from the catalog.
2. Read problem requirements, edge cases, common pitfalls, and a change request twist.
3. Write a structured design across five essential areas: assumptions, classes, relationships, key flow, and tradeoffs.
4. Submit the design and monitor evaluation progress.
5. Review criterion-level feedback with exact quotes from the submission.
6. Revise the design in a new attempt and compare improvements side by side.

I left out user authentication, custom problem editors, and graphical canvas diagrams to keep the prototype reliable and easy to understand during an interview.

## User Flow

The learner journey follows a strict state progression:
1. Browse catalog at `/` and open `/problems/{id}`.
2. Fill out the 5-box form. The page generates a unique idempotency key.
3. Click submit. The browser posts to `/problems/{id}/submit`.
4. If validation passes, a new `Attempt` and `Submission` are saved with status `SUBMITTED`.
5. A background task starts the evaluation pipeline and the browser redirects to `/submissions/{id}`.
6. The status page displays `EVALUATING` and refreshes every 3 seconds.
7. Once evaluation finishes, the page shows the 5 rubric criteria, scores from 0 to 5, cited evidence, concerns, and suggestions.
8. If the learner wants to improve, they click "Revise this design", which opens the problem form pre-filled with their previous text.
9. From `/history`, they can select any two attempts of the same problem to view score differences and resolved concerns at `/compare`.

## Core Classes and Responsibilities

- `Problem` (`app/domain/problem.py`):
Represents an engineering problem. Holds requirements, edge cases, common pitfalls, and the change request twist. It deliberately does not contain a reference answer.

- `DesignDocument` (`app/domain/design_document.py`):
Encapsulates the five submission sections. It enforces minimum length rules via `validate()` and formats the content for evaluators via `as_text()`. It is the only class that understands the submission input format.

- `Rubric` and `Criterion` (`app/domain/rubric.py`):
Defines the standard 5 evaluation criteria: Requirement Coverage, Class Responsibilities, Coupling and Cohesion, Extensibility, and Edge Cases and Testability. Each criterion has a score range of 0 to 5.

- `Attempt` (`app/domain/attempt.py`):
Represents one try by a learner on a given problem. Tracks `attempt_number` to maintain a sequential revision timeline.

- `Submission` (`app/domain/submission.py`):
Holds a `DesignDocument`, an idempotency key, and a lifecycle status. It enforces valid status transitions internally.

- `CriterionResult` and `Evaluation` (`app/domain/evaluation.py`):
`CriterionResult` represents feedback for a single criterion, including score, evidence, concern, suggestion, confidence, and source tag ("rule" or "ai"). `Evaluation` aggregates results with a summary text.

- `AttemptRepository` (`app/repository/attempt_repository.py`):
Manages all SQLite persistence. All SQL statements live strictly inside this class.

- `EvaluationService` (`app/services/evaluation_service.py`):
Coordinates submission creation, status updates, evaluator execution, result merging, and error handling.

- `ComparisonService` (`app/services/comparison_service.py`):
Compares two evaluated attempts. It calculates score differences per criterion and classifies concerns into resolved, still open, or new.

## Deterministic vs LLM Split

I separated evaluation into two distinct layers:

1. Deterministic rules (`RuleBasedEvaluator`):
Rule checks run quickly and never fail due to network issues. They inspect the submission for objective problems: empty sections, text that is too short, lack of class declarations, missing relationship terms (like "has-a", "is-a", "implements"), absence of tradeoff discussions, and omitted requirement keywords.

2. Language model review (`LLMEvaluator`):
LLMs evaluate semantic understanding. The model checks whether the proposed design actually satisfies problem requirements, whether responsibilities are clean, and whether the architecture can handle the change request twist. It must cite exact phrases from the learner text as evidence.

Why split them this way?
If the LLM call times out or returns bad JSON, the system still provides useful deterministic feedback to the learner. Furthermore, deterministic rules catch obvious oversights before the learner relies solely on an external model.

## State Machine

The submission lifecycle has four states:
- `SUBMITTED`: Stored in database, waiting for evaluation to begin.
- `EVALUATING`: Background worker or task is executing rule checks and LLM calls.
- `COMPLETED`: All evaluators finished and merged results are saved.
- `FAILED`: An evaluator threw an exception or returned unparseable output.

Allowed transitions:
- `SUBMITTED` -> `EVALUATING`
- `EVALUATING` -> `COMPLETED`
- `EVALUATING` -> `FAILED`
- `FAILED` -> `EVALUATING` (on retry)

Attempting any other transition raises an `InvalidStateTransitionError`. For example, a `COMPLETED` submission cannot be moved back to `EVALUATING` or `FAILED`.

## Change Tests

I tested the design against two future changes.

### Change Test A: New Submission Format (e.g., Mermaid class diagram)
Only `DesignDocument` needs to be updated. Because `DesignDocument` exposes `as_text()` and handles validation internally, evaluators and repositories do not care whether the input comes from 5 text boxes, a Mermaid diagram string, or a JSON payload. Evaluators receive the formatted text directly.

### Change Test B: New Evaluator (e.g., Security or Concurrency checker)
`EvaluationService` accepts a list of `Evaluator` instances in its constructor:
```python
class Evaluator(ABC):
    @abstractmethod
    def evaluate(self, submission, rubric, problem=None):
        pass
```
To add a new checker, create a class implementing `evaluate` and pass it into `EvaluationService`. The service code does not need any modifications. I verified this with an automated test in `tests/test_evaluation_service.py::test_evaluator_swap_plugs_in_without_changing_service_code`.

## Key Trade-offs

1. BackgroundTasks vs a real queue: simple to run and explain, but an in-flight evaluation is lost if the server restarts.
2. Structured text vs diagram or code: text is the smallest format that still shows design thinking, but it gives less evidence about real relationships and behaviour.
3. Fixed rubric vs reference solution: allows different valid designs, but scores depend on how well the rubric and prompt are written.
4. Text similarity for comparing concerns vs semantic comparison: easy to implement and explain, but can miss concerns that are reworded.
5. Fake client vs live Gemini: runs offline and is easy to test, but I have not verified real LLM output quality.
6. SQLite: zero setup, fine for one user, not meant for concurrent writes at scale.

## Failure Handling and Idempotency

- Network failure or model timeout:
If Gemini times out or returns an error status, `EvaluationService` catches the exception. It saves the rule-based results so the learner still sees feedback, transitions the submission to `FAILED`, and records a human-readable error message. The learner can click "Retry Evaluation" on the status page to try again.

- Malformed LLM output:
The prompt instructs the model to return strict JSON. `LLMEvaluator` strips code fences, parses the JSON, and verifies that all 5 criteria are present. If parsing fails, it raises `LLMEvaluationError`, which triggers the same graceful failure handling.

- Duplicate submissions:
Every submission form contains an `idempotency_key`. If a user clicks submit twice or refreshes the POST request, `EvaluationService` finds the existing submission by its key and returns it immediately without triggering a second evaluation.

## Scaling Out: What to Split First

In this prototype, evaluation runs in FastAPI's `BackgroundTasks` within the web server process. If this project grew to handle real production traffic, the first thing I would extract is the evaluation worker.

Right now, long LLM calls tie up web server worker threads. Under high traffic, multiple concurrent submissions could starve incoming HTTP requests. I would replace `BackgroundTasks` with a message queue (such as Redis with Celery or RQ). The web route would push the `submission_id` to the queue and return immediately. Dedicated worker processes would pop tasks, run evaluators, and write results back to the database.
