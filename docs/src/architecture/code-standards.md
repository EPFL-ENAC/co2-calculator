# Code Standards and Guidelines

This guide defines coding standards, testing requirements, and
dependency management policies for maintaining code quality across
the CO₂ Calculator project.

## Core Principles

Write code that is:

- **Readable** - Clear naming and structure
- **Maintainable** - Easy to modify and extend
- **Testable** - Designed for automated testing
- **Secure** - No secrets, follows security best practices
- **Documented** - Comments explain why, not what

Use English for all code, comments, and documentation.

## Naming Conventions

Follow language-specific conventions consistently:

**Python:**

- Variables/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

**JavaScript/TypeScript:**

- Variables/functions: `camelCase`
- Classes/Components: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

**Files:**

- All files: `kebab-case.ext`
- Components: `ComponentName.vue` (exception for Vue)
- Test files: `module-name.test.ts`

**Database & DTOs:**

- Tables: `plural_snake_case` (e.g., `user_profiles`)
- Columns: `snake_case`
- DTOs: Match database column names exactly
- **Critical**: Never translate naming across environments

## Language-Specific Standards

### Python

Follow PEP 8 and [Python Guide](https://docs.python-guide.org/).

**Code style:**

```python
def calculate_emissions(distance: float, mode: str) -> float:
    """Calculate CO2 emissions for travel.

    Args:
        distance: Distance in kilometers
        mode: Transportation mode (car, train, plane)

    Returns:
        Emissions in kg CO2

    Raises:
        ValueError: If mode is invalid
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")

    return distance * EMISSION_FACTORS[mode]
```

**Requirements:**

- Type hints for function signatures
- Docstrings for all public functions/classes
- Use `ruff` for linting
- Format with `ruff`
- Unit tests with `pytest`

**Testing:**

```python
def test_calculate_emissions_car():
    result = calculate_emissions(100, "car")
    assert result == 20.0  # 100km * 0.2 kg/km

def test_calculate_emissions_invalid_mode():
    with pytest.raises(ValueError):
        calculate_emissions(100, "invalid")
```

### JavaScript/TypeScript

Follow ESLint configuration in project.

**Code style:**

```typescript
interface EmissionCalculation {
  distance: number;
  mode: TransportMode;
  emissions: number;
}

export function calculateEmissions(
  distance: number,
  mode: TransportMode,
): number {
  if (!isValidMode(mode)) {
    throw new Error(`Invalid transport mode: ${mode}`);
  }

  return distance * EMISSION_FACTORS[mode];
}
```

**Requirements:**

- TypeScript for all new code
- Explicit return types
- Avoid `any` type
- Document complex logic
- Use Vitest for tests

**Testing:**

```typescript
describe("calculateEmissions", () => {
  it("calculates car emissions correctly", () => {
    const result = calculateEmissions(100, "car");
    expect(result).toBe(20.0);
  });

  it("throws error for invalid mode", () => {
    expect(() => calculateEmissions(100, "invalid")).toThrow(
      "Invalid transport mode",
    );
  });
});
```

### HTML/CSS

**HTML - Semantic and accessible:**

```html
<!-- Good: Semantic tags with ARIA -->
<nav aria-label="Main navigation">
  <ul>
    <li><a href="/dashboard">Dashboard</a></li>
  </ul>
</nav>

<main>
  <h1>Calculate Emissions</h1>
  <button type="button" aria-label="Calculate results" @click="calculate">
    Calculate
  </button>
</main>

<!-- Bad: Divs without semantics -->
<div class="nav">
  <div class="item">Dashboard</div>
</div>
```

**Accessibility requirements:**

- WCAG Level AA compliance
- Semantic HTML elements
- Keyboard navigation support
- Visible focus indicators
- Alt text for images
- ARIA labels where needed

**CSS - Use design tokens:**

```css
/* Good: Design tokens */
.card {
  padding: var(--spacing-md);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  border-radius: var(--radius-sm);
}

/* Bad: Hardcoded values */
.card {
  padding: 16px;
  color: #333333;
  font-size: 14px;
  border-radius: 4px;
}
```

**Requirements:**

- Use CSS variables for all values
- Prefer `rem`/`em` over `px`
- Mobile-first responsive design
- No component library overrides
- Use Stylelint

## Security Standards

### Critical Rules

**Never commit secrets:**

- No API keys in code
- No passwords in config
- No tokens in comments
- Use environment variables
- Review before commit

**Input validation:**

```python
# Validate and sanitize user input
def create_user(email: str, name: str) -> User:
    if not is_valid_email(email):
        raise ValueError("Invalid email format")

    sanitized_name = sanitize_input(name)
    return User(email=email, name=sanitized_name)
```

**SQL injection prevention:**

```python
# Good: Parameterized queries
cursor.execute(
    "SELECT * FROM users WHERE email = %s",
    (email,)
)

# Bad: String concatenation
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

**Dependencies:**

- Run security audits regularly
- Update vulnerable packages immediately
- Review Dependabot alerts
- Pin exact versions

## Testing Requirements

### Coverage Standards

Minimum test coverage: **60%** across the codebase

Track coverage:

```bash
# Backend
cd backend && make coverage

# Frontend
cd frontend && npm run test:coverage
```

### Test Types

**Unit tests** - Test individual functions:

```python
def test_calculate_discount():
    assert calculate_discount(100, 0.1) == 10.0
    assert calculate_discount(0, 0.5) == 0.0
```

**Integration tests** - Test component interactions:

```python
async def test_user_registration_flow():
    response = await client.post("/api/users", json={
        "email": "test@epfl.ch",
        "name": "Test User"
    })
    assert response.status_code == 201
    assert response.json()["email"] == "test@epfl.ch"
```

**E2E tests** - Test critical user flows:

```typescript
test("user can calculate emissions", async ({ page }) => {
  await page.goto("/calculator");
  await page.fill('[name="distance"]', "100");
  await page.selectOption('[name="mode"]', "car");
  await page.click('button[type="submit"]');

  await expect(page.locator(".result")).toContainText("20.0 kg CO₂");
});
```

### Test Principles

- Tests should be deterministic (no random data)
- Test one thing at a time
- Use descriptive test names
- Mock external dependencies
- Clean up test data

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
cd backend && pytest tests/test_emissions.py

# Run with coverage
make coverage
```

## Dependencies Management

### Adding Dependencies

**Python with uv:**

```bash
cd backend
uv add package-name==1.2.3
make install
```

**Node.js with npm:**

```bash
cd frontend
npm install package-name@1.2.3 --save-exact
```

### Version Pinning Policy

**Hard versioning required** - Always use exact versions:

```toml
# pyproject.toml - Good
dependencies = [
    "fastapi==0.104.1",
    "pydantic==2.5.0"
]

# Bad - No ranges allowed
dependencies = [
    "fastapi>=0.104",  # ❌
    "pydantic~=2.5.0"  # ❌
]
```

```json
// package.json - Good
{
  "dependencies": {
    "vue": "3.3.4",
    "pinia": "2.1.7"
  }
}

// Bad - No ranges allowed
{
  "dependencies": {
    "vue": "^3.3.4",   // ❌
    "pinia": "~2.1.7"  // ❌
  }
}
```

### Upgrade Strategy

**Security updates only** unless approved by PM:

1. Monitor security advisories
2. Test updates in dev environment
3. Document breaking changes
4. Create PR with clear description

**Major version upgrades require RFC:**

- Breaking changes need proposal
- Migration path documented
- Team discussion and approval

### Dependency Audits

Run security audits regularly:

```bash
# Python
cd backend && uv pip audit

# Node.js
cd frontend && npm audit

# Check Dependabot alerts
# Visit GitHub Security tab
```

Fix critical vulnerabilities immediately.

## Performance Guidelines

### Backend Performance

- Use database indexes for frequent queries
- Implement pagination for large datasets
- Cache expensive computations
- Use async/await for I/O operations
- Profile slow endpoints

```python
# Good: Async database queries
async def get_user_emissions(user_id: int) -> List[Emission]:
    return await db.query(Emission)\
        .filter(user_id=user_id)\
        .limit(100)\
        .all()

# Good: Caching
@cache(ttl=3600)
async def get_emission_factors() -> dict:
    return await db.query(EmissionFactor).all()
```

### Frontend Performance

- Lazy load routes and components
- Optimize images (WebP, compression)
- Minimize bundle size
- Use virtual scrolling for long lists
- Debounce user input

```typescript
// Good: Lazy loading
const Dashboard = defineAsyncComponent(() => import("./views/Dashboard.vue"));

// Good: Debouncing
const debouncedSearch = debounce((query: string) => {
  performSearch(query);
}, 300);
```

### Performance Testing

Optional but recommended for backend:

- Load testing with k6 or locust
- Monitor response times
- Profile database queries
- Check memory usage

## Documentation Standards

### Code Comments

Explain **why**, not **what**:

```python
# Good: Explains reasoning
# Use exponential backoff to avoid overwhelming the API
# during high traffic periods
await retry_with_backoff(api_call, max_attempts=3)

# Bad: States the obvious
# Call the API
await api_call()
```

### Module Documentation

Each module needs README:

- Purpose and scope
- Installation steps
- Usage examples
- API reference (if applicable)

### API Documentation

Document all endpoints:

```python
@router.post("/emissions", response_model=EmissionResponse)
async def calculate_emissions(request: EmissionRequest):
    """Calculate CO2 emissions for transportation.

    Args:
        request: Calculation parameters (distance, mode)

    Returns:
        EmissionResponse with calculated values

    Raises:
        HTTPException: 400 if invalid input
    """
```

Use OpenAPI/Swagger for REST APIs.

## Code Review Checklist

Before approving PR, verify:

- [ ] Code follows style guidelines
- [ ] Tests added with good coverage
- [ ] Documentation updated
- [ ] No hardcoded secrets or values
- [ ] Security considerations addressed
- [ ] Performance impact acceptable
- [ ] Accessibility requirements met (UI)
- [ ] Error handling implemented
- [ ] Linter passes without warnings

## Tools and Automation

**Python:**

- `ruff` - Fast linting + Code formatting
- `mypy` - Type checking
- `pytest` - Testing
- `coverage` - Test coverage

**JavaScript/TypeScript:**

- `eslint` - Linting
- `prettier` - Formatting
- `vitest` - Testing
- `typescript` - Type checking
- `stylelint` - CSS linting

Run all checks: `make ci` from project root.
