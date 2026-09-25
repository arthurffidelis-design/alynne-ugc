// Service worker mínimo: permite instalar o app na tela inicial.
// Não guarda nada em cache para a Alynne sempre ver a versão mais nova.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
