# 📑 Contributing Guidelines – CO₂ Calculator Development @ EPFL

## 1. Purpose

These guidelines aim to ensure the quality, security, maintainability, and longevity of the code produced for the CO₂ Calculator project. They are based on the standards described in the EPFL project specifications.

---

## 2. Project Management

- The project follows the HERMES project management methodology (Swiss federal standard).
- Development must be planned and documented per phase (design, implementation, validation, deployment).
- All development work must be linked to a planned and approved task by the EPFL project manager.

---

## 3. Development Standards

### 3.1 Documentation

- Code must be documented with clear, concise comments that explain business logic and technical choices.
- Each module should include technical documentation (README, installation guide, API docs).

### 3.2 Style Compliance

- Follow SOLID principles and general programming best practices.
- Use a consistent naming convention (English preferred; use snake_case or camelCase according to the language).
- Keep a clear, coherent file structure that matches the project architecture.

### 3.3 Security

- Follow OWASP best practices (input validation, secure session management, etc.).
- Identified vulnerabilities must be fixed immediately.
- EPFL reserves the right to perform external security audits.

### 3.4 Performance

- Code should be optimized to avoid bottlenecks.
- Load and performance tests must be integrated into the CI/CD pipeline.

### 3.5 Testability

- Each feature must be covered by unit and integration tests.
- End-to-end functional tests must be provided for critical user flows.
- Test coverage is measured automatically and must remain above the threshold agreed with EPFL (to be defined).

---

## 4. Code Review

- All new contributions must be submitted via a pull request (PR).
- Each PR must be reviewed by at least one peer reviewer, plus an EPFL expert when required.
- Review criteria:

  * Code documentation
  * Adherence to standards and best practices
  * Security
  * Performance
  * Tests and coverage

---

## 5. Integration and Deployment

- The project must remain containerized and deployable via a public container registry (Docker/OCI).
- APIs must comply with REST/JSON standards and provide OpenAPI specifications.
- Code must remain the property of EPFL (internal license).

---

## 6. Maintenance and Evolution

- After each update: run non-regression tests systematically.
- Any evolution must be discussed and validated with EPFL before implementation.
- Track fixes and changes using a ticketing tool (to be defined).

---

## 7. Knowledge Transfer

- Each delivery must include documentation and guides needed to enable the internal team to operate autonomously.
- Training sessions should be organized to ensure the EPFL teams can take over the system.

---

👉 These guidelines can be published in the repository as the `CONTRIBUTING.md` file.

Would you like me to generate a ready-to-use GitHub-flavored Markdown version for direct commit to the repo?


Medical References:
1. None — DOI: file-SACQCkqjEb9KesQCKns7QE