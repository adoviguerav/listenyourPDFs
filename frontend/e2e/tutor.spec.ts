// E2E Fase 3 (M5): push-to-talk con micrófono falso → respuesta del tutor en voz
// → la narración retoma. Backend con FakeSTT/FakeLLM + espeak.
import { expect, test } from "@playwright/test";
import path from "path";

const FIXTURE = path.resolve(__dirname, "../../backend/tests/fixtures/paper-2col.pdf");

test.use({
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
    ],
    ...(process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : {}),
  },
  permissions: ["microphone"],
});

test("push-to-talk: pregunta por voz → respuesta hablada → retoma", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");

  // Documento listo (subir si la biblioteca está vacía).
  if ((await page.getByTestId("doc-item").count()) === 0) {
    await page.getByTestId("file-input").setInputFiles(FIXTURE);
  }
  const item = page.getByTestId("doc-item").first();
  await expect(item.getByText(/escuchado \d+%/)).toBeVisible({ timeout: 90_000 });
  await item.click();
  await expect(page.getByTestId("pdf-canvas")).toBeVisible({ timeout: 20_000 });

  // Escuchando…
  await page.getByTestId("play-button").click();
  const audio = page.getByTestId("audio");
  await expect
    .poll(async () => audio.evaluate((a: HTMLAudioElement) => a.currentTime), {
      timeout: 20_000,
    })
    .toBeGreaterThan(0.5);

  // Mantener pulsado el botón, hablar (el mic falso emite tono), soltar.
  const ptt = page.getByTestId("ptt-button");
  await ptt.dispatchEvent("pointerdown");
  await expect(ptt).toContainText("Suelta", { timeout: 10_000 });
  // La narración se pausa mientras grabas (RF-4.1).
  expect(await audio.evaluate((a: HTMLAudioElement) => a.paused)).toBe(true);
  await page.waitForTimeout(1200);
  await ptt.dispatchEvent("pointerup");

  // Transcript (FakeSTT) y respuesta en texto van llegando.
  await expect(page.getByTestId("ptt-transcript")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("ptt-answer")).not.toHaveText("", { timeout: 30_000 });

  // La voz del tutor suena (audio secundario avanza).
  const voice = page.getByTestId("ptt-voice");
  await expect
    .poll(async () => voice.evaluate((a: HTMLAudioElement) => a.currentTime), {
      timeout: 60_000,
    })
    .toBeGreaterThan(0.3);

  // Al terminar la respuesta, la narración principal retoma sola (RF-4.1).
  await expect
    .poll(async () => audio.evaluate((a: HTMLAudioElement) => !a.paused), {
      timeout: 60_000,
    })
    .toBeTruthy();
});
