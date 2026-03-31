---
name: python-conventions
description: "Python conventions: code style, error handling, logging, testing, project structure, code review, pipeline architecture, README maintenance"
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
- MUST pin dependency versions in production projects

## Rules

- NEVER place application code in the root directory (except `main.py` and `settings.py`)
- NEVER place test files outside of `tests/`
- MUST keep `src/common/gen_utils.py` as the single location for shared utilities

## Makefile (Docker Projects)

- MUST create a `Makefile` in the project root for any project that uses Docker
- MUST use the template at `$AI_AGENT_ENV_PATH/templates/Makefile.docker` as the starting point — read it and replace `{container_name}` with the project's actual container name
- MUST include AT MINIMUM these targets: `attach`, `build`, `bash`, `down`, `help`, `logs`, `restart`
- MUST add a comment above each target describing what it does (format: `# make <target> - <description>`)
- MUST list all targets in `.PHONY` at the top of the file
- Additional project-specific targets MAY be added as needed (e.g., `migrate`, `seed`, `test`)
- NEVER hardcode container names in multiple places — if the project has multiple containers, define variables at the top of the Makefile

---

# 8. Virtual Environments

## When Required

- MUST use a virtual environment when a project requires ANY packages or modules that are NOT part of the Python standard library
- Exception: If the project uses Docker for its runtime environment, a virtual environment is NOT required (Docker provides isolation)

## Setup

- MUST use Python's built-in `venv` module to create virtual environments
- MUST name the virtual environment directory `.venv` (dot-prefixed, in the project root)
- MUST add `.venv/` to `.gitignore`. NEVER commit the virtual environment to version control

```bash
# MUST create venv in the project root
python -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

## Rules

- MUST activate the virtual environment before installing packages or running the project
- MUST install ALL project dependencies inside the virtual environment. NEVER install packages globally with `pip install` outside a venv
- MUST verify the venv is active before running `pip install` — check for `(.venv)` in the shell prompt or run `which python` to confirm it points to `.venv/`
- MUST recreate the venv if switching Python versions
- NEVER use `sudo pip install` — this is always wrong

---

# 9. Code Review Checklist

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

## Documentation

- MUST verify the README is up to date with all code changes (per Section 11)
- MUST verify ARCHITECTURE.md is up to date if the change affects structure, modules, or data flow (per Section 12)
- If any code change affects features, setup, usage, structure, or configuration, the relevant docs MUST be updated in the same changeset

---

# 10. Pipeline & Workflow Architecture

## Pipeline Isolation

- Multi-step workflows MUST be structured as independent, composable stages
- Each stage MUST be a standalone function that takes explicit input and returns explicit output
- NEVER nest meaningful business logic inside other functions where it cannot be called or tested independently
- Each stage MUST be importable and callable on its own — including from tests, scripts, and notebooks

## Function Nesting

- NEVER define functions inside other functions when the inner function contains meaningful business logic
- Every testable operation MUST be a top-level or class-level function
- Helper closures are acceptable ONLY for trivial logic (e.g., sort keys, simple callbacks) that has no need for independent testing

```python
# NEVER do this — business logic trapped inside another function
def run_pipeline(raw_data: list[dict]) -> list[dict]:
    def transform(item: dict) -> dict:
        # 20 lines of meaningful transformation logic
        ...
    return [transform(item) for item in raw_data]

# MUST do this — each stage is a top-level function
def transform_item(item: dict) -> dict:
    """Transform a single raw item into the processed format.

    Args:
        item: Raw item dictionary from the data source

    Returns:
        Transformed item dictionary
    """
    # Transformation logic here
    ...

def run_pipeline(raw_data: list[dict]) -> list[dict]:
    """Execute the full processing pipeline on raw data.

    Args:
        raw_data: List of raw item dictionaries

    Returns:
        List of transformed item dictionaries
    """
    return [transform_item(item) for item in raw_data]
```

## Explicit Data Boundaries

- Each pipeline stage MUST accept typed input and return typed output
- Stages MUST NOT depend on previous stages having just executed — they MUST work with any valid input, including test fixtures or saved intermediate results
- NEVER pass shared mutable state between stages — return new data from each stage
- MUST use dataclasses, TypedDicts, or Pydantic models for complex stage inputs/outputs

```python
from dataclasses import dataclass

@dataclass
class ExtractionResult:
    """Output of the extraction stage."""
    records: list[dict]
    source_count: int
    errors: list[str]

def extract(source_paths: list[str]) -> ExtractionResult:
    """Extract raw records from source files.

    Args:
        source_paths: Paths to source data files

    Returns:
        ExtractionResult containing records and metadata
    """
    ...

def validate(data: ExtractionResult) -> list[dict]:
    """Validate extracted records and filter invalid ones.

    Args:
        data: Output from the extraction stage

    Returns:
        List of validated record dictionaries
    """
    ...
```

## Intermediate Results

- For long-running pipelines, MUST support saving and loading intermediate results so individual stages can be re-run without executing the entire pipeline
- MUST use a consistent serialization format (JSON, Parquet, or pickle depending on data type)
- Intermediate result files MUST include metadata (timestamp, stage name, input parameters) for traceability
- NEVER require the full pipeline to run end-to-end during development or debugging — each stage MUST be independently executable

```python
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def save_stage_output(data: dict, stage_name: str, output_dir: Path) -> Path:
    """Save intermediate pipeline results to disk.

    Args:
        data: The stage output data to persist
        stage_name: Name of the pipeline stage
        output_dir: Directory for intermediate result files

    Returns:
        Path to the saved output file
    """
    output_path = output_dir / f"{stage_name}_output.json"
    output_path.write_text(json.dumps(data, default=str))
    logger.info("Saved %s output to %s", stage_name, output_path)
    return output_path

def load_stage_output(stage_name: str, output_dir: Path) -> dict:
    """Load previously saved intermediate pipeline results.

    Args:
        stage_name: Name of the pipeline stage to load
        output_dir: Directory containing intermediate result files

    Returns:
        The deserialized stage output data
    """
    output_path = output_dir / f"{stage_name}_output.json"
    return json.loads(output_path.read_text())
```

---

# 11. README Maintenance

## New Projects

- MUST create a `README.md` in the project root when starting any new Python project
- The README MUST include these sections at minimum:
  - **Project Title & Description** — what the project does and why it exists
  - **Setup & Installation** — how to set up the environment, install dependencies, and configure `.env`
  - **Usage** — how to run the project, including CLI commands or entry points
  - **Project Structure** — overview of directory layout and key files
  - **Pipeline / Workflow** — if the project has multi-step pipelines, document each stage, its inputs, and its outputs
  - **Configuration** — environment variables, settings, and configuration options

## Keeping the README Current

- MUST review the README after ANY code change and update it if the change affects:
  - New or removed features / pipeline stages
  - Changed setup steps, dependencies, or environment variables
  - Modified CLI commands, entry points, or usage patterns
  - Altered project structure (new directories, moved files, renamed modules)
  - Changed configuration options or settings
- If a code change does NOT affect any of the above, the README does NOT need to change
- NEVER let the README fall out of sync with the actual code — an outdated README is worse than no README

## Rules

- MUST update the README in the SAME commit or set of changes as the code it documents — NEVER defer README updates to a later task
- MUST keep the README concise and scannable — use short descriptions, bullet points, and code blocks
- NEVER include implementation details that belong in docstrings or code comments — the README is for users and developers orienting to the project
- MUST document how to run individual pipeline stages independently (per Section 10) in the Usage or Pipeline section
- MUST update the Project Structure section when files or directories are added, moved, or removed

---

# 12. Architecture Documentation

## Session Start

- At the START of every session, MUST check if `ARCHITECTURE.md` exists in the project root
- If it exists, MUST read it to orient to the project structure before making any changes
- If it does NOT exist, MUST create it before proceeding with any other work — analyze the existing codebase and generate the file following the Required Content guidelines below
- The purpose of `ARCHITECTURE.md` is to give both humans and AI agents a high-level understanding of how the codebase is organized — it is NOT a replacement for the README or code-level docstrings

## Required Content

- **Overview** — 2-3 sentence summary of the system's purpose and design approach
- **Directory Structure** — what each top-level directory and key subdirectory is responsible for
- **Key Files** — purpose of important root-level and configuration files (e.g., `main.py`, `settings.py`, `pyproject.toml`)
- **Module Responsibilities** — what each module/package in `src/` does and its role in the system
- **Data Flow** — how data moves through the system (e.g., "scrapers fetch raw data → processors normalize it → exporters write to database")
- **External Dependencies** — what major third-party services or APIs the project integrates with and which modules own those integrations

## What NOT to Include

- NEVER include function signatures, class methods, or implementation details — that belongs in docstrings
- NEVER include setup/install instructions — that belongs in the README
- NEVER include API endpoint documentation — use a dedicated API doc or OpenAPI spec for that
- Keep descriptions to 1-2 sentences per item — this is a map, not a manual

## Keeping ARCHITECTURE.md Current

- MUST review `ARCHITECTURE.md` after ANY code change and update it if the change affects:
  - New or removed directories or modules
  - Changed module responsibilities (e.g., a module now handles a different concern)
  - New external service integrations
  - Changed data flow between components
- If a code change does NOT affect the structure or organization, `ARCHITECTURE.md` does NOT need to change
- MUST update `ARCHITECTURE.md` in the SAME commit or set of changes as the structural code change — NEVER defer

## Example

```markdown
# Architecture

## Overview
CarFinder is a pipeline that scrapes vehicle listings from multiple marketplaces,
enriches them with valuation data, and outputs ranked deals.

## Directory Structure
- `src/scrapers/` — Data collection from external marketplaces (one module per source)
- `src/processors/` — Normalization, deduplication, and enrichment of raw listings
- `src/valuations/` — Integration with pricing/valuation APIs (KBB, Edmunds)
- `src/exporters/` — Output formatters (CSV, database, notifications)
- `src/common/` — Shared utilities, custom exceptions, and data models
- `tests/` — Unit and integration tests mirroring the src/ structure
- `config/` — Environment-specific configuration templates

## Key Files
- `main.py` — Entry point; orchestrates the pipeline stages
- `settings.py` — Runtime configuration loaded from environment variables
- `pyproject.toml` — Project metadata and dependency definitions

## Data Flow
Scrapers → Processors (normalize/deduplicate) → Valuations (price lookup) → Exporters (output)
```

---

# 13. Plan Storage

- ALL implementation plans, architecture plans, and phase plans MUST be saved to `.claude/plans/` in the project directory
- NEVER save plan files to the project root or other locations
- Plan files MUST use descriptive names (e.g., `PHASE1_IMPLEMENTATION_PLAN.md`, `ARCHITECTURE_PLAN.md`)
- Plans MUST be kept up to date as work progresses — mark completed items, update status
