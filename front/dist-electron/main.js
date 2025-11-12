import { app, BrowserWindow, ipcMain } from "electron";
import path from "path";
import { fileURLToPath } from "url";
import { createRequire } from "module";
const require$1 = createRequire(import.meta.url);
const Database = require$1("better-sqlite3");
const __filename$1 = fileURLToPath(import.meta.url);
const __dirname$1 = path.dirname(__filename$1);
process.env["ELECTRON_DISABLE_SECURITY_WARNINGS"] = "true";
let mainWindow = null;
const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname$1, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    },
    backgroundColor: "#f3f4f6",
    show: false
  });
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname$1, "../dist/index.html"));
  }
  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
};
app.whenReady().then(() => {
  initializeDatabase();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
let db = null;
function initializeDatabase() {
  try {
    let dbPath;
    if (process.env.DB_PATH) {
      dbPath = process.env.DB_PATH;
    } else {
      const projectRoot = path.join(__dirname$1, "..", "..");
      dbPath = path.join(projectRoot, "data", "mcp_observer.db");
    }
    console.log(`[DB] Initializing database...`);
    console.log(`[DB] Database path: ${dbPath}`);
    console.log(`[DB] __dirname: ${__dirname$1}`);
    console.log(`[DB] app.getAppPath(): ${app.getAppPath()}`);
    db = new Database(dbPath, {
      readonly: true,
      fileMustExist: true,
      timeout: 5e3
    });
    console.log(`[DB] Database connection opened successfully`);
    db.pragma("query_only = ON");
    console.log(`[DB] Set query_only pragma`);
    const journalMode = db.pragma("journal_mode", { simple: true });
    console.log(`[DB] Journal mode: ${journalMode}`);
    const testQuery = db.prepare("SELECT COUNT(*) as count FROM sqlite_master");
    const testResult = testQuery.get();
    console.log(`[DB] Database schema tables count: ${testResult.count}`);
    console.log(`[DB] Database initialized successfully`);
    return true;
  } catch (error) {
    console.error(`[DB] Error setting up database:`, error.message);
    console.error(`[DB] Error stack:`, error.stack);
    return false;
  }
}
function getMcpServersFromDB() {
  console.log(`[DB] getMcpServersFromDB called`);
  if (!db) {
    console.error(`[DB] Database not initialized`);
    return [];
  }
  try {
    const query = `
      SELECT
        mcpTag,
        producer,
        tool,
        tool_title,
        tool_description,
        tool_parameter,
        annotations,
        created_at
      FROM mcpl
      ORDER BY mcpTag, created_at
    `;
    console.log(`[DB] Executing query: ${query.trim()}`);
    const rows = db.prepare(query).all();
    console.log(`[DB] Query returned ${rows.length} rows`);
    const serverMap = /* @__PURE__ */ new Map();
    rows.forEach((row) => {
      const serverName = row.mcpTag;
      if (!serverMap.has(serverName)) {
        serverMap.set(serverName, {
          id: serverMap.size + 1,
          name: serverName,
          type: row.producer || "local",
          icon: "🔧",
          tools: []
        });
        console.log(`[DB] Added new server: ${serverName}`);
      }
      const server = serverMap.get(serverName);
      server.tools.push({
        name: row.tool,
        description: row.tool_description || ""
      });
    });
    const servers = Array.from(serverMap.values());
    console.log(`[DB] Returning ${servers.length} servers`);
    servers.forEach((s) => console.log(`[DB]   - ${s.name}: ${s.tools.length} tools`));
    return servers;
  } catch (error) {
    console.error("[DB] Error fetching MCP servers from database:", error);
    return [];
  }
}
ipcMain.handle("api:servers", () => {
  console.log(`[IPC] api:servers called`);
  const servers = getMcpServersFromDB();
  console.log(`[IPC] api:servers returning ${servers.length} servers`);
  return servers;
});
ipcMain.handle("api:servers:messages", (_event, serverId) => {
  console.log(`[IPC] api:servers:messages called with serverId: ${serverId}`);
  if (!db) {
    console.error(`[DB] Database not initialized`);
    return [];
  }
  try {
    const mcpServers = getMcpServersFromDB();
    const server = mcpServers.find((s) => s.id === serverId);
    if (!server) {
      console.error(`[DB] Server with id ${serverId} not found`);
      throw new Error("Server not found");
    }
    console.log(`[DB] Found server: ${server.name}`);
    const query = `
      SELECT
        id,
        ts,
        producer,
        pid,
        pname,
        event_type,
        mcpTag,
        data,
        created_at
      FROM raw_events
      WHERE mcpTag = ? AND event_type = 'MCP'
      ORDER BY ts ASC
    `;
    console.log(`[DB] Executing query for mcpTag: ${server.name}`);
    const rows = db.prepare(query).all(server.name);
    console.log(`[DB] Query returned ${rows.length} messages`);
    const messages = rows.map((row) => {
      let parsedData = {};
      try {
        parsedData = typeof row.data === "string" ? JSON.parse(row.data) : row.data;
      } catch (e) {
        console.error(`[DB] Error parsing data for event ${row.id}:`, e);
        parsedData = { raw: row.data };
      }
      let messageType = row.event_type;
      if (parsedData.message && parsedData.message.method) {
        messageType = parsedData.message.method;
      }
      let sender = "unknown";
      if (parsedData.task === "SEND") {
        sender = "client";
      } else if (parsedData.task === "RECV") {
        sender = "server";
      }
      const maliciousScore = 0;
      let timestamp;
      try {
        if (row.ts > 1e15) {
          const tsInMs = Math.floor(row.ts / 1e6);
          timestamp = new Date(tsInMs).toISOString();
        } else if (row.ts > 1e12) {
          timestamp = new Date(row.ts).toISOString();
        } else {
          timestamp = new Date(row.ts * 1e3).toISOString();
        }
      } catch (e) {
        console.error(`[DB] Error converting timestamp for event ${row.id}, ts=${row.ts}:`, e);
        timestamp = (/* @__PURE__ */ new Date()).toISOString();
      }
      return {
        id: row.id,
        content: "",
        type: messageType,
        sender,
        timestamp,
        maliciousScore,
        data: {
          message: parsedData.message || parsedData
        }
      };
    });
    console.log(`[IPC] api:servers:messages returning ${messages.length} messages`);
    return messages;
  } catch (error) {
    console.error("[IPC] Error fetching messages:", error);
    return [];
  }
});
ipcMain.handle("api:engine-results", () => {
  console.log(`[IPC] api:engine-results called`);
  if (!db) {
    console.error(`[DB] Database not initialized`);
    return [];
  }
  try {
    const query = `
      SELECT
        er.id,
        er.engine_name,
        er.serverName,
        er.severity,
        er.score,
        er.detail,
        er.created_at,
        re.ts,
        re.event_type,
        re.data
      FROM engine_results er
      LEFT JOIN raw_events re ON er.raw_event_id = re.id
      ORDER BY er.created_at DESC
    `;
    console.log(`[DB] Executing query for engine results`);
    const results = db.prepare(query).all();
    console.log(`[DB] Query returned ${results.length} engine results`);
    console.log(`[IPC] api:engine-results returning ${results.length} results`);
    return results;
  } catch (error) {
    console.error("[IPC] Error fetching engine results:", error);
    return [];
  }
});
ipcMain.handle("ping", () => "pong");
ipcMain.handle("get-app-info", () => {
  return {
    version: app.getVersion(),
    name: app.getName(),
    platform: process.platform
  };
});
