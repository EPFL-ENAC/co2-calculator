# EPFL CO₂ Calculator — Frontend

Vue 3 + Quasar 2 SPA. See
[Tech Stack](../docs/src/architecture/08-tech-stack.md) for the full
toolchain and [CONTRIBUTING](../CONTRIBUTING.md) for the contributor
workflow.

## Install dependencies

```bash
make install
```

The repo is npm-only (committed `package-lock.json`); the `make install`
target wraps `npm install --ignore-scripts`.

## Start the dev server

Hot-code reloading on `http://localhost:9000`:

```bash
make dev
```

## Lint and format

```bash
make lint    # prettier --check + eslint + stylelint
make format  # auto-fix
```

## Type-check

```bash
make type-check  # vue-tsc (canonical, matches husky/CI)
```

## Build

```bash
make localbuild  # SPA build → dist/spa
make serve       # preview the built SPA locally
make build       # Docker image (production container)
```

## Tests

```bash
make test  # component tests + Playwright E2E
```

## Quasar configuration

See [Configuring quasar.config.js](https://v2.quasar.dev/quasar-cli-vite/quasar-config-js).

## Storybook

```bash
make storybook-install  # one-time
make storybook          # start dev server
```

## See also

- Root [`Makefile`](../Makefile) — CI orchestration (`make ci`).
- [`frontend/Makefile`](Makefile) — full list of targets (`make help`).
