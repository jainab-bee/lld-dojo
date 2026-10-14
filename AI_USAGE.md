# AI Usage

I used Claude to plan the project and write the build prompt, and Antigravity to generate the code from that prompt. After that I ran the app and read through the main files.

## Decisions

1. Product direction. I asked Claude what to build. It suggested a structured-text design form with five sections and feedback that quotes evidence from my submission. I accepted this because text is the smallest format that still shows design thinking.

2. No reference solution. A reference answer was an obvious option. I decided against it because the brief says many designs can be valid. Each problem has requirements, edge cases and common pitfalls, and the rubric is fixed.

3. Rules plus LLM. I kept deterministic rule checks as a separate evaluator so that a Gemini failure still leaves the learner with some feedback. If the LLM fails, the service saves the rule results and marks the submission FAILED with a retry option.

4. Research claims. An early version of my pitch implied that competing tools lack AI feedback and attempt history. I changed it to a hypothesis, because those tools may already have similar features.

5. A small edit after running the app. I added a new edge case to the Parking Lot problem in problems.json ("Two vehicles arrive at the same time and only one spot is left"), because the original list did not cover concurrent entry. I checked in the browser that it shows on the problem page.

## What I checked myself
I ran the full flow in the browser with the fake LLM client: submit, feedback, revise, history and compare. I did not test with a live Gemini key. I also ran the test suite (20 tests passing) and fixed a pytest import error by adding a pytest.ini with pythonpath set to the project root.
