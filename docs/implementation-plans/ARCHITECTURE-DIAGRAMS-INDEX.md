# Documentation Index - Backend Architecture

## Overview

This index provides quick access to all backend architecture documentation and Mermaid diagrams.

## Quick Reference

### 📋 Implementation Plans

- **[Backend Dead Code Removal](./backend-dead-code-removal.md)** - Complete implementation plan and results
- **[Dead Code Removal Report](./DEAD-CODE-REMOVAL-REPORT.md)** - Final report with executive summary

### 🔄 Request Flow Diagrams

**File**: [`backend-request-flow-diagrams.md`](./backend-request-flow-diagrams.md)

| #   | Diagram                     | Description                          | Use Case                          |
| --- | --------------------------- | ------------------------------------ | --------------------------------- |
| 1   | Authentication Flow         | JWT validation, OAuth2 callback      | User login, session management    |
| 2   | Carbon Reports Flow         | Report creation and listing          | Yearly carbon footprint reports   |
| 3   | Modules Data Flow           | Module data retrieval, item creation | Equipment, travel, headcount data |
| 4   | Factors Flow                | Factor lookup and classification     | Emission factor queries           |
| 5   | Backoffice Flow             | Unit reporting and filtering         | Admin reporting dashboard         |
| 6   | Audit Flow                  | Audit log retrieval                  | Change tracking, compliance       |
| 7   | Data Sync Flow              | Ingestion jobs and streaming         | External data integration         |
| 8   | Files Flow                  | File upload/download                 | CSV imports, exports              |
| 9   | Architecture Layer Diagram  | System layers overview               | High-level architecture           |
| 10  | Request Processing Flow     | Complete request lifecycle           | Understanding request handling    |
| 11  | Module Data Flow (Detailed) | Factor enrichment, emissions         | Detailed module processing        |
| 12  | Audit Trail Creation Flow   | Audit document creation              | Audit trail mechanism             |

### 🏗️ Architecture Overview Diagrams

**File**: [`backend-architecture-overview.md`](./backend-architecture-overview.md)

| #   | Diagram                      | Description                     | Use Case                |
| --- | ---------------------------- | ------------------------------- | ----------------------- |
| 1   | Complete System Architecture | All components and interactions | System overview         |
| 2   | User Authentication Flow     | OAuth2/OIDC integration         | Authentication flow     |
| 3   | Carbon Report Creation Flow  | Report creation with audit      | Report lifecycle        |
| 4   | Module Data Entry Flow       | Data entry with factor lookup   | Data entry process      |
| 5   | Factor Lookup Flow           | Classification merging          | Factor resolution       |
| 6   | Backoffice Reporting Flow    | Aggregated reporting            | Reporting generation    |
| 7   | Data Ingestion Flow          | Background job processing       | Data import process     |
| 8   | Component Interaction Map    | Routes → Services → Repos       | Component relationships |
| 9   | Technology Stack             | All technologies used           | Tech stack overview     |
| 10  | Deployment Architecture      | Kubernetes deployment           | Deployment structure    |
| 11  | Security Architecture        | Security layers                 | Security overview       |

## How to Use These Diagrams

### For New Developers

1. Start with **Complete System Architecture** (Architecture Overview #1)
2. Review **Request Processing Flow** (Request Flow #10)
3. Study specific feature flows (e.g., **Authentication Flow** #1)
4. Read **Technology Stack** diagram for tech overview

### For Troubleshooting

1. Identify the feature area (e.g., carbon reports, modules)
2. Find the corresponding **Request Flow Diagram**
3. Trace the flow to identify where issues occur
4. Check **Component Interaction Map** for dependencies

### For Feature Development

1. Review **Architecture Layer Diagram** (Request Flow #9)
2. Study similar existing features' flows
3. Use **Component Interaction Map** to understand where to add code
4. Follow patterns from existing diagrams

### For Architecture Reviews

1. Start with **Complete System Architecture**
2. Review **Deployment Architecture**
3. Check **Security Architecture**
4. Examine specific feature flows as needed

## Diagram Legend

### Symbols Used

- **Rectangle** - Component or service
- **Cylinder** - Database or storage
- **Cloud** - External service
- **Arrow** - Data flow or dependency
- **Dashed Arrow** - Async communication

### Color Coding

- **Blue** - Frontend/Client layer
- **Green** - Service/Business logic layer
- **Orange** - Data/Repository layer
- **Purple** - Infrastructure/Core layer
- **Red** - Security/Authentication
- **Yellow** - External services

## Common Patterns

### Request Flow Pattern

```
Frontend → API Router → Auth → Service → Repository → Database
```

### Response Flow Pattern

```
Database → Repository → Service → API Router → Frontend
```

### Error Handling Pattern

```
Any Layer → Exception Handler → Logger → Error Response
```

### Audit Trail Pattern

```
Mutation → Service → Audit Service → Audit Repository → Database
```

## File Locations

### Backend

```
backend/
├── app/
│   ├── api/v1/          # Route handlers
│   ├── services/        # Business logic
│   ├── repositories/    # Data access
│   ├── models/          # Database models
│   ├── schemas/         # Pydantic schemas
│   └── core/            # Core infrastructure
└── tests/               # Test files
```

### Frontend

```
frontend/
├── src/
│   ├── api/             # API client functions
│   ├── stores/          # Pinia stores
│   └── components/      # Vue components
```

### Documentation

```
docs/
└── implementation-plans/
    ├── backend-dead-code-removal.md
    ├── DEAD-CODE-REMOVAL-REPORT.md
    ├── backend-request-flow-diagrams.md
    └── backend-architecture-overview.md
```

## Quick Links

### Most Used Diagrams

1. [Authentication Flow](./backend-request-flow-diagrams.md#1-authentication-flow)
2. [Modules Data Flow](./backend-request-flow-diagrams.md#3-modules-data-flow)
3. [Complete System Architecture](./backend-architecture-overview.md#complete-system-architecture)
4. [Request Processing Flow](./backend-request-flow-diagrams.md#10-request-processing-flow)

### Feature-Specific Flows

- **Carbon Reports**: [Carbon Reports Flow](./backend-request-flow-diagrams.md#2-carbon-reports-flow)
- **Modules**: [Modules Data Flow](./backend-request-flow-diagrams.md#3-modules-data-flow)
- **Factors**: [Factors Flow](./backend-request-flow-diagrams.md#4-factors-flow)
- **Backoffice**: [Backoffice Flow](./backend-request-flow-diagrams.md#5-backoffice-flow)
- **Audit**: [Audit Flow](./backend-request-flow-diagrams.md#6-audit-flow)
- **Data Sync**: [Data Sync Flow](./backend-request-flow-diagrams.md#7-data-sync-flow)

## Maintenance

### Updating Diagrams

When making changes to the codebase:

1. Identify affected diagrams
2. Update diagrams to reflect new flow
3. Add new diagrams for new features
4. Keep documentation in sync with code

### Version Control

- Diagrams are version-controlled with code
- Commit messages should reference updated diagrams
- Major architecture changes should update multiple diagrams

## Contributing

### Adding New Diagrams

1. Create diagram in appropriate file
2. Add to this index
3. Update related diagrams if needed
4. Document in implementation plan if significant

### Diagram Standards

- Use consistent naming conventions
- Follow color coding scheme
- Keep diagrams focused and not too complex
- Add descriptions for complex flows
- Test diagrams render correctly in Mermaid

## Support

For questions about:

- **Architecture**: Review Complete System Architecture diagram
- **Request Flows**: Find relevant feature flow diagram
- **Component Relationships**: Check Component Interaction Map
- **Deployment**: Review Deployment Architecture diagram
- **Security**: Study Security Architecture diagram

---

**Last Updated**: March 16, 2026  
**Maintained By**: Backend Team  
**Version**: 1.0
