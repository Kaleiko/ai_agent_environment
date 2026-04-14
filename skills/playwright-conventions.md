---
name: playwright-conventions
description: "Mandatory conventions for Playwright end-to-end tests in Python"
globs: ["**/*.py"]
---

**These are MANDATORY conventions. ALL Playwright E2E test code MUST follow these rules without exception.**

# Playwright E2E Test Conventions

## 1. Project Structure

The E2E test repo MUST follow this structure:

```
e2e-tests/                     # Repository root
  conftest.py                  # Root fixtures (browser, base URLs, auth)
  pyproject.toml               # Pytest config and dependencies
  .env.example                 # Environment variable template
  pages/                       # Page objects
    __init__.py
    base_page.py               # Base page object class
    login_page.py
    dashboard_page.py
    ...
  fixtures/                    # Shared fixtures (test data, helpers)
    __init__.py
    auth.py                    # Authentication fixtures
    test_data.py               # Test data factories
    ...
  tests/                       # Test files
    conftest.py                # Test-level fixtures
    test_auth_flow.py          # Tests organized by user flow
    test_billing_flow.py
    test_onboarding_flow.py
    ...
  traces/                      # Playwright trace files (gitignored)
```

## 2. Test Organization

- Tests MUST be organized by **user flow or feature**, NOT by microservice or page
- A test file represents a complete user journey (e.g., `test_billing_flow.py` covers creating an invoice through payment)
- Test file names MUST use the pattern `test_{flow_name}.py`
- Test function names MUST use the pattern `test_{action}_{expected_outcome}` (e.g., `test_submit_invoice_creates_payment_record`)
- NEVER organize tests by backend service (e.g., no `test_auth_service.py` or `test_billing_api.py`)
- A single test MAY span multiple microservices — tests reflect user journeys, not architecture

## 3. Page Objects

All page interactions MUST go through page objects. NEVER use raw selectors in test functions.

### Base Page

```python
from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate(self, path: str = "") -> None:
        self.page.goto(path)
```

### Page Object Rules

- Each page or significant component MUST have its own page object class
- Page objects MUST encapsulate selectors — tests NEVER reference selectors directly
- Page object methods MUST represent **user actions** (e.g., `login()`, `submit_form()`, `select_plan()`), NOT low-level interactions (e.g., `click_button()`, `fill_input()`)
- Page objects MUST use `data-testid` attributes as the primary selector strategy
- Fallback selector priority: `data-testid` > `role` > `text` > CSS — NEVER use XPath
- Page objects MUST return `self` or another page object for method chaining where natural

### Example Page Object

```python
from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self._email = page.locator("[data-testid='email-input']")
        self._password = page.locator("[data-testid='password-input']")
        self._submit = page.locator("[data-testid='login-submit']")
        self._error = page.locator("[data-testid='login-error']")

    def navigate(self) -> "LoginPage":
        self.page.goto("/login")
        return self

    def login(self, email: str, password: str) -> "DashboardPage":
        self._email.fill(email)
        self._password.fill(password)
        self._submit.click()
        self.page.wait_for_url("**/dashboard**")
        from pages.dashboard_page import DashboardPage

        return DashboardPage(self.page)

    def login_expecting_error(self, email: str, password: str) -> "LoginPage":
        self._email.fill(email)
        self._password.fill(password)
        self._submit.click()
        self._error.wait_for(state="visible")
        return self

    @property
    def error_message(self) -> str:
        return self._error.text_content() or ""
```

## 4. Fixtures

### Root conftest.py

```python
import os

import pytest
from playwright.sync_api import Page


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL of the application under test."""
    return os.environ.get("E2E_BASE_URL", "http://localhost:3000")


@pytest.fixture
def page(page: Page, base_url: str) -> Page:
    """Override default page fixture with base URL."""
    page.goto(base_url)
    return page
```

### Fixture Rules

- Authentication state MUST be managed via fixtures, NOT repeated login steps in each test
- Use `storage_state` for authenticated sessions to avoid logging in before every test
- Test data MUST be created via fixtures or factory functions, NEVER hardcoded in tests
- Fixtures that create data MUST clean up after themselves (use `yield` with teardown)
- Scope fixtures appropriately: `session` for expensive setup, `function` for test isolation
- NEVER share mutable state between tests — each test MUST be independently runnable

## 5. Configuration

### Environment Variables

- `E2E_BASE_URL` — Frontend URL (default: `http://localhost:3000`)
- `E2E_API_URL` — Direct API URL for setup/assertions (default: `http://localhost:8000`)
- `E2E_HEADED` — Run in headed mode for debugging (`true`/`false`)
- `E2E_SLOW_MO` — Slow down actions by N milliseconds

ALL configuration MUST be via environment variables. NEVER hardcode URLs, credentials, or environment-specific values.

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "smoke: Quick sanity checks",
    "critical: Business-critical flows",
    "slow: Tests that take >30s",
]
```

## 6. Assertions

- Assert on **user-visible outcomes**, NOT implementation details
- Use `expect()` from Playwright for automatic waiting and retry:
  ```python
  from playwright.sync_api import expect

  expect(page.locator("[data-testid='success-message']")).to_be_visible()
  expect(page.locator("[data-testid='item-count']")).to_have_text("5")
  ```
- NEVER use `time.sleep()` — use Playwright's built-in waiting (`wait_for_selector`, `wait_for_url`, `expect` with timeout)
- For API state assertions, use direct API calls via `requests` or Playwright's `request` context — do NOT scrape the UI for backend state

## 7. Trace & Debugging

### Trace Configuration

Traces MUST be configured for CI failure debugging:

```python
from collections.abc import Generator

import pytest
from playwright.sync_api import Page


@pytest.fixture(autouse=True)
def trace_on_failure(page: Page, request: pytest.FixtureRequest) -> Generator:
    page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield
    if request.node.rep_call and request.node.rep_call.failed:
        trace_path = f"traces/{request.node.name}.zip"
        page.context.tracing.stop(path=trace_path)
    else:
        page.context.tracing.stop()
```

- Traces MUST be saved as CI artifacts on failure
- `traces/` directory MUST be gitignored
- Screenshots on failure are optional but recommended

## 8. Test Markers & Running

- Use `@pytest.mark.smoke` for quick sanity checks (< 10 tests, < 2 min total)
- Use `@pytest.mark.critical` for business-critical flows
- Use `@pytest.mark.slow` for tests over 30 seconds
- Default test run (no markers) MUST complete in under 10 minutes
- Tests MUST be parallelizable — use `pytest-xdist` with `-n auto` for CI

## 9. Naming Conventions

| Item | Pattern | Example |
|------|---------|---------|
| Test file | `test_{flow_name}.py` | `test_checkout_flow.py` |
| Test function | `test_{action}_{expected_outcome}` | `test_apply_coupon_reduces_total` |
| Page object file | `{page_name}_page.py` | `checkout_page.py` |
| Page object class | `{PageName}Page` | `CheckoutPage` |
| Fixture file | `{concern}.py` | `auth.py`, `test_data.py` |
| Fixture function | descriptive, no `test_` prefix | `authenticated_page`, `sample_invoice` |

## 10. What Tests MUST NOT Do

- NEVER import or call application source code directly — tests interact only through browser and public APIs
- NEVER access the database directly — use API endpoints for setup/verification
- NEVER depend on test execution order
- NEVER share state between test functions
- NEVER use `time.sleep()` — use Playwright waits
- NEVER hardcode URLs, credentials, or test data
- NEVER write tests that pass only in a specific environment

## 11. Test Coverage Requirements

- When planning tests for a page or flow, MUST identify all user-interactable components (buttons, forms, links, dropdowns, toggles, modals, etc.)
- Every interactable component MUST have at least one test covering its primary interaction
- Coverage MUST include both happy path (component works as expected) and error states (validation failures, disabled states, error messages)
- If a component triggers a state change (navigation, data mutation, UI update), the test MUST assert the resulting state
- NEVER write tests that only verify page loads or static content — tests MUST exercise user interactions
