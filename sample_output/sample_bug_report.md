# [Backend] checkout::test_pay: A backend service returned HTTP 500; the client could not obtain valid data.

- **Severity:** Critical  |  **Priority:** P1  |  **Owner:** Backend / Platform team
- **Environment:** staging | chromium | Windows 11 | pytest

## Description
A backend service returned HTTP 500; the client could not obtain valid data.

Inspect server logs for the failing endpoint; the defect is server-side, not in the test.

## Steps to reproduce
1. Run test 'checkout::test_pay'.
2. Navigate to /checkout.
3. Observe the reported failure and attached evidence.

**Expected:** The test completes successfully.
**Actual:** expected 200 but server returned HTTP 500

## Evidence
- Assertion: expected 200 but server returned HTTP 500
- Exception: AssertionError
- Network status codes observed: 500
- Console errors: 1 (e.g. Payment request failed)

## Suggested fix
Inspect server logs for the failing endpoint; the defect is server-side, not in the test.
