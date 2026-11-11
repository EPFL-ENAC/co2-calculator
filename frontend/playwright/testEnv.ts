// Runs before any app module: runtime.ts reads window.injectedEnvVariable at
// import time, and the app has no institution defaults (#500).
import { TEST_RUNTIME_ENV } from '../tests/runtimeEnv';

window.injectedEnvVariable = TEST_RUNTIME_ENV;
