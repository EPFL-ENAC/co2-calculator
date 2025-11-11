# Frontend Overview

The frontend is a Single Page Application (SPA) built with Vue 3 and Quasar Framework. This overview provides setup instructions, implementation details, and references to system-wide architecture documentation.

For system architecture and technology decisions, see:

- [Component Breakdown](../architecture/09-component-breakdown.md) - Frontend layer architecture
- [Tech Stack](../architecture/08-tech-stack.md) - Technology selection rationale
- [Auth Flow](../architecture/04-auth-flow.md) - Authentication implementation
- [ADR-002 Frontend Framework](../architecture-decision-records/002-frontend-framework.md) - Why Vue 3 + Quasar

---

## Quick Start

### Prerequisites

- Node.js 18+ (LTS recommended)
- npm, yarn, or pnpm package manager
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

```bash
# Clone repository (if not already done)
git clone https://github.com/EPFL-ENAC/co2-calculator.git
cd co2-calculator/frontend

# Install dependencies
npm install
# or
yarn install

# Copy environment file
cp .env.example .env
# Edit .env with your backend API URL
```

### Development Server

```bash
# Start development server with hot reload
npm run dev
# or
quasar dev

# Application will be available at http://localhost:5173
```

### Build for Production

```bash
# Build production bundle
npm run build
# or
quasar build

# Output in dist/spa/ directory
```

---

## Project Structure

```
frontend/
├── src/
│   ├── assets/          # Static assets (images, fonts)
│   ├── components/      # Reusable Vue components
│   ├── composables/     # Vue composition functions
│   ├── layouts/         # Layout components (header, footer, sidebar)
│   ├── pages/           # Route page components
│   ├── router/          # Vue Router configuration
│   ├── stores/          # Pinia state management stores
│   ├── i18n/            # Internationalization (i18n) translations
│   ├── boot/            # Quasar boot files (plugins, etc.)
│   ├── css/             # Global styles, SCSS tokens
│   ├── App.vue          # Root application component
│   └── main.ts          # Application entry point
├── public/              # Static public files
├── index.html           # HTML template
├── quasar.config.js     # Quasar framework configuration
├── package.json         # Dependencies and scripts
└── tsconfig.json        # TypeScript configuration
```

### Key Directories

- **components/**: Organized by feature (labs/, reports/, admin/, shared/)
- **pages/**: One component per route (LabsPage.vue, DashboardPage.vue)
- **stores/**: Pinia stores for state management (authStore, labsStore)
- **router/**: Route definitions with guards for authentication
- **i18n/**: Language files (en.json, fr.json, de.json)

---

## Architecture Patterns

### Component Hierarchy

```
App.vue
└── MainLayout.vue
    ├── HeaderNav.vue
    ├── SidebarMenu.vue
    └── <router-view> (page components)
        ├── LabsPage.vue
        │   └── LabCard.vue
        ├── LabDetailPage.vue
        │   ├── LabOverview.vue
        │   ├── DataImportPanel.vue
        │   └── ResultsChart.vue
        └── AdminPage.vue
```

**Pattern**: Presentational components (UI) + Container components (logic)

### State Management (Pinia)

```typescript
// stores/labsStore.ts
export const useLabsStore = defineStore("labs", {
  state: () => ({
    labs: [],
    currentLab: null,
    loading: false,
  }),
  actions: {
    async fetchLabs() {
      /* API call */
    },
    async createLab(data) {
      /* API call */
    },
  },
  getters: {
    labsByDate: (state) => state.labs.sort(/*...*/),
  },
});
```

**Stores**: `authStore`, `labsStore`, `importsStore`, `reportsStore`, `adminStore`

### Routing

```javascript
// router/routes.ts
const routes = [
  {
    path: "/",
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      { path: "labs", component: LabsPage },
      { path: "labs/:id", component: LabDetailPage },
      { path: "reports", component: ReportsPage },
      { path: "admin", component: AdminPage, meta: { requiresRole: "admin" } },
    ],
  },
];
```

**Route Guards**: Authentication and role-based access control implemented in `router/index.ts`

---

## Development Workflow

### Running Development Server

```bash
# Start with hot module replacement
npm run dev

# Start with specific port
quasar dev --port 8080

# Start with HTTPS (for OIDC testing)
quasar dev --https
```

### Code Quality

```bash
# Lint code (ESLint)
npm run lint

# Format code (Prettier)
npm run format

# Type checking (TypeScript)
npm run type-check
```

### Testing

```bash
# Run unit tests (Vitest)
npm run test:unit

# Run component tests (Playwright)
npm run test:component

# Run E2E tests (Playwright)
npm run test:e2e

# Generate coverage report
npm run test:coverage
```

**Test Coverage Target**: 70% minimum (see [Architecture TODO](../architecture/TODO.md#testing-documentation))

---

## Configuration

### Environment Variables

Create `.env` file in `frontend/` directory:

```env
# Backend API
VITE_API_BASE_URL=http://localhost:8000/api/v1

# OIDC Authentication
VITE_OIDC_AUTHORITY=https://login.microsoftonline.com/{tenant}/v2.0
VITE_OIDC_CLIENT_ID=your-client-id
VITE_OIDC_REDIRECT_URI=http://localhost:5173/auth/callback

# Feature Flags
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_DEBUG_PANEL=true
```

**Note**: `VITE_` prefix is required for Vite to expose variables to the client.

### Quasar Configuration

Edit `quasar.config.js` for:

- Build options (target browsers, bundle splitting)
- Quasar plugins (Notify, Dialog, Loading)
- Dev server proxy (API calls to backend)
- CSS preprocessor options

---

## Authentication & Authorization

### Authentication Flow

1. User clicks "Login" → Redirect to Microsoft Entra ID (OIDC)
2. User authenticates with EPFL credentials
3. Redirect back to `/auth/callback` with authorization code
4. Frontend exchanges code for JWT token
5. Store token in memory (authStore) + localStorage (refresh token)
6. Include token in all API requests: `Authorization: Bearer <token>`

**Implementation**: `oidc-client-ts` library in `boot/oidc.ts`

**Detailed Flow**: See [Auth Flow Across Layers](../architecture/04-auth-flow.md)

### Route Protection

```javascript
// router/index.ts
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: "Login" });
  } else if (to.meta.requiresRole && !authStore.hasRole(to.meta.requiresRole)) {
    next({ name: "Forbidden" });
  } else {
    next();
  }
});
```

---

## Internationalization (i18n)

### Language Support

- **English** (en) - Default
- **French** (fr) - Primary for EPFL users
- **German** (de) - Additional support

### Translation Files

```
src/i18n/
├── en.json
├── fr.json
└── de.json
```

### Usage in Components

```vue
<template>
  <h1>{{ $t("labs.title") }}</h1>
  <p>{{ $t("labs.description", { count: labsCount }) }}</p>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t, locale } = useI18n();

// Programmatic usage
const message = t("common.success");
locale.value = "fr"; // Switch language
</script>
```

**Library**: `vue-i18n` integration with Quasar

---

## UI Component System

### Quasar Components

Leverage Quasar's extensive component library:

- **Forms**: QInput, QSelect, QDate, QFile
- **Data Display**: QTable, QCard, QList, QTree
- **Navigation**: QTabs, QDrawer, QBreadcrumbs
- **Feedback**: QDialog, QNotify, QLoading, QTooltip

**Documentation**: [Quasar Components](https://quasar.dev/vue-components/)

### Custom Components

Organized by feature in `components/`:

```
components/
├── labs/
│   ├── LabCard.vue
│   ├── LabForm.vue
│   └── LabFilters.vue
├── reports/
│   ├── ReportChart.vue (eCharts integration)
│   └── ReportExport.vue
├── shared/
│   ├── LoadingSpinner.vue
│   ├── ErrorBoundary.vue
│   └── ConfirmDialog.vue
└── admin/
    ├── UserManagement.vue
    └── FactorEditor.vue
```

### Styling

- **SCSS Tokens**: Design system tokens in `css/tokens/` (generated from Figma)
- **Global Styles**: `css/quasar.variables.scss` (Quasar theme customization)
- **Component Styles**: Scoped `<style lang="scss" scoped>`
- **Utility Classes**: Quasar's responsive classes (`.q-pa-md`, `.col-xs-12`)

---

## API Integration

### HTTP Client

```typescript
// boot/axios.ts
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
});

// Request interceptor (add auth token)
api.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`;
  }
  return config;
});

// Response interceptor (handle errors)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      authStore.logout();
    }
    return Promise.reject(error);
  },
);
```

### API Service Layer

```typescript
// services/labsService.ts
export const labsService = {
  async fetchLabs() {
    const { data } = await api.get("/labs");
    return data;
  },

  async createLab(labData) {
    const { data } = await api.post("/labs", labData);
    return data;
  },

  async importCSV(labId, file) {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await api.post(`/labs/${labId}/imports`, formData);
    return data;
  },
};
```

**Pattern**: Services abstract API calls from components/stores

---

## Data Visualization

### eCharts Integration

```vue
<template>
  <div ref="chartRef" style="width: 100%; height: 400px;"></div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import * as echarts from "echarts";

const chartRef = ref(null);
let chartInstance = null;

onMounted(() => {
  chartInstance = echarts.init(chartRef.value);
  updateChart();
});

const updateChart = () => {
  const option = {
    title: { text: "CO2 Emissions by Category" },
    xAxis: { type: "category", data: ["Travel", "Equipment", "Energy"] },
    yAxis: { type: "value" },
    series: [{ data: [120, 200, 150], type: "bar" }],
  };
  chartInstance.setOption(option);
};

watch(() => props.data, updateChart);
</script>
```

**Charts**: Bar charts, line charts, pie charts, treemaps for emissions breakdown

---

## Performance Optimization

### Code Splitting

```javascript
// router/routes.ts
const routes = [
  {
    path: "/admin",
    component: () => import("pages/AdminPage.vue"), // Lazy load
  },
];
```

### Bundle Optimization

```javascript
// quasar.config.js
build: {
  vueRouterMode: 'history',
  vitePlugins: [
    ['vite-plugin-compression', { algorithm: 'gzip' }]
  ],
  rollupOptions: {
    output: {
      manualChunks: {
        'vendor-vue': ['vue', 'vue-router', 'pinia'],
        'vendor-quasar': ['quasar'],
        'vendor-charts': ['echarts']
      }
    }
  }
}
```

### Image Optimization

- Use WebP format for images
- Lazy load images with `v-lazy` directive
- Responsive images with `<picture>` element

See [Scalability Strategy](../architecture/12-scalability.md) for system-wide performance.

---

## Troubleshooting

### Development Server Issues

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf .quasar node_modules/.vite
npm run dev
```

### OIDC Authentication Issues

- Check redirect URI matches OIDC provider configuration
- Verify client ID and tenant ID are correct
- Ensure HTTPS is enabled for production (OIDC requirement)
- Check browser console for CORS errors

### API Connection Issues

```javascript
// Check proxy configuration in quasar.config.js
devServer: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

### Build Errors

```bash
# Type check for errors
npm run type-check

# Check for ESLint errors
npm run lint

# Check Quasar configuration
quasar info
```

---

## Production Deployment

### Build Process

```bash
# Production build
npm run build

# Output: dist/spa/
# - index.html
# - assets/ (JS, CSS, images)
```

### Nginx Configuration

```nginx
server {
  listen 80;
  server_name co2calculator.epfl.ch;

  root /usr/share/nginx/html;
  index index.html;

  # SPA fallback
  location / {
    try_files $uri $uri/ /index.html;
  }

  # Cache static assets
  location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }

  # Security headers
  add_header X-Frame-Options "SAMEORIGIN";
  add_header X-Content-Type-Options "nosniff";
  add_header X-XSS-Protection "1; mode=block";
}
```

### Docker Build

```dockerfile
# Multi-stage build
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist/spa /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

For deployment architecture, see:

- [Deployment Topology](../architecture/11-deployment-topology.md) - Kubernetes setup
- [CI/CD Pipeline](../architecture/06-cicd-pipeline.md) - Automated deployment
- [Environments](../architecture/05-environments.md) - Environment configuration

---

## Additional Resources

### Architecture Documentation

- [System Overview](../architecture/02-system-overview.md) - Full system diagram
- [Component Breakdown](../architecture/09-component-breakdown.md) - Frontend layer details
- [Data Flow](../architecture/10-data-flow.md) - Data movement patterns

### External Documentation

- [Vue 3 Documentation](https://vuejs.org/)
- [Quasar Framework](https://quasar.dev/)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Vue Router Documentation](https://router.vuejs.org/)
- [Vue I18n Documentation](https://vue-i18n.intlify.dev/)
- [eCharts Documentation](https://echarts.apache.org/)

---

**Last Updated**: November 11, 2025  
**Readable in**: ~10 minutes
