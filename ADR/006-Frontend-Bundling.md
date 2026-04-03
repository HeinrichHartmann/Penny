# ADR-006: Frontend Bundling and Dependency Management

## Status
Draft

## Context

The current frontend is served as plain static files:
- [src/penny/static/index.html](../src/penny/static/index.html) loads Vue and ECharts from CDNs
- [src/penny/static/app.js](../src/penny/static/app.js) contains the full application in one file
- There is no frontend package manager, bundler, or test tooling

This keeps the prototype simple, but it creates three problems:
- Dependency versions are managed implicitly via CDN URLs
- Frontend code is hard to split into maintainable modules
- Testing, linting, and future build steps have no natural home

## Decision

Adopt a small frontend toolchain based on:
- **Vite** for bundling and dev builds
- **npm** for dependency management
- **ES modules** for frontend code organization

Frontend dependencies such as `vue` and `echarts` should be installed locally and bundled into build output served by FastAPI. We should stop relying on CDNs for runtime dependencies.

The initial migration should remain in **JavaScript**, not TypeScript.

## Rationale

### Why Vite

- Minimal setup for a small app
- Fast local development
- Natural path from the current browser-based JS setup
- Easy later migration to TypeScript if needed

### Why local package management

- Reproducible dependency versions
- Better support for offline and packaged app builds
- Clean integration point for tests, linting, and formatting

### Why not TypeScript yet

The main problem today is missing build structure, not missing types.

Adding TypeScript before bundling would increase setup complexity without fixing the core issues:
- ad hoc dependency loading
- monolithic frontend structure
- missing test/build pipeline

TypeScript remains a valid follow-up once the frontend is split into modules and built through Vite.

## Consequences

- Add `package.json` and Vite config to the repository
- Move frontend code from one large file into smaller JS modules
- Build frontend assets as part of development and packaging workflows
- Update FastAPI/static serving to point at bundled assets
- Revisit TypeScript after the bundling migration is stable

## Comments

**2026-04-03 (Code Review):** Agree with this decision. The identified problems match findings from the frontend code review - the 784-line monolithic `app.js` would benefit from ES module splitting into `api.js`, `charts.js`, `dateUtils.js`, etc. The "no TypeScript yet" stance is pragmatic; adding types to a monolith doesn't address the structural issues.

One consideration: ensure Vite build output is compatible with Briefcase static asset bundling if desktop packaging remains a goal.
