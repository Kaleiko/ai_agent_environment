# FastAPI Conventions

## 1. End-to-End API Testing (MANDATORY)

Every API endpoint MUST have end-to-end tests that verify the full request/response cycle. This is non-negotiable — no endpoint ships without tests.

### Requirements

- MUST use `httpx.AsyncClient` with `ASGITransport` (or `TestClient` for sync tests) against the actual FastAPI app — no mocking the app itself
- MUST test the real request path: routing → dependencies → handler → response
- MUST cover: success cases, expected error cases (4xx), and input validation
- MUST assert on status codes, response body structure, and key field values
- MUST test with realistic payloads, not empty or trivial data

### Test Structure

- All end-to-end tests MUST be placed in `tests/end-to-end-testing/`
- Mirror the route structure within that directory (e.g., `tests/end-to-end-testing/test_users.py` for `routes/users.py`)
- Each endpoint gets its own test function (or class) — do not bundle unrelated endpoints
- Use fixtures for app client, auth tokens, and test data setup/teardown

### What Counts as End-to-End

- The test sends an HTTP request and receives an HTTP response
- Database operations (if any) execute against a real test database, not mocks
- External service calls MAY be mocked at the boundary, but everything inside the app is real

### Running Tests After Code Changes

- After ANY code change to the FastAPI app, you MUST run the full end-to-end test suite: `pytest tests/end-to-end-testing/`
- This applies to ALL changes — route handlers, models, middleware, dependencies, config, database schemas
- Do NOT selectively run only the tests for the files you changed — run the entire suite to catch regressions
- If any test fails, fix the issue before considering the task complete

### Test Data Cleanup (MANDATORY)

- Tests that create, modify, or delete data MUST clean up after themselves
- Use pytest fixtures with `yield` for setup/teardown — create test data before `yield`, delete it after
- POST tests: delete the created resource in teardown
- PATCH/PUT tests: restore the original state or delete the test resource in teardown
- DELETE tests: create the resource in setup, test the delete, verify it's gone — no teardown needed
- MUST NOT rely on test execution order — each test must be independently runnable
- MUST NOT leave orphaned data that could cause other tests to fail or produce false positives

### What Does NOT Count

- Calling handler functions directly (bypasses middleware, deps, validation)
- Unit testing Pydantic models in isolation (useful but not a substitute)
- Testing with mocked request/response objects
