# Competitive Research and Product Direction

I wrote this short research note to document the problem I am solving, review existing tools, and outline my product hypothesis.

## The Learner Problem

Preparing for Low-Level Design (LLD) interviews is frustrating for students. Unlike Data Structures and Algorithms where test cases pass or fail deterministically, object-oriented design is open-ended. 

Learners commonly struggle with:
1. Passive reading without active recall: Most preparation consists of reading blogs or watching YouTube videos that show someone else's solution. When asked to design from scratch in an interview, students can find it hard to start, because they have not practiced structuring requirements into classes themselves.
2. The "single correct answer" trap: Students often memorize one specific design pattern combination and assume any deviation is wrong. In reality, multiple valid designs exist depending on trade-offs.
3. Lack of targeted feedback: Generic AI feedback often tells learners "Your design is 82/100, good job." This does not explain what classes are missing or whether the design can handle requirement changes.

## Existing Tools

Two tools in this space are:

### 1. Educative (Grokking the Low Level Design Interview)
What it offers: structured lessons, OOP principles, design problems, and mock interviews.
From the public course page, the course has structured lessons where each case study walks through requirements, UML diagrams and code, and ends with an AI-powered mock interview. I did not try the mock interview, so I can't say how specific its feedback is on a learner's own design.

### 2. LLDCanvas
I came across LLDCanvas as an LLD practice tool, but I could not find enough public information to review it properly, so I am not making claims about its features or feedback.

## Target Gap and Product Hypothesis

Since at least one of these tools already offers AI-based mock interviews, I am not treating AI feedback itself as my difference.
I am not claiming existing tools lack AI feedback or revision history, because those platforms may already offer similar features or add them over time.

Instead, my focus is on a specific target gap: feedback that quotes evidence from the learner's own design, and a way to compare concerns between two attempts of the same problem.

My product hypothesis is:
If learners receive feedback that directly quotes evidence from their own written design and can track how their concerns evolve across successive attempts, they will improve their design thinking faster than by reading reference solutions.

I built LLD Dojo around three ideas:
1. Evidence-based critique: Every feedback item must cite exact phrases from the learner's submission. If the submission does not mention something, the system says so plainly instead of making things up.
2. Fixed criteria over single scores: Rather than giving a score out of 100, the platform evaluates five engineering criteria: Requirement Coverage, Class Responsibilities, Coupling and Cohesion, Extensibility, and Edge Cases.
3. Tracking progress across revisions: Learners can revise their design and inspect which concerns were resolved, which are still open, and what new issues appeared.

This is a hypothesis to test with real users. I have not tested it with real interview candidates yet.
