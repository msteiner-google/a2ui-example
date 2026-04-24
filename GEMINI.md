# Project-Specific Python Standards (Derived from pyproject.toml)

## Environment & Versioning

- **Python Version:** Use Python 3.14 features and syntax (e.g., modern type hinting).
- **Target Platform:** `py314`.

## Formatting (Ruff)

- **Line Length:** Maximum 88 characters.
- **Indentation:** 4 spaces (no tabs).
- **Quotes:** Use **double quotes** (`"`) for strings.
- **Trailing Commas:** Respect magic trailing commas (like Black).
- **Docstrings:** Use **Google style** docstrings.
- **Docstring Code:** Enable auto-formatting of code examples within docstrings.

## Linting & Quality (Ruff)

- **Ruleset:** Follow the extensive rule selections including `ANN` (annotations), `D` (pydocstyle), `I` (isort), `PL` (Pylint), and `UP` (pyupgrade).
- **Annotations:** Mandatory type annotations for functions and variables (`ANN` rules enabled).
- **Docstrings:** Mandatory docstrings for public modules, classes, and functions (`D` rules enabled).
- **Exceptions:**
  - `S101`: `assert` statements are permitted (e.g., in tests or for type narrowing).
  - `COM812` & `ISC001`: Ignored for compatibility with the Ruff formatter.
- **Variable Naming:** Use `_` or `__` prefixes for dummy/unused variables.

## Type Checking (ty / Basedpyright)

- **Mode:** Strict type hinting is preferred despite `typeCheckingMode = "off"` in config, as `ANN` rules are active in linting.
- **Imports:** Report missing imports.
- **Root Directory:** Primary source code is located in `src/`.

## General Guidelines

- Always run `ruff check --fix` and `ruff format` after generating or modifying Python code.
- Prioritize functional, maintainable, and type-safe code.
- Minimize linting errors by adhering strictly to the Ruff ruleset defined in `pyproject.toml`.
