// @vitest-environment node
import { createServer as createHttpServer } from "node:http";
import { fileURLToPath } from "node:url";
import { createServer, loadConfigFromFile } from "vite";
import { expect, it } from "vitest";

it("preserves the browser origin and host through the configured development API proxy", async () => {
  const seen: { host: string | undefined; origin: string | undefined }[] = [];
  const backend = createHttpServer((req, res) => {
    seen.push({ host: req.headers.host, origin: req.headers.origin });
    const accepted = req.headers.origin === `http://${req.headers.host}`;
    res.statusCode = accepted ? 200 : 403;
    res.end(JSON.stringify({ accepted }));
  });
  await new Promise<void>((resolve) => backend.listen(0, "127.0.0.1", resolve));
  const address = backend.address();
  if (!address || typeof address === "string") throw new Error("Missing test backend address");
  const loaded = await loadConfigFromFile({ command: "serve", mode: "test" },
    fileURLToPath(new URL("../vite.config.ts", import.meta.url)));
  if (!loaded) throw new Error("Missing frontend configuration");
  const configured = loaded.config.server!.proxy!["/api"];
  // Retarget only this test's loopback backend. Vite's string shorthand sets changeOrigin=true.
  const proxy = typeof configured === "string"
    ? { target: `http://127.0.0.1:${address.port}`, changeOrigin: true }
    : { ...configured, target: `http://127.0.0.1:${address.port}` };
  const server = await createServer({ ...loaded.config, configFile: false,
    server: { ...loaded.config.server, host: "127.0.0.1", port: 0, strictPort: false,
      proxy: { "/api": proxy } } });
  try {
    await server.listen();
    const url = server.resolvedUrls!.local[0].replace(/\/$/, "");
    const response = await fetch(url + "/api/skill-executions/fixture/interactions/fixture/respond", {
      method: "POST", headers: { Origin: url, "Content-Type": "application/json" }, body: "{}"
    });
    expect(response.status).toBe(200);
    expect(seen).toEqual([{ host: new URL(url).host, origin: url }]);
  } finally {
    await server.close();
    backend.closeAllConnections();
    await new Promise<void>((resolve, reject) => backend.close((error) => error ? reject(error) : resolve()));
  }
}, 20000);
