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
- **Redis cache** stores response data. Secure your Redis instance if running in a shared environment.
- **No authentication** is built into ContextForge itself. If exposing it beyond localhost, add a reverse proxy with authentication.

## Supported Versions

| Version | Supported |
|---------|:---------:|
| 0.7.x | ✅ |
| < 0.7 | ❌ |
