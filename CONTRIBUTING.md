# Contributing to reivo-guard

Thanks for your interest in contributing! This guide covers the basics.

## Development Setup

### TypeScript

```bash
cd ts
npm install
npm test          # Run tests (Vitest)
npm run build     # Build with tsup
npm run lint      # ESLint check
```

### Python

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest            # Run tests
```

## Project Structure

```
ts/           TypeScript package (npm: reivo-guard)
python/       Python package (PyPI: reivo-guard)
bench/        Benchmarks
examples/     Usage examples
```

## Making Changes

1. Fork the repo and create a branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass (`npm test` / `pytest`)
4. Keep changes focused — one feature or fix per PR

## Code Style

- **TypeScript**: ESLint + Prettier. Run `npm run lint` before committing.
- **Python**: Follow PEP 8. Type hints encouraged.

## Pull Requests

- Keep PRs small and focused
- Describe what changed and why
- Link related issues if applicable

## Reporting Issues

- Use [GitHub Issues](https://github.com/tazsat0512/reivo-guard/issues)
- Include: what you expected, what happened, and steps to reproduce

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
