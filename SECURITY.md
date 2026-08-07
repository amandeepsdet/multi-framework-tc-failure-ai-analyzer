# Security Policy

## Reporting a Vulnerability

Please **do not** open a public issue for security problems.

Instead, report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/security/advisories/new).
We aim to acknowledge reports within a few business days and will keep you
informed as we investigate and prepare a fix.

When reporting, please include:

- A description of the vulnerability and its impact
- Steps to reproduce (a minimal proof of concept is ideal)
- Affected version(s) and environment

## Supported Versions

See [SUPPORTED_VERSIONS.md](SUPPORTED_VERSIONS.md) for which releases receive
security updates.

## How this SDK handles your data

`aiqa` is designed to be safe by default:

- **Offline by default.** The heuristic engine and similarity search run
  entirely on your machine. No data leaves your environment unless you
  explicitly configure an LLM provider.
- **Secret masking.** Before any evidence is written to disk or sent to an LLM,
  the engine masks secrets (passwords, JWTs, bearer tokens, API keys, cookies).
  This is controlled by `AI_MASK_SECRETS` (on by default); optional URL masking
  is available via `AI_MASK_URLS`.
- **No credentials in the repo.** Provider keys are read from environment
  variables / `.env` (which is git-ignored) and are never committed.

## Scope

This policy covers the `aiqa` SDK and the bundled `qa_ai_engine` plugin. Issues
in third-party dependencies should be reported to their respective projects, but
feel free to let us know so we can bump or pin the dependency.
