# ADR-001: Use uv as Python Package Manager

**Status**: Accepted  
**Date**: 2024-12-15  
**Deciders**: Development Team

## TL;DR

Use uv instead of pip/Poetry for faster builds, reproducible
deployments via lock files, and unified tooling for venv + packages.

## Context

Need Python package manager with lock file support, fast resolution,
Docker optimization, and PEP 621 compliance. Evaluated pip + venv, Poetry, and uv.

## Decision

**Use uv** for all Python dependency management.

**Why uv wins:**

- 10-100x faster than pip (Rust-based)
- Produces `uv.lock` for reproducible builds
- Native PEP 621 support (standard `pyproject.toml`)
- Official Docker images (`ghcr.io/astral-sh/uv:python3.12-alpine`)
- Unified tool (handles venv + packages)
- Maintained by Astral (same team as ruff)

## Alternatives Considered

**pip + venv** (standard library)  
✗ No lock file, slow resolution, separate tools  
✓ Universal, no dependencies

**Poetry**  
✗ Slower, non-standard `pyproject.toml`, heavier  
✓ Mature, lock file support, good UX

## Consequences

**Positive:**

- Dramatically faster builds (CI/CD + Docker)
- Reproducible environments via `uv.lock`
- Simple workflow: `uv sync` handles everything
- Docker optimization with multi-stage builds

**Negative:**

- Newer tool (less mature than pip/Poetry)
- Team learning curve (minimal, similar to pip)
- Not yet universally adopted

**Mitigation:**

- Standard `pyproject.toml` allows easy migration
- uv stable since v0.1, production-ready

## References

- [uv Documentation](https://github.com/astral-sh/uv)
- [PEP 621](https://peps.python.org/pep-0621/)
