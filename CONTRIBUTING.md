# Contributing to NavaiaForge SDK

Thank you for your interest in contributing to the NavaiaForge SDK. This guide covers everything you need to get started.

---

## Code of Conduct

Be respectful and constructive. We are building tools for the community and expect all contributors to act professionally.

---

## Getting Started

### Prerequisites

- **Node.js** >= 18.0.0 (for the TypeScript SDK)
- **Python** >= 3.10 (for the Python SDK)
- **Git**

### Setting Up the Development Environment

1. Fork and clone the repository:

```bash
git clone https://github.com/NavaiaSolutions/navaia-forge-sdk.git
cd navaia-forge-sdk
```

2. Set up the TypeScript SDK:

```bash
cd packages/javascript
npm install
npm run typecheck
npm test
```

3. Set up the Python SDK:

```bash
cd packages/python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
mypy navaia_forge/
```

---

## How to Contribute

### Bug Reports

Open an issue with:
- A clear title and description
- Steps to reproduce
- Expected vs. actual behavior
- SDK version, language, and runtime version

### Feature Requests

Open an issue describing:
- The problem you are trying to solve
- Your proposed solution
- Any alternatives you considered

### Pull Requests

1. Create a branch from `main`:

```bash
git checkout -b feat/my-feature
```

2. Make your changes following the code style guidelines below.

3. Add or update tests. We require 80%+ test coverage.

4. Run all checks:

```bash
# TypeScript
cd packages/javascript
npm run typecheck
npm test
npm run lint

# Python
cd packages/python
pytest --cov=navaia_forge
ruff check navaia_forge/
mypy navaia_forge/
```

5. Commit with a descriptive message using conventional commits:

```
feat: add batch task creation method
fix: handle timeout in wait_for_completion
docs: update quickstart example
```

6. Push and open a pull request against `main`.

---

## Contributing Agent Templates

Workforce templates live in the `templates/` directory as JSON files. To contribute a new template:

1. Create a JSON file following the existing template structure.
2. Include at least 2 agents with clearly defined roles.
3. Define edges between agents to show the workflow.
4. Add a descriptive `name`, `description`, and `category`.
5. Test the template by instantiating it via the SDK.
6. Submit a PR with the template and a brief description of the use case.

### Template Structure

```json
{
  "name": "My Workforce Template",
  "description": "A brief description of what this workforce does.",
  "category": "engineering",
  "runtime_mode": "claude_max",
  "agents": [
    {
      "name": "Agent Name",
      "role": "agent_role",
      "instructions": "Detailed instructions for the agent.",
      "model_provider": "anthropic",
      "model_name": "sonnet"
    }
  ],
  "edges": [
    {
      "source": "Agent A",
      "target": "Agent B",
      "approval_mode": "auto_run",
      "label": "Handoff description"
    }
  ]
}
```

---

## Code Style Guidelines

### TypeScript

- Strict mode enabled (`strict: true` in tsconfig)
- Use `readonly` for immutable properties
- Prefer `const` over `let`; never use `var`
- Use explicit return types on exported functions
- Format with the project's ESLint configuration

### Python

- Follow PEP 8
- Use type annotations on all function signatures
- Use `@dataclass(frozen=True)` for immutable data structures
- Format with `ruff` (line length: 100)
- Type-check with `mypy --strict`

### General

- Keep functions under 50 lines
- Keep files under 800 lines
- Handle errors explicitly -- never silently swallow exceptions
- Prefer immutable data structures
- No hardcoded secrets or API keys

---

## CLA Requirement

Before we can merge your first pull request, you must sign our [Contributor License Agreement](./CLA.md). This is a one-time requirement that ensures we can distribute your contributions under the project license.

---

## Questions?

Open a discussion on GitHub or reach out at dev@navaia.com.
