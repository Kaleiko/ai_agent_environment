# Project Initialization Instructions

## Environment File Rules
- NEVER create or read .env files - users handle these exclusively

## Initialization Control
Check the **PROJECT INITIATION DATE** field below:
- If it contains a real date (e.g., JULY 15, 2025): STOP - initialization already completed
- If it contains `<date>`: PROCEED with all instructions below, then replace `<date>` with today's date

**PROJECT INITIATION DATE: December 21, 2024**

## Instructions (only execute if `<date>` is present above)
- if executing instructions in this file, never use any delete or remove type operations for items exclusively in this file without first asking for confirmation even if user asks you to run this file autonomously. 

# File and Folder Creation

- Check if following files and folders exist in project.  If any files or folders do not exist, create them.  Any newly created files can be left blank
    - `src/`
    - `src/common/`
    - `src/common/gen_utils.py`
    - `main.py`
    - `config/`
    - `config/config.py`
    - `tests/`
    - `README.md`
    - `.vscode/`
    - `.vscode/settings.json`
    - `.claude/`


## Update VS Code Settings

1. Add the following to `.vscode/settings.json`
```json
{
    "security.workspace.trust.untrustedFiles": "open",
    "files.promptForFileCreation": false,
    "files.promptForFileModification": false
}
```

## pyproject.toml

1. Check if `pyproject.toml` file exists in root project directory. If does not exist, CREATE `pyproject.toml` file in root project path and then proceed to complete all steps for this section.
2. Copy contents from ai/ai_docs/templates/pyproject.toml_project into the pyproject.toml file


## .gitignore
1. Check if `.gitignore` file exists in root project directory. If does not exist, CREATE `.gitignore` file in root project path and then proceed to step 2.
2. Copy contents from ai/ai_docs/templates/.gitignore_python into the .gitignore file