# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in ContextForge, please report it responsibly.

**Do not open a public issue.** Instead, email the maintainer directly:

📧 **ayushh.ofc10@gmail.com**

### What to Include

- A description of the vulnerability
- Steps to reproduce (if applicable)
- The potential impact
- Any suggested fix (optional, but appreciated)

### Response Timeline

- **Acknowledgment:** Within 48 hours
- **Assessment:** Within 1 week
- **Fix:** As soon as possible, depending on severity

### Scope

This policy covers the ContextForge codebase and its official Docker images. Third-party dependencies (OpenAI SDK, Redis, FAISS, etc.) should be reported to their respective maintainers.

## Security Considerations

ContextForge is designed to run as a **local proxy** between your application and LLM providers. Keep the following in mind:

- **API keys** are stored in `.env` and passed to upstream providers. Never commit `.env` to version control.
- **Telemetry data** (prompts, responses, costs) is stored locally in SQLite. It never leaves your machine.
- **Redis cache** stores response data. Secure your Redis instance if running in a shared environment. If Redis is unreachable, ContextForge degrades to a cache miss rather than failing requests — it does not silently retry indefinitely or block.
- **Gateway authentication is opt-in and disabled by default** (`CONTEXTFORGE_API_KEYS` unset), which is appropriate for local single-user development. **Set `CONTEXTFORGE_API_KEYS` before exposing ContextForge beyond localhost** — this requires `Authorization: Bearer <token>` on every endpoint except `/health`. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md).
- **CORS** allows all origins by default but never enables credentialed (cookie) requests, regardless of origin configuration — the gateway is authenticated via bearer token, not cookies.

## Supported Versions

| Version | Supported |
|---------|:---------:|
| 1.0.x | ✅ |
| < 1.0 | ❌ |
