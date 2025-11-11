### 🎯 **Project Goal**

Develop an **open-source CO2 calculator** for EPFL research activities — allowing each lab to measure, visualize, and simulate its CO2 emissions. The tool must be **scalable, secure, and reusable by other academic institutions**.

---

### 🧱 **Core Deliverables (Mandate de base)**

#### 1. **Custom Web Application**

- Responsive web app following **EPFL IT standards and branding**
- Multi-language (EN required, extensible to FR and others)
- Secure authentication via **MS Entra ID (OIDC/SAML2)**
- Modular, containerized architecture (deployable via Docker/registry)
- REST API (JSON, documented with OpenAPI/Swagger)

#### 2. **Main Functional Modules**

| Module                                 | Purpose                                                              |
| -------------------------------------- | -------------------------------------------------------------------- |
| **Mon Laboratoire**                    | Annual data input for CO2 sources                                    |
| **Déplacements professionnels**        | Capture & calculate travel emissions                                 |
| **Infrastructure**                     | Buildings, energy use, equipment                                     |
| **Consommation électrique équipement** | Energy from lab devices                                              |
| **Achats**                             | Purchases and material impacts                                       |
| **Services internes**                  | Shared platforms and internal services                               |
| **Visualisation des résultats**        | Dashboards, PDF/CSV exports                                          |
| **Documentation & Contact**            | Help, support, resources                                             |
| **Interfaces de gestion (admin)**      | IT and business management dashboards, logs, user roles, data import |

#### 3. **Roles & Access**

- Gestionnaire IT
- Gestionnaire Métier (complet / restreint)
- Utilisateur·rice principal·e
- Utilisateur·rice standard

Access rights and views depend on role and faculty (managed via Entra ID groups).

#### 4. **Data Integration**

- Manual CSV import validation
- Optional automated ingestion (e.g., lab energy data, staff database)
- Integration with **EPFL Accred** for user–unit linkage
- Externalized logging and retention (1–10 years)

#### 5. **Maintenance & Support**

- **Corrective & preventive maintenance**
- SLA-based intervention times (P1–P3 priority levels)
- Annual high-load period in February (optional enhanced support)
- Regular security & dependency updates, regression tests

#### 6. **Training & Knowledge Transfer**

- Documentation + training for ~10 internal staff
- EPFL takes ownership of code and operation after handover

---

### ⚙️ **Technical & Organizational Requirements**

- Must comply with **EPFL’s IT and security standards** (Annexe 8)
- Follow **HERMES project methodology** for project management
- Code reviews by EPFL (SOLID, OWASP, test coverage required)
- Deliver within **Q2 2026 (target production)**
- Open-source and portable to other institutions

---

### 🧩 **Optional Modules / Extensions**

- Infrastructure – direct emissions
- Achats – transport & other submodules
- Impact of external cloud services
- Simulation of research projects
- AI-assisted data integration (optional)
- Additional visualization and emission models

---

### 💸 **Evaluation Weighting (for awareness)**

| Criterion           | Weight |
| ------------------- | ------ |
| Functional coverage | 40%    |
| Price               | 30%    |
| Organization        | 10%    |
| References          | 10%    |
| Sustainability      | 5%     |
| Offer quality       | 5%     |
