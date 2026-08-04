// E2E de la DoD de Fase 2: subir → procesar → escuchar → retomar, RSS y PWA.
import { expect, test } from "@playwright/test";
import path from "path";

const FIXTURE = path.resolve(__dirname, "../../backend/tests/fixtures/paper-2col.pdf");

test.describe.configure({ mode: "serial" });

test("subir → procesar → escuchar → retomar", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "listenyourPDFs" })).toBeVisible();

  // Subir el PDF fixture.
  await page.getByTestId("file-input").setInputFiles(FIXTURE);

  // Aparece en la biblioteca y termina de procesarse (extracción + arranque TTS).
  const item = page.getByTestId("doc-item").first();
  await expect(item).toBeVisible({ timeout: 20_000 });
  await expect(item.getByText(/escuchado \d+%/)).toBeVisible({ timeout: 90_000 });

  // Entrar al reproductor y darle play.
  await item.click();
  await expect(page.getByTestId("doc-title")).toContainText("Trace-based", {
    timeout: 15_000,
  });
  await page.getByTestId("play-button").click();

  // El audio avanza de verdad.
  const audio = page.getByTestId("audio");
  await expect
    .poll(async () => audio.evaluate((a: HTMLAudioElement) => a.currentTime), {
      timeout: 15_000,
    })
    .toBeGreaterThan(0.5);

  // Velocidad.
  await page.getByTestId("rate-button").click();
  expect(await audio.evaluate((a: HTMLAudioElement) => a.playbackRate)).toBe(1.25);

  // Saltar al bloque siguiente y dejar que guarde posición.
  await page.getByRole("button", { name: "Siguiente ▸" }).click();
  await expect(page.getByTestId("block-pos")).toContainText("bloque 2/", {
    timeout: 15_000,
  });
  await page.waitForTimeout(6000); // > intervalo de guardado de posición (5s)

  // Recargar: retoma en el bloque 2 (RF-3.4-M).
  await page.reload();
  await expect(page.getByTestId("block-pos")).toContainText("bloque 2/", {
    timeout: 15_000,
  });
});

test("enviar a podcast publica episodio en el feed RSS", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Enviar a podcast" }).click();
  await expect(page.getByText("en podcast")).toBeVisible({ timeout: 300_000 });

  const feed = await request.get("http://localhost:8000/feed.xml");
  expect(feed.ok()).toBeTruthy();
  const xml = await feed.text();
  expect(xml).toContain("<enclosure");
  expect(xml).toContain("audio/mpeg");

  const m = xml.match(/enclosure url="([^"]+)"/);
  const mp3 = await request.get(m![1]);
  expect(mp3.ok()).toBeTruthy();
  expect((await mp3.body()).length).toBeGreaterThan(100_000);
});

test("PWA instalable: manifest y service worker accesibles", async ({ page, request }) => {
  const manifest = await request.get("http://localhost:3000/manifest.json");
  expect(manifest.ok()).toBeTruthy();
  const m = await manifest.json();
  expect(m.display).toBe("standalone");
  expect(m.icons.length).toBeGreaterThanOrEqual(2);

  const sw = await request.get("http://localhost:3000/sw.js");
  expect(sw.ok()).toBeTruthy();

  await page.goto("/");
  await expect
    .poll(async () =>
      page.evaluate(() => navigator.serviceWorker?.getRegistration().then((r) => !!r)),
    )
    .toBeTruthy();
});
