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

## Naming Conventions

- MUST use descriptive naming following Python conventions
- ALL import statements MUST be at the top of the file, NEVER inline
- NEVER use single-letter variable names outside of comprehensions or loops

## Function Requirements

- Every function MUST have a comprehensive docstring covering purpose, parameters, and return values
- Every function MUST have type hints for ALL parameters and return values
- NEVER submit a function without both a docstring and type hints

## Code Organization

- MUST refactor repetitive logic or similar code patterns appearing more than twice into reusable functions
- MUST store commonly used utility functions in `src/common/gen_utils.py` for project-wide access

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

---

# 2. Error Handling

## Rules

- MUST use specific exception types. NEVER use bare `except:` or `except Exception` unless re-raising
- MUST ALWAYS log errors with relevant context (IDs, relevant data, operation being performed)
- MUST re-raise exceptions that should bubble up. NEVER silently swallow exceptions
- MUST return None or default values ONLY for recoverable errors
- MUST ALWAYS include error context to aid debugging

## Example

```python
import logging

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
        logging.error(f"Invalid item ID format: {item_id}, Error: {e}")
        raise
    except requests.RequestException as e:
        # Recoverable — return None
        logging.error(f"Network error fetching item {item_id}: {e}")
        return None
    except Exception as e:
        # MUST log unexpected errors AND re-raise. NEVER swallow silently
        logging.error(f"Unexpected error fetching item {item_id}: {e}")
        raise
```

---

# 3. Logging

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
- MUST use f-strings for log messages with variables

---

# 4. Testing

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

# 5. Project Structure

When creating a new Python project, MUST use this structure. When working in an existing project, MUST follow its existing structure but ALWAYS suggest this layout if asked to reorganize.

## Directory Organization

- `src/` — ALL application code MUST go here (except root files listed below)
- `src/common/gen_utils.py` — MUST store reusable utility functions here. NEVER duplicate utility logic across modules
- `tests/` — ALL test files MUST go here

## Root Directory Files

- `main.py` — Application entry point. MUST exist for every project
- `settings.py` — Main configuration settings
- `config/` — Configuration files and templates
- `dockerfile` & `docker-compose.yaml` — Docker configuration
- `makefile` — Build automation commands

## Rules

- NEVER place application code in the root directory (except `main.py` and `settings.py`)
- NEVER place test files outside of `tests/`
- MUST keep `src/common/gen_utils.py` as the single location for shared utilities

---

# 6. Code Review Checklist

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
