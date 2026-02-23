---
name: python-conventions
description: "Python conventions: code style, error handling, logging, testing, project structure, code review"
globs: ["**/*.py"]
---

**These are MANDATORY conventions. ALL Python code MUST follow these rules without exception.**

---

# 1. Code Style

## Language & Formatting

- MUST follow PEP8 compliance
- MUST NOT exceed 120 characters per line
- MUST use 4 spaces for indentation, NEVER tabs

## Import Ordering

- ALL import statements MUST be at the top of the file, NEVER inline
- MUST follow this order, separated by blank lines:
    1. Standard library (`os`, `sys`, `logging`, etc.)
    2. Third-party packages (`httpx`, `pydantic`, etc.)
    3. Local/project imports (`from src.common import gen_utils`, etc.)

```python
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src.common.gen_utils import parse_response
from src.models.user import User
```

## Naming Conventions

- MUST use descriptive naming following Python conventions
- NEVER use single-letter variable names outside of comprehensions or loops

## Constants

- MUST use `UPPER_SNAKE_CASE` for all constants
- MUST define module-level constants at the top of the file, after imports
- MUST store project-wide constants in `settings.py`
- NEVER use magic numbers or magic strings — extract them into named constants

```python
# settings.py
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 30
API_BASE_URL = "https://api.example.com/v1"

# NEVER do this:
if retries > 3:  # What does 3 mean?
    pass

# MUST do this:
if retries > MAX_RETRY_ATTEMPTS:
    pass
```

## Function Requirements

- Every function MUST have a comprehensive docstring covering purpose, parameters, and return values
- Every function MUST have type hints for ALL parameters and return values
- NEVER submit a function without both a docstring and type hints

## Code Organization

- MUST refactor repetitive logic or similar code patterns appearing more than twice into reusable functions
- MUST store commonly used utility functions and classes in `src/common/gen_utils.py` for project wide access
- MUST refactor `gen_utils.py` if there are more than 20 functions based on these rules.
    - If several functions are related to a similar subject matter, create a new file as `{subject_name}_utils.py`.
        - Example, a project uses MongoDB, and there are 22 functions in `gen_utils.py` and 19 of the functions relate to MongoDB. Because there are 22 functions, you must refactor `gen_utils.py` by taking 19 of the functions related to MongoDB and placing them in a newly created file called `mongodb_utils.py`

## Type Hints (Python 3.10+)

MUST use built-in generics and union syntax. NEVER import from `typing` for types available as builtins:

```python
# MUST use X | None instead of Optional[X]
def fetch_data(url: str, timeout: int | None = None) -> dict:
    pass

# MUST use built-in list[], dict[] instead of typing.List, typing.Dict
def process_items(item_list: list[dict[str, str]]) -> list[str]:
    pass

# MUST use X | Y instead of Union[X, Y]
def parse_response(data: str | dict) -> dict:
    pass

# MUST use built-in tuple[] instead of typing.Tuple
def get_status(item_id: str) -> tuple[bool, str]:
    return True, "Active"
```

## Docstring Format

Every function MUST have a docstring with these sections:
- Purpose (first line)
- Args (ALL parameters)
- Returns (return value description)
- Raises (if applicable)

NEVER omit the Args or Returns sections.

```python
def process_data(item_id: str, status: dict) -> bool:
    """Process and validate item status data.

    Args:
        item_id: Unique identifier for the item
        status: Dictionary containing item status information

    Returns:
        True if processing was successful, False otherwise

    Raises:
        ValueError: If item_id is empty or status is invalid
    """
    # Function implementation here
```

## Async Conventions

- MUST use `async/await` when performing I/O-bound operations (HTTP requests, database queries, file I/O)
- NEVER call blocking functions (e.g., `time.sleep`, `requests.get`) inside async code — use async equivalents (`asyncio.sleep`, `httpx.AsyncClient`)
- MUST prefix async functions with verbs that imply I/O (e.g., `fetch_`, `send_`, `load_`) to distinguish from sync helpers
- MUST use `asyncio.gather()` for concurrent independent tasks, NEVER sequential `await` when tasks are independent
- MUST use `async with` for async context managers (e.g., `httpx.AsyncClient`, `aiofiles.open`)

```python
import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

async def fetch_all_items(item_ids: list[str]) -> list[dict]:
    """Fetch multiple items concurrently.

    Args:
        item_ids: List of item IDs to fetch

    Returns:
        List of item data dictionaries
    """
    async with httpx.AsyncClient() as client:
        tasks = [fetch_item(client, item_id) for item_id in item_ids]
        return await asyncio.gather(*tasks)

async def fetch_item(client: httpx.AsyncClient, item_id: str) -> dict:
    """Fetch a single item from the API.

    Args:
        client: The HTTP client instance
        item_id: The item ID to fetch

    Returns:
        Item data dictionary
    """
    response = await client.get(f"/items/{item_id}")
    response.raise_for_status()
    return response.json()
```

---

# 2. Error Handling

## Custom Exceptions

- MUST create custom exception classes for domain-specific errors
- MUST store all custom exceptions in `src/common/exceptions.py`
- MUST name exceptions with the `Error` suffix (e.g., `ValidationError`, `ItemNotFoundError`). NEVER use `Exception` suffix
- MUST inherit from a project-level base exception class

```python
# src/common/exceptions.py

class AppError(Exception):
    """Base exception for all project-specific errors."""

class ItemNotFoundError(AppError):
    """Raised when a requested item does not exist."""

class AuthenticationError(AppError):
    """Raised when authentication fails."""
```

## Rules

- MUST use specific exception types. NEVER use bare `except:` or `except Exception` unless re-raising
- MUST ALWAYS log errors with relevant context (IDs, relevant data, operation being performed)
- MUST re-raise exceptions that should bubble up. NEVER silently swallow exceptions
- MUST return None or default values ONLY for recoverable errors
- MUST ALWAYS include error context to aid debugging

## Example

```python
import logging

logger = logging.getLogger(__name__)

def fetch_item_data(item_id: str) -> dict | None:
    """Fetch item data with proper error handling.

    Args:
        item_id: The item ID to fetch

    Returns:
        Item data dict or None if a recoverable error occurs
    """
    try:
        response = make_api_call(item_id)
        return response.json()
    except ValueError as e:
        # MUST handle specific known errors first
        logger.error("Invalid item ID format: %s, Error: %s", item_id, e)
        raise
    except requests.RequestException as e:
        # Recoverable — return None
        logger.error("Network error fetching item %s: %s", item_id, e)
        return None
    except Exception as e:
        # MUST log unexpected errors AND re-raise. NEVER swallow silently
        logger.error("Unexpected error fetching item %s: %s", item_id, e)
        raise
```

---

# 3. Environment Variables & Secrets

## Rules

- MUST use `python-dotenv` and `.env` files for local development configuration
- MUST use `os.environ` to read environment variables in production
- MUST add `.env` to `.gitignore`. NEVER commit `.env` files to version control
- MUST provide a `.env.example` with placeholder values for required variables
- NEVER use real secrets as default values — defaults MUST be empty or clearly fake (e.g., `your-api-key-here`)
- MUST store all secrets (API keys, tokens, database credentials) as environment variables, NEVER in code or config files

## Example

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]  # MUST raise if missing in production
API_KEY = os.environ.get("API_KEY", "")  # Optional — empty default, NEVER a real key
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
```

`.env.example`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
API_KEY=your-api-key-here
DEBUG=false
```

---

# 4. Logging

## Setup

MUST configure logger at module level. NEVER use `logging.info()` directly — ALWAYS use a named logger:

```python
import logging

logger = logging.getLogger(__name__)
```

## Logging Levels

MUST use the correct level for each situation:

- **DEBUG**: Detailed diagnostic information ONLY — NEVER use in production-critical paths
- **INFO**: Normal operation confirmations
- **WARNING**: Unexpected but non-critical situations
- **ERROR**: Serious problems requiring attention. MUST ALWAYS include context
- **CRITICAL**: Program may not be able to continue

## Rules

- MUST ALWAYS include relevant context in log messages (IDs, usernames, operation names)
- MUST add `exc_info=True` when logging exceptions to capture stack traces
- MUST NEVER log sensitive information (passwords, tokens, API keys, PII)
- MUST use lazy formatting (`%s`) for log messages, NEVER f-strings in logger calls

---

# 5. Testing

## Test Generation

- MUST generate comprehensive tests alongside ALL new functions
- NEVER submit new functionality without corresponding tests

## Test File Naming

- Test files MUST use the prefix `test_` followed by the name of the file being tested
- Example: Testing `retrievals.py` → MUST create `test_retrievals.py`
- NEVER use any other naming convention for test files

## Test Function Naming

- Test functions MUST follow the convention: `test_{function_name_being_tested}`
- Example: Testing function `generate_id()` → MUST create `test_generate_id()`
- NEVER use generic test names like `test_1()` or `test_basic()`

## Test Coverage

- MUST include tests for ALL of the following:
  - Normal operation (happy path)
  - Edge cases (empty inputs, boundary values, None values)
  - Error conditions (invalid inputs, expected exceptions)
- NEVER skip edge case or error condition tests
- ALL new functionality MUST have passing tests before code review

---

# 6. Linting & Formatting

## Tools

- MUST use `ruff` for both linting and formatting
- MUST configure `ruff` in `pyproject.toml`
- MUST pass `ruff check` and `ruff format --check` before committing

## Configuration

```toml
# pyproject.toml
[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]  # E/F/W = pycodestyle + pyflakes, I = isort

[tool.ruff.format]
quote-style = "double"
```

## Rules

- MUST run `ruff check --fix` to auto-fix issues before committing
- MUST run `ruff format` to auto-format before committing
- NEVER disable linting rules inline (`# noqa`) without a comment explaining why

---

# 7. Project Structure

When creating a new Python project, MUST use this structure. When working in an existing project, MUST follow its existing structure but ALWAYS suggest this layout if asked to reorganize.

## Directory Organization

- `src/` — ALL application code MUST go here (except root files listed below)
- `src/common/gen_utils.py` — MUST store reusable utility functions here. NEVER duplicate utility logic across modules
- `tests/` — ALL test files MUST go here

## Root Directory Files

- `main.py` — Application entry point. MUST exist for application projects
- `settings.py` — Main configuration settings
- `config/` — Configuration files and templates
- `dockerfile` & `docker-compose.yaml` — Docker configuration
- `makefile` — Build automation commands

## Dependency Management

- MUST use `pyproject.toml` for new projects
- `requirements.txt` is acceptable for existing projects that already use it
- MUST use a virtual environment (`venv`) for every project. NEVER install packages globally
- MUST pin dependency versions in production projects

## Rules

- NEVER place application code in the root directory (except `main.py` and `settings.py`)
- NEVER place test files outside of `tests/`
- MUST keep `src/common/gen_utils.py` as the single location for shared utilities

---

# 8. Code Review Checklist

**MUST verify ALL items before finalizing any code changes.**

## Security

- MUST validate and sanitize ALL external inputs
- MUST have proper error handling and logging on every function that can fail
- MUST NEVER hardcode secrets, credentials, API keys, or tokens
- MUST NEVER log sensitive information (passwords, tokens, PII)

## Performance

- MUST use efficient algorithms and data structures appropriate to the problem
- MUST use caching where repeated expensive operations occur
- MUST optimize database queries — NEVER use N+1 query patterns

## Maintainability

- MUST have clear, readable code structure
- MUST have comprehensive docstrings on ALL functions
- MUST use consistent naming conventions throughout
- MUST maintain proper separation of concerns — NEVER mix business logic with I/O

## Quality Assurance

- ALL tests MUST pass before finalizing
- MUST have test coverage for new functionality
- MUST have zero linting errors or warnings
- MUST NEVER submit code that fails any of the above checks
