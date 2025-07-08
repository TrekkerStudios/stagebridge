// src/index.js
import { Hono } from "hono";
import bonjour from "bonjour";
import { cors } from "hono/cors";
import { assets } from './embedded_assets.js'; // Import the embedded assets

// --- Zeroconf Discovery Setup (Unchanged) ---
const bj = bonjour();
const discoveredDevices = new Map();
const browser = bj.find({ type: "stagebridge-api", protocol: "tcp" });

browser.on("up", (service) => {
  console.log("Device discovered:", service.name);
  discoveredDevices.set(service.fqdn, {
    name: service.name,
    host: service.host,
    ip: service.addresses?.[0],
    port: service.port,
    fqdn: service.fqdn,
  });
});

browser.on("down", (service) => {
  console.log("Device went away:", service.name);
  discoveredDevices.delete(service.fqdn);
});

console.log("Starting network discovery for StageBridge devices...");

// --- Hono Web Server Setup ---
const app = new Hono();

// Middleware
app.use("*", cors());

// --- API Routes (Unchanged) ---
app.get("/api/devices", (c) => {
  const devices = Array.from(discoveredDevices.values());
  return c.json(devices);
});

app.post("/api/sync", async (c) => {
  const { rtp_ip, rtp_port } = await c.req.json();
  if (!rtp_ip || !rtp_port) {
    return c.json({ error: "Missing rtp_ip or rtp_port" }, 400);
  }
  const devices = Array.from(discoveredDevices.values());
  const updatePromises = devices.map(async (device) => {
    const deviceUrl = `http://${device.ip}:${device.port}`;
    try {
      const configRes = await fetch(`${deviceUrl}/api/config`);
      if (!configRes.ok) throw new Error("Failed to fetch config");
      const currentConfig = await configRes.json();
      currentConfig.rtp_midi_target_ip = rtp_ip;
      currentConfig.rtp_midi_target_port = rtp_port;
      const putRes = await fetch(`${deviceUrl}/api/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentConfig),
      });
      if (!putRes.ok) throw new Error("Failed to save config");
      await fetch(`${deviceUrl}/api/system/restart`, { method: "POST" });
      return { name: device.name, status: "success" };
    } catch (error) {
      console.error(`Failed to sync ${device.name}:`, error.message);
      return { name: device.name, status: "failure", reason: error.message };
    }
  });
  const results = await Promise.allSettled(updatePromises);
  return c.json(results);
});

// --- Static File Serving from Embedded Assets ---
app.get("/", (c) => {
  const htmlContent = Buffer.from(assets['index.html'], 'base64').toString('utf8');
  return c.html(htmlContent);
});

app.get("/style.css", (c) => {
  const cssContent = Buffer.from(assets['style.css'], 'base64').toString('utf8');
  return new Response(cssContent, {
    headers: { "Content-Type": "text/css" },
  });
});

app.get("/client.js", (c) => {
  const jsContent = Buffer.from(assets['client.js'], 'base64').toString('utf8');
  return new Response(jsContent, {
    headers: { "Content-Type": "application/javascript" },
  });
});

// --- Start the Server ---
const PORT = 8000;
console.log(`Fleet Manager server running at http://localhost:${PORT}`);

export default {
  port: PORT,
  fetch: app.fetch,
};

// Graceful shutdown for Bonjour
process.on("SIGINT", () => {
  console.log("Shutting down discovery...");
  browser.stop(() => {
    bj.destroy();
    process.exit();
  });
});