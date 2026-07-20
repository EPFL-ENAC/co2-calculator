// Leaf module (no store/api/i18n imports) so pure-function Playwright
// specs can import these enums without dragging Vite-only APIs
// (import.meta.glob in src/i18n) into the node test runner.
// Values mirror the backend IngestionState/IngestionResult int enums.

export enum IngestionState {
  NOT_STARTED = 0,
  QUEUED = 1,
  RUNNING = 2,
  FINISHED = 3,
}

export enum IngestionResult {
  SUCCESS = 0,
  WARNING = 1,
  ERROR = 2,
}
