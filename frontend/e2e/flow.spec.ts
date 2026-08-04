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

  // Entrar al documento: el visor del PDF es la vista por defecto.
  await item.click();
  await expect(page.getByTestId("doc-title")).toContainText("Trace-based", {
    timeout: 15_000,
  });
  await expect(page.getByTestId("pdf-canvas")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("page-pos")).toContainText("pág. 1 / 14", {
    timeout: 20_000,
  });

  // Pasar página a mano y volver a la 1.
  await page.getByTestId("next-page").click();
  await expect(page.getByTestId("page-pos")).toContainText("pág. 2");
  await expect(page.getByTestId("read-from-page")).toBeVisible();

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

  // "Leer desde esta página": salta al primer bloque de la pág. 2 (genera si hace falta).
  await page.getByTestId("read-from-page").click();
  await expect
    .poll(
      async () => {
        const pos = await page.getByTestId("block-pos").textContent();
        const t = await audio.evaluate((a: HTMLAudioElement) => a.currentTime);
        return !pos?.startsWith("bloque 1/") && t > 0.3;
      },
      { timeout: 60_000 },
    )
    .toBeTruthy();
  await expect(page.getByTestId("page-pos")).toContainText("pág. 2");

  // Dejar que guarde posición y comprobar que la recarga retoma ahí (RF-3.4-M).
  await page.waitForTimeout(6000); // > intervalo de guardado de posición (5s)
  const posText = await page.getByTestId("block-pos").textContent();
  const blockNum = posText?.match(/bloque (\d+)\//)?.[1];
  expect(Number(blockNum)).toBeGreaterThan(1); // ya no estamos en el bloque 1

  await page.reload();
  await expect(page.getByTestId("block-pos")).toContainText(`bloque ${blockNum}/`, {
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
