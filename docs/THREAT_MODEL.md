# Threat model

**Status:** internal engineering assessment  
**Scope:** the administrator-operated AFM application in this repository  
**Last reviewed:** 2026-10-08

This document records the current trust boundaries, security controls, and
remaining risks visible in the code and deployment configuration. It is not an
independent penetration test, compliance assessment, or approval to process live
or regulated data. Reassess it after material changes to authentication,
deployment, data handling, or the public API.

## System and trust boundaries

```text
Administrator browser
    | HTTPS must be terminated by a trusted edge proxy in production
    v
Frontend container (static UI + Nginx API proxy)
    | private Compose network
    v
FastAPI application
    | PostgreSQL connection using deployment credentials
    v
PostgreSQL data volume
```

CI is a separate boundary. It uses disposable PostgreSQL databases and
test-only credentials; its API concurrency smoke is restricted to a loopback
target. Operators, the host, the TLS-terminating proxy, environment secrets,
backup storage, and database administrators are trusted infrastructure
components and are outside the application's ability to secure on their own.

## Assets and security objectives

| Asset | Objective |
| --- | --- |
| Administrator credentials, JWT/CSRF signing secrets, session cookies | Prevent disclosure, forgery, and unauthorized use. |
| Invoice, fuel-rate, payment, and audit-event records | Preserve confidentiality and financial integrity; prevent unauthorized changes and loss. |
| Provider and airline contact information | Limit access to authorized operators and protect it in transit and at rest. |
| Database backups and restore credentials | Restrict access, protect confidentiality, and demonstrate recoverability. |
| API and database availability | Keep operations usable while bounding abusive or accidental resource consumption. |

## Threats, current controls, and residual risk

| Threat | Existing controls | Residual risk / required production action |
| --- | --- | --- |
| Stolen or guessed administrator credentials | Argon2id password hashing; login rate limit; active-admin check; short-lived signed access token. | No MFA or self-service identity provider. Protect administrator devices, use unique strong passwords, and consider MFA before production use. Rate limiting is IP-based and may affect users behind a shared NAT. |
| Session theft, cross-site request forgery, or browser script injection | HttpOnly access cookie; separate signed CSRF cookie and required mutation header; SameSite cookie setting; CSP and browser security headers in Nginx. | TLS is not terminated by this repository's Compose stack. Configure HTTPS, secure cookies, HSTS, proxy trust, and exact origins at the production edge. Review the CSP and third-party Google Fonts dependency for the deployment's privacy requirements. |
| Unauthorized API access or privilege escalation | The production entry point (`backend.app.main:app`) exposes the current `/api/v1` routes, which verify the signed token and active administrator on each request. | The repository retains a separate legacy application entry point (`app.app:app`) for compatibility tests; it has different authentication and mutation semantics and is not the Docker/CI entry point. Keep deployment commands pinned to `backend.app.main:app`; do not expose the legacy app without a separate security review. The current API has a single administrator role. |
| Invoice or payment tampering, duplicate writes, or invalid financial state | Server-calculated totals; immutable invoice snapshots and terminal lifecycle checks; payment ledger; database uniqueness, check, foreign-key, and rate-overlap constraints; concurrency tests. | Database owners can alter records directly. Database privilege separation, controlled migration credentials, monitored administrative access, and independently retained audit evidence are deployment responsibilities. |
| Repudiation or undetected privileged changes | Invoice lifecycle, cancellation, and payment events are recorded; API request IDs aid request correlation. | Request IDs are not a durable security audit log, and application audit rows are not cryptographically tamper-evident against database administrators. Define retention, access, alerting, and independent log export before regulated use. |
| Data disclosure through network, browser, logs, or backups | PostgreSQL is not published by Compose; API responses use `no-store`; application errors are brief; secrets are configured through environment settings. | Encrypt production traffic and backups, restrict and rotate secrets, define data retention, and verify that logs and monitoring never collect credentials, cookies, or unnecessary personal data. |
| Denial of service or capacity exhaustion | Login throttling; bounded query parameters; health/readiness endpoints; CI performs a 10-worker, 15-second read-only API concurrency smoke with a p95 threshold. | The CI smoke is not a capacity benchmark, sustained soak, write-load test, or production-data test. Add representative data volumes, an agreed SLO, infrastructure-level controls, and a separately approved capacity test before launch. |
| Database loss, corruption, or operator error | CI restores a PostgreSQL dump into a distinct disposable database and compares application rows and sequence state. | This does not prove production RPO/RTO, off-site backup availability, encryption, point-in-time recovery, or recovery under incident conditions. Rehearse restoration from the actual protected production backup and record measured recovery time. |
| Vulnerable or compromised dependencies and build pipeline | Locked Python/npm dependencies; CodeQL; npm advisory audit; Dependabot; protected `main` and required CI checks. | These controls do not eliminate zero-days, compromised maintainers, or unsafe release configuration. Review alerts, pin and review workflow actions, protect release credentials, and verify release artifacts. |

## Release and production-readiness gates

Before processing real or regulated financial data:

- Complete an independent threat-model review and penetration test; track findings
  to remediation or documented risk acceptance.
- Decide whether legacy API routes are supported; remove unused surfaces or test
  their authentication and authorization equivalence.
- Establish MFA, least-privilege database roles, secret rotation, encrypted
  off-site backups, audit-log retention, incident ownership, and alerting.
- Run a representative load and soak test against production-like data and
  infrastructure; define and meet latency, error-rate, and capacity objectives.
- Restore the intended production backup in an isolated environment, verify
  application-level financial records, and measure recovery point and time.
- Conduct manual keyboard, screen-reader, zoom, and assistive-technology review;
  automated axe checks alone do not establish accessibility conformance.

The repository's CI evidence is useful for regression detection. Passing it does
not satisfy these deployment-specific gates or certify regulatory compliance.
