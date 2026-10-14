from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.domain.design_document import DesignDocument
from app.domain.rubric import Rubric
from app.domain.submission import SubmissionStatus
from app.evaluators.llm_evaluator import LLMEvaluator
from app.evaluators.rule_based import RuleBasedEvaluator
from app.llm.client import create_default_llm_client
from app.repository.attempt_repository import AttemptRepository
from app.services.comparison_service import ComparisonService
from app.services.evaluation_service import EvaluationService
from app.services.practice_service import PracticeService

BASE_DIR = Path(__file__).resolve().parent

# Initialize repository and services
repository = AttemptRepository(db_path=BASE_DIR.parent / "lld_dojo.db")
practice_service = PracticeService(repository, problems_path=BASE_DIR / "data" / "problems.json")

# LLM and evaluation setup
llm_client = create_default_llm_client()
evaluators = [
    RuleBasedEvaluator(),
    LLMEvaluator(client=llm_client),
]
problems_map = {p.id: p for p in practice_service.get_problems()}
rubric = Rubric.standard_lld_rubric()
evaluation_service = EvaluationService(
    repository=repository,
    evaluators=evaluators,
    rubric=rubric,
    problems=problems_map,
)
comparison_service = ComparisonService()

app = FastAPI(title="LLD Dojo", description="Low-Level Design Practice Platform")

# Static files and templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def list_problems(request: Request):
    """Problem list view."""
    problems = practice_service.get_problems()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"problems": problems},
    )


@app.get("/problems/{problem_id}", response_class=HTMLResponse)
def problem_detail(
    request: Request,
    problem_id: str,
    from_submission: str | None = None,
):
    """Problem spec and structured design submission form."""
    problem = practice_service.get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    prefill_doc = None
    if from_submission:
        sub = repository.get_submission(from_submission)
        if sub:
            prefill_doc = sub.design_document

    idempotency_key = str(uuid.uuid4())
    return templates.TemplateResponse(
        request=request,
        name="problem_detail.html",
        context={
            "problem": problem,
            "doc": prefill_doc,
            "idempotency_key": idempotency_key,
            "error": None,
        },
    )


@app.post("/problems/{problem_id}/submit", response_class=HTMLResponse)
def submit_design(
    request: Request,
    problem_id: str,
    background_tasks: BackgroundTasks,
    assumptions: str = Form(""),
    classes_and_responsibilities: str = Form(""),
    relationships: str = Form(""),
    key_flow: str = Form(""),
    tradeoffs: str = Form(""),
    idempotency_key: str = Form(...),
):
    """Handles structured design submission and initiates background evaluation."""
    problem = practice_service.get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    doc = DesignDocument(
        assumptions=assumptions,
        classes_and_responsibilities=classes_and_responsibilities,
        relationships=relationships,
        key_flow=key_flow,
        tradeoffs=tradeoffs,
    )

    # Validate design document
    try:
        doc.validate()
    except ValueError as validation_err:
        return templates.TemplateResponse(
            request=request,
            name="problem_detail.html",
            context={
                "problem": problem,
                "doc": doc,
                "idempotency_key": idempotency_key or str(uuid.uuid4()),
                "error": str(validation_err),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Check for existing submission with the same idempotency key
    existing_sub = repository.get_submission_by_idempotency_key(idempotency_key)
    if existing_sub:
        return RedirectResponse(
            url=f"/submissions/{existing_sub.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Create new attempt and submission
    attempt = practice_service.create_attempt(problem_id)
    submission, is_new = evaluation_service.submit_design(
        attempt_id=attempt.id,
        design_document=doc,
        idempotency_key=idempotency_key,
    )

    if is_new:
        # Schedule evaluation in background task
        background_tasks.add_task(evaluation_service.process_evaluation, submission.id)

    return RedirectResponse(
        url=f"/submissions/{submission.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/submissions/{submission_id}", response_class=HTMLResponse)
def view_submission(request: Request, submission_id: str):
    """Status and feedback page for a submission."""
    submission = repository.get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    attempt = repository.get_attempt(submission.attempt_id)
    problem = practice_service.get_problem(attempt.problem_id) if attempt else None
    evaluation = repository.get_evaluation(submission.id)

    return templates.TemplateResponse(
        request=request,
        name="submission_status.html",
        context={
            "submission": submission,
            "attempt": attempt,
            "problem": problem,
            "evaluation": evaluation,
        },
    )


@app.post("/submissions/{submission_id}/retry", response_class=HTMLResponse)
def retry_submission(
    request: Request,
    submission_id: str,
    background_tasks: BackgroundTasks,
):
    """Retries a failed evaluation."""
    submission = repository.get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status == SubmissionStatus.FAILED:
        submission.transition_to(SubmissionStatus.EVALUATING)
        repository.update_submission(submission)
        background_tasks.add_task(evaluation_service.process_evaluation, submission.id)

    return RedirectResponse(
        url=f"/submissions/{submission.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/history", response_class=HTMLResponse)
def view_history(request: Request):
    """View all past attempts grouped by problem."""
    grouped = practice_service.get_grouped_history()
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"grouped_history": grouped},
    )


@app.get("/compare", response_class=HTMLResponse)
def compare_attempts(request: Request, a: str, b: str):
    """Compares two attempts of the same problem."""
    attempt_a = repository.get_attempt(a)
    attempt_b = repository.get_attempt(b)

    if not attempt_a or not attempt_b:
        raise HTTPException(status_code=404, detail="One or both attempts not found")

    if attempt_a.problem_id != attempt_b.problem_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot compare attempts from two different problems",
        )

    # Ensure chronological order (attempt_a is earlier or equal to attempt_b)
    if attempt_a.attempt_number > attempt_b.attempt_number:
        attempt_a, attempt_b = attempt_b, attempt_a

    sub_a = repository.get_latest_submission_for_attempt(attempt_a.id)
    sub_b = repository.get_latest_submission_for_attempt(attempt_b.id)

    if not sub_a or not sub_b:
        raise HTTPException(
            status_code=400,
            detail="Both attempts must have at least one submission to compare",
        )

    eval_a = repository.get_evaluation(sub_a.id)
    eval_b = repository.get_evaluation(sub_b.id)

    if not eval_a or not eval_b:
        raise HTTPException(
            status_code=400,
            detail="Both attempts must be evaluated before comparing",
        )

    problem = practice_service.get_problem(attempt_a.problem_id)
    comparison = comparison_service.compare(attempt_a, eval_a, attempt_b, eval_b)

    return templates.TemplateResponse(
        request=request,
        name="compare.html",
        context={
            "problem": problem,
            "comparison": comparison,
            "sub_b_id": sub_b.id,
        },
    )
