# Security Guidelines for the `checky` Project  

This document outlines the security best practices and controls that should be applied throughout the design, implementation, testing, and deployment of the `checky` codebase. It aligns with the core security principles of Security by Design, Least Privilege, Defense in Depth, and Fail Securely.

## 1. Secure Architecture & Design

- **Secure Defaults:** All new features, endpoints, and configurations must ship with the most restrictive, secure settings by default.  
- **Modular Boundaries:** Keep components (API, RAG processor, audio module, examples, and docs) logically and physically separated to limit cross-component compromise.
- **Least Privilege:** Grant services, containers, and users only the permissions they strictly need (e.g., read-only access for documentation hosting, minimal file I/O for audio playback).
- **Defense in Depth:** Layer controls—network firewall, API gateway, application-level authorization, and data encryption—so that if one fails, others still protect the system.

## 2. Authentication & Access Control

- **API Token Authentication:** Require a strong, random API token on every request to `/v1/check` and `/v1/status/{id}`. Store tokens hashed in datastore and allow token rotation via a secure endpoint.
- **Strong Credentials:** Enforce complexity (minimum length, mixed character types) and store credentials using Argon2 or bcrypt with unique salts.
- **Session Management (if session cookies are used):**  
  - Set `Secure`, `HttpOnly`, and `SameSite=Strict` flags on cookies.  
  - Invalidate sessions on logout and after reasonable idle and absolute timeouts.
- **Role-Based Access Control (RBAC):**  
  - Define roles (e.g., admin, reader) and implement server-side checks for each protected resource.  
  - Never rely on client-side role hints.
- **Multi-Factor Authentication (MFA):** Offer MFA (e.g., TOTP or SMS) for administrative operations such as token regeneration.

## 3. Input Validation & Output Encoding

- **JSON Schema / Pydantic Validation:** Use FastAPI’s Pydantic models to enforce strict data schemas (types, lengths, patterns) on all incoming JSON payloads.
- **Prevent Injection Attacks:**  
  - Do not build SQL/command strings by concatenation.  
  - Use parameterized queries or ORMs.  
  - Avoid `eval` or dynamic code execution functions.
- **Template Safety:** If any HTML templates are used (e.g., in examples), apply context-aware escaping to user-supplied data.
- **File Uploads (Examples / Assets):**  
  - Restrict accepted file types and sizes.  
  - Store uploads outside the webroot with randomized filenames.  
  - Scan for malware if feasible.

## 4. Data Protection & Privacy

- **Transport Encryption:** Enforce TLS 1.2+ on all endpoints (API, documentation). Redirect HTTP to HTTPS and configure HSTS.
- **At-Rest Encryption:** If persistent storage is used in future (e.g., file-based logs), encrypt sensitive data at rest using AES-256.
- **Secret Management:**  
  - Never hard-code secrets or tokens in source code or repo.  
  - Use environment variables or a dedicated vault (HashiCorp Vault, AWS Secrets Manager) to inject secrets at runtime.
- **Minimal Data Retention:** Only store logs, tokens, or PII for as long as absolutely necessary. Implement data-deletion workflows to comply with GDPR/CCPA.
- **No Sensitive Data in Logs:** Mask or omit PII and secrets from application and access logs.

## 5. API & Service Security

- **Rate Limiting & Throttling:** Implement per-token and per-IP limits to mitigate brute-force and DoS attacks. Return `429 Too Many Requests` when limits are hit.
- **CORS Policy:** Allow only trusted origins in production (e.g., your corporate domain or specific dashboards) and restrict methods to only what’s needed.
- **Strict HTTP Methods:** Map operations to correct verbs (`POST /v1/check`, `GET /v1/status`). Reject mismatched methods with `405 Method Not Allowed`.
- **Versioning:** Always expose versioned routes (`/v1/...`) and deprecate older versions gracefully.
- **Minimal Response Surface:** Expose only necessary JSON fields. Do not return internal stack traces or debug information.

## 6. Web Application Security Hygiene

- **CSRF Protection:** If the frontend interacts with the API via cookies, implement anti-CSRF tokens on all state-changing requests.
- **Security Headers:**  
  - Content-Security-Policy (CSP) to restrict script sources.  
  - X-Frame-Options: `DENY` or `SAMEORIGIN` to prevent clickjacking.  
  - X-Content-Type-Options: `nosniff` to prevent MIME sniffing.  
  - Referrer-Policy: `strict-origin-when-cross-origin`.
- **Cookie Hardening:** If any session or token is stored in a cookie, mark it `Secure`, `HttpOnly`, and a strict `SameSite` attribute.
- **Third-Party Integrity:** Use Subresource Integrity (SRI) hashes for any CDN-hosted scripts or stylesheets.

## 7. Infrastructure & Configuration Management

- **Server Hardening:**  
  - Disable unused services and ports.  
  - Keep the OS and dependencies up to date with security patches.  
  - Enforce strong SSH key policies if remote access is needed.
- **Container Security:**  
  - Build minimal Docker images and scan them with tools like Trivy.  
  - Run containers with non-root user privileges.  
  - Limit container capabilities (use seccomp, AppArmor).
- **No Default Credentials:** Change all out-of-the-box passwords and disable default accounts.
- **Disable Debug Mode in Production:** Ensure FastAPI, Uvicorn, and third-party libraries are not running in debug or verbose mode in production.

## 8. Dependency Management

- **Lockfiles & Pinning:** Use a lockfile (`poetry.lock` or `requirements.txt` with pinned versions) to guarantee reproducible builds.
- **Vulnerability Scanning:** Integrate SCA tools (e.g., Dependabot, Snyk, GitHub Advanced Security) into CI to detect CVEs in direct and transitive dependencies.
- **Minimal Footprint:** Only install required libraries. Avoid large frameworks or modules that introduce unneeded attack surface.
- **Regular Updates:** Schedule periodic dependency upgrades and rebuilds to incorporate new security patches.

## 9. Logging, Monitoring & Incident Response

- **Structured Logging:** Emit JSON-structured logs at appropriate levels (INFO, WARN, ERROR) with relevant context (request IDs, user IDs) but no secrets.
- **Centralized Aggregation:** Ship logs to a central platform (ELK, Splunk, or hosted services) and set retention policies.
- **Real-Time Alerts:** Integrate Sentry or equivalent to capture unhandled exceptions and performance anomalies.
- **Audit Trails:** Record administrative actions (token regeneration, password resets) with timestamps and actors for forensic analysis.
- **Incident Playbook:** Maintain a documented response plan covering detection, containment, eradication, recovery, and post-mortem steps.

## 10. Compliance & Privacy Considerations

- **Data Minimization:** Collect and process only the data necessary for validation and reporting.
- **Consent & Disclosure:** If collecting PII (emails for registration), provide clear privacy notices and allow users to delete their data.
- **Retention & Deletion:** Implement workflows to purge inactive accounts and expired data in line with legal requirements.
- **Storage Localization:** If required by regulation, restrict data storage to specific geographic regions.

---
By adhering to these guidelines, the `checky` project will maintain a robust security posture across its API, infrastructure, and user-facing components. Regular reviews and updates to these practices should be scheduled as the codebase and threat landscape evolve.