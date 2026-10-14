# LLD Dojo

LLD Dojo is a practice platform for low-level system design interviews. I built it as a prototype for a 2-day engineering assignment. 

Most interview preparation platforms give you a reference answer to read or give you a generic AI score out of 100. That does not help me understand whether my design actually works. LLD Dojo focuses on three practical principles:
1. Every piece of feedback quotes evidence from my own written submission.
2. There is no single master solution. The system evaluates the design against problem requirements and a fixed 5-point rubric.
3. When I revise a design, I can compare attempts side by side to see which concerns were resolved and which are still open.

## Tech Stack

I chose a straightforward monolithic stack with no frontend build tools and no external queues:
- Python 3.11+
- FastAPI with server-rendered Jinja2 templates
- Plain CSS in a single stylesheet (no Tailwind, no Node.js)
- SQLite using Python's standard `sqlite3` module
- Google Gemini API via REST with a fallback to `FakeLLMClient`
- Background evaluation via FastAPI `BackgroundTasks`
- pytest for automated testing

## How to Run the App

### 1. Clone and navigate to the project directory
```bash
git clone <your-repo-url>
cd lld-dojo
```

### 2. Set up a virtual environment (optional but recommended)
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables (optional)
Copy `.env.example` to `.env`:
```bash
# On macOS / Linux:
cp .env.example .env
# On Windows:
copy .env.example .env
```
If you have a Google Gemini API key, add it inside `.env`:
```
GEMINI_API_KEY=your_actual_key_here
```
Without an API key, the app uses a fake client that returns canned feedback built from the submission text. It is for running and testing offline, not a real AI review.

### 5. Start the web server
Run uvicorn from the `lld-dojo` directory:
```bash
uvicorn app.main:app --reload --port 8000
```
Open your browser at `http://127.0.0.1:8000`.

## How to Run Tests

Run pytest from the `lld-dojo` directory:
```bash
python -m pytest -v
```
All tests run in less than two seconds using SQLite and the in-memory or fake test doubles.

## Key Decisions

1. Server-rendered HTML instead of React or Vue:
For a 2-day prototype, server-rendered templates let me build a fast, clean user experience without configuring bundlers, npm dependencies, or client-side routers.

2. Fixed rubric instead of a 100-point score:
Numerical scores give a false sense of precision. Instead, I broke evaluation into five clear engineering criteria: Requirement Coverage, Class Responsibilities, Coupling and Cohesion, Extensibility, and Edge Cases and Testability. Each criterion is scored from 0 to 5.

3. Rule-based evaluation alongside LLM evaluation:
LLMs can hallucinate or fail due to network timeouts. By running deterministic rule checks first, the system immediately catches empty sections, missing classes, and unmentioned relationships. If the LLM call fails, the rule checks are preserved and displayed to the user.

4. DesignDocument encapsulation:
The `DesignDocument` class is the only part of the domain that knows the text section format. If I want to add class diagrams or JSON inputs in the future, I can update this class without changing the database schema or the evaluators.

## Trade-offs

See DESIGN.md for trade-offs.

## Known Limitations

- Monolith background tasks run in the web server process. If the server restarts during an evaluation, that in-flight task is interrupted.
- Concern comparison uses text similarity and rubric matching. It handles typical revisions well, but a deep semantic diff will require embeddings or a secondary model comparison in the future.
- The platform currently includes three curated problems (Parking Lot, Vending Machine, Elevator System). An admin portal for adding new problems is not yet built.
- I tested the app only with the fake LLM client. The Gemini client is written against the same LLMClient interface, but I did not run it against the live API.
