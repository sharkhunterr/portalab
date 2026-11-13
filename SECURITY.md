# Security policy

## Supported versions

Security fixes go into the latest release. Upgrade to it before reporting, in case the issue is already fixed.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report it privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Include:

- the Portalab version (shown in *Administration › About*) and how it is deployed (Docker Compose, Unraid, behind a reverse proxy…);
- what an attacker can do, and what they need first (an account, a role, network access);
- the steps or a request that reproduce it;
- any logs or screenshots that help (remove your own secrets and personal data first).

You will get an answer as soon as possible. The fix is prepared privately, released, and then the report is published with credit to you, unless you prefer to stay anonymous.

## What Portalab does about security

Every release goes through these checks before it is published:

- static analysis of the code (Bandit, Semgrep with the OWASP Top 10 rules);
- known vulnerabilities in dependencies (pip-audit, npm audit) and in the Docker image (Trivy);
- secrets in the repository's history (gitleaks);
- the Dockerfile and Compose file (Hadolint, Trivy config, a hardening test);
- OWASP ZAP against the running image, and the API fuzzed from its OpenAPI contract (Schemathesis);
- more than 75 security test files: permissions, CSRF, sessions, injection, isolation of plugins, crafted archives, secrets and personal data kept out of the logs.

Each release also comes with an SBOM (CycloneDX) of the image.

Deployment advice lives in [docs/configuration.md](docs/configuration.md): reverse proxy, trusted proxies, plain HTTP on a LAN, going on the internet.
