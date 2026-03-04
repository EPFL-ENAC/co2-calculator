---
description: follow these guidelines for backend and frontend development to ensure code quality, type safety, and architectural consistency.
applyTo: "backend/**, frontend/**"
---

You are a senior software engineer. Follow ALL rules strictly. No explanations unless asked. Output production-ready code only.

# BACKEND — Python 3.12 (uv & Makefile)

- **Tooling**: Use `uv` for dependency management and environment execution. All common tasks (lint, test, run) must be executed via `Makefile` commands.
- **Ruff**: line-length=88, indent=4, select=["E","F","I"], double quotes, fix=true, exclude migrations.
- **Mypy**: strict mode — all public functions must have full type annotations. No `Any` unless unavoidable. `warn_unused_ignores=true`.
- **SQLAlchemy**: Always wrap column references in `col()` (e.g., `col(Model.field) == value`) to satisfy Mypy `ColumnElement` types.
- **Docstrings**: Google-style docstrings mandatory for all public functions/classes.
- **Structure**: Imports: stdlib → third-party → local (alphabetical). Functions ≤40 lines, single responsibility, ≤2 levels nesting.
- **Error Handling**: Explicit exceptions only; no bare `except`.

# FRONTEND — Vue 3 + TypeScript + Quasar

- **Script**: `<script setup lang="ts">` only. Composition API mandatory (No Options API).
- **Style**: Prettier (singleQuote=true, semi=true). ESLint (vue/flat/recommended + vueTsConfigs.recommended).
- **Types**: `defineProps`/`defineEmits` with explicit interface types; no implicit `any`.
- **Logic**: No business logic in templates; extract to Composables (`useX`).
- **State**: Pinia (strongly typed). Components ≤300 lines.
- **Cleanliness**: No `console.log`, no unused variables.

# ARCHITECTURE & WORKFLOW

- **Clean Architecture**: Strict separation of `domain` / `application` / `infrastructure`.
- **Dependency Management**: Update `pyproject.toml` using `uv add` or `uv remove`.
- **Clean Code**: No circular imports, no dead code, no commented-out code, no `TODO`s.
- **Automation**: If a task can be done via `make` (e.g., `make lint`, `make test`), use it.

# TESTING

- **Backend**: `pytest` with fixtures. Mock all external services. No real DB in unit tests.
- **Frontend**: `Vitest` for composables and business logic; separate from UI components.

# NEVER

- Ignore lint/type errors or use `# type: ignore` without a specific error code (e.g., `# type: ignore[import]`).
- Use bare column comparisons in SQLAlchemy joins—always use `col()`.
- Guess missing types; if a type is unknown, investigate the library or define a Protocol.
- Mix quote styles or leave unused imports.
