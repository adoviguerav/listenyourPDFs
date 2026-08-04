// Service worker mínimo: requisito de instalabilidad PWA. La cache offline llega en v1 (RF-3.5).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
