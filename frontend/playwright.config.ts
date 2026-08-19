import { defineConfig } from "@playwright/test";

// El backend corre con proveedores locales (LLM fake + TTS espeak): pipeline real
// con audio real, sin API keys. El worker va embebido en el mismo comando.
const DATA_DIR = process.env.LYP_E2E_DATA ?? "/tmp/lyp-e2e-data";
const VENV_BIN = process.env.LYP_VENV_BIN ?? "/workspace/venv-app/bin";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  retries: 0,
  workers: 1,          // los specs comparten backend y biblioteca: nada de carreras
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:3000",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : {},
  },
  webServer: [
    {
      command:
        `sh -c 'rm -rf ${DATA_DIR} && ` +
        `LYP_DATA_DIR=${DATA_DIR} LLM_PROVIDER=fake TTS_PROVIDER=espeak STT_PROVIDER=fake LYP_WARMUP_BLOCKS=4 ` +
        `${VENV_BIN}/python -m app.worker & ` +
        `LYP_DATA_DIR=${DATA_DIR} LLM_PROVIDER=fake TTS_PROVIDER=espeak STT_PROVIDER=fake LYP_WARMUP_BLOCKS=4 ` +
        `${VENV_BIN}/uvicorn app.api.main:app --port 8000'`,
      cwd: "../backend",
      url: "http://localhost:8000/docs",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
