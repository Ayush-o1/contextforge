# Contributing to ContextForge

Thank you for your interest in contributing to ContextForge! Whether it's fixing a bug, improving documentation, or adding a new feature, your help is appreciated.

---

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing Guidelines](#testing-guidelines)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)
- [Definition of Done](#definition-of-done)
- [Code of Conduct](#code-of-conduct)

---

## Ways to Contribute

- **Bug reports** — Found something broken? [Open an issue](https://github.com/Ayush-o1/contextforge/issues/new).
- **Feature requests** — Have an idea? Open an issue and describe what you'd like and why.
- **Code contributions** — Fix a bug, add a feature, or improve performance.
- **Documentation** — Fix typos, clarify instructions, or add examples.
- **Testing** — Add test coverage for existing features.

---

## Development Setup

### Prerequisites

- Python 3.11+
- Docker (for Redis)
- Git

### Steps

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/Ayush-o1/contextforge.git
   cd contextforge
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**

   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY (only needed for live testing, not unit tests)
   ```

5. **Verify everything works:**

   ```bash
   ruff check app/ tests/ benchmarks/
   PYTHONPATH=. pytest tests/ -v
   ```

   All 149 tests should pass without any live API calls or running services.

---

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

### Rules

- **Line length:** 120 characters
- **Lint rules:** `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `W` (warnings)
- **Target:** Python 3.11

### Running the Linter

```bash
ruff check app/ tests/ benchmarks/
```

Fix auto-fixable issues:

```bash
ruff check --fix app/ tests/ benchmarks/
```

### Import Order

Imports should be sorted by ruff's isort rules:

1. Standard library
2. Third-party packages
3. Local imports

### Type Hints

Use type hints for function signatures. We use Pydantic models for API schemas — follow the existing patterns in `app/models.py`.

---

## Testing Guidelines

### General Rules

- **All tests must be fixture-based.** No live API calls, no running services.
- **Use `conftest.py` fixtures** for shared mocks (Redis, FAISS, proxy, router).
- **New features require tests.** No untested code will be merged.
- **Don't break existing tests.** Run the full suite before submitting a PR.

### Running Tests

```bash
# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run a specific test file
PYTHONPATH=. pytest tests/test_cache.py -v

# Run a specific test
PYTHONPATH=. pytest tests/test_cache.py::test_cache_hit -v
```

### Writing Tests

- Place tests in the `tests/` directory.
- Follow the naming convention: `test_<module>.py`.
- Use `httpx.AsyncClient` with FastAPI's `TestClient` for endpoint tests.
- Use the fixtures defined in `tests/conftest.py` — don't create new mocks if existing ones work.

### Test Coverage

| File | Tests | What's Tested |
|------|:-----:|---------------|
| `test_proxy.py` | 12 | Health, completions, streaming, error propagation |
| `test_cache.py` | 14 | VectorStore, SemanticCache, endpoint integration |
| `test_router.py` | 18 | Classifier, 1000-prompt accuracy, override header |
| `test_compressor.py` | 5 | Token counting, thresholds, fallback, system messages |
| `test_telemetry.py` | 5 | Write/read, summary, cost estimation, dedup |
| `test_adaptive.py` | 8 | Threshold tuning, min/max caps, endpoints |
| `test_cache_invalidation.py` | 7 | Flush, invalidate, stats, idempotent flush |
| `test_benchmarks.py` | 15 | Paraphrase, latency stats, routing accuracy |
| `test_tool_use.py` | — | Tool-use passthrough, schema translation, multi-provider |
| `test_failover.py` | — | LiteLLM failover routing, provider retry behavior |
| `test_phase3.py` | — | Phase 3 end-to-end router integration |
| **Total** | **149** | All pass without live API calls or running services |

---

## Branch Naming

| Pattern | Use |
|---------|-----|
| `phase/<N>-<name>` | Phase feature branches (e.g., `phase/8-dockerization`) |
| `docs/<description>` | Documentation changes |
| `fix/<description>` | Bug fixes |
| `refactor/<description>` | Non-functional improvements |
| `feat/<description>` | New features outside of the phase structure |

Always branch from `main`.

---

## Commit Messages

Write clear, concise commit messages. Use the imperative mood ("Add feature" not "Added feature").

**Format:**

```
<type>: <short description>

<optional longer description>
```

**Types:**

| Type | Use |
|------|-----|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `refactor` | Code change that doesn't fix a bug or add a feature |
| `chore` | Maintenance (deps, CI, config) |

**Examples:**

```
feat: add adaptive threshold evaluation endpoint
fix: handle Redis connection timeout in cache lookup
docs: update API reference with compression headers
test: add integration tests for cache invalidation
```

---

## Pull Request Process

### Before Submitting

1. **Branch from `main`** using the naming conventions above.
2. **Write tests** for any new functionality.
3. **Run the linter:** `ruff check app/ tests/ benchmarks/` — must pass with zero errors.
4. **Run the tests:** `PYTHONPATH=. pytest tests/ -v` — must pass with zero failures.
5. **Update documentation** if your change affects the public API, configuration, or behavior.

### PR Checklist

Copy this into your PR description:

```markdown
- [ ] Code is implemented and lint-clean (`ruff check` passes)
- [ ] Tests are written and passing (`pytest` passes)
- [ ] Existing tests still pass (no regressions)
- [ ] Documentation is updated (if applicable)
- [ ] Commit messages follow the conventions
```

### Review Process

1. Open a PR against `main`.
2. Fill in the PR description with what you changed and why.
3. A maintainer will review your PR.
4. Address any feedback and push updates.
5. Once approved, a maintainer will merge the PR.

---

## Reporting Issues

When reporting a bug, include:

1. **What you expected** to happen.
2. **What actually happened** (error messages, unexpected behavior).
3. **Steps to reproduce** the issue.
4. **Environment details:** OS, Python version, Docker version (if relevant).
5. **Relevant logs** — check the server output or `data/telemetry.db`.

For feature requests, explain:

1. **What** you want to see.
2. **Why** it would be useful.
3. **How** you imagine it working (optional, but helpful).

---

## Definition of Done

A feature is considered "done" when:

- [ ] Code is implemented and lint-clean
- [ ] Tests are written and passing
- [ ] Existing tests still pass (no regressions)
- [ ] Documentation is updated
- [ ] PR is reviewed and merged
- [ ] Version is tagged on `main` (for phase completions)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold a welcoming and inclusive environment.

---

## Questions?

If you're unsure where to start or have questions, feel free to [open an issue](https://github.com/Ayush-o1/contextforge/issues) or reach out to the maintainer at ayushh.ofc10@gmail.com.
