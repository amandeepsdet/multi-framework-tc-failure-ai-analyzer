# AI Failure Analysis — checkout::test_pay

- **Category:** Backend
- **Confidence:** 92%
- **Severity:** Critical
- **Owner:** Backend / Platform team
- **Source:** heuristic

## Root cause
A backend service returned HTTP 500; the client could not obtain valid data.

Inspect server logs for the failing endpoint; the defect is server-side, not in the test.

_Confidence rationale: Rule-based classification from 4 evidence signal(s)._

## Evidence
- Assertion: expected 200 but server returned HTTP 500
- Exception: AssertionError
- Network status codes observed: 500
- Console errors: 1 (e.g. Payment request failed)

## Recommendations
- Inspect server logs for the failing endpoint; the defect is server-side, not in the test.

## Reasoning
Deterministic heuristic analysis. Configure an LLM provider for deeper natural-language reasoning.
