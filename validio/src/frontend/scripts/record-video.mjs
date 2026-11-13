// The browser half of `make video` (scripts/record_video.py starts the server and calls this).
// A 1920x1080 stage in headless Firefox, recorded: the agent's terminal on the left third, the web app
// in a frame on the right two thirds, a phone frame for the approve page. The clicks follow
// tmp/pitch/video-script.md and docs/DEMO.md. Each shot is padded to its voice-over length from
// scripts/video_shots.json.
//
// Elements are found by data-testid (testids.md, lane K), then by the same element id the current pages
// have. A click the page cannot do yet (no approve code field) is done by API and listed as a fallback,
// so the scenes after it still see the state the demo has at that point. VIDEO_STRICT=1 makes a missing
// element or a fallback fail the run.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { firefox } from "@playwright/test";

const BASE = process.env.VIDEO_BASE;
const CODE = process.env.VIDEO_CODE;
const RAW = process.env.VIDEO_RAW;
const STRICT = process.env.VIDEO_STRICT === "1";
const { shots } = JSON.parse(readFileSync(process.env.VIDEO_SHOTS, "utf8"));
const W = 1920, H = 1080, TERM = 640;

const report = { testid: new Set(), id: new Set(), missing: new Set(), fallbacks: [], shots: [] };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);

const STAGE = `<!doctype html><html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; }
  body { margin: 0; width: ${W}px; height: ${H}px; overflow: hidden; display: flex; background: #1b1e26;
    font-family: "DejaVu Sans Mono", "Liberation Mono", monospace; }
  #term { width: ${TERM}px; height: ${H}px; display: flex; flex-direction: column; background: #161922;
    border-right: 1px solid #2d3142; color: #d6dae3; }
  #bar { padding: 14px 22px; font-size: 16px; color: #8a93a8; border-bottom: 1px solid #2d3142; }
  #bar b { color: #d6dae3; font-weight: 600; }
  #out { flex: 1; margin: 0; padding: 18px 22px; font-size: 18px; line-height: 1.38; white-space: pre-wrap;
    overflow-wrap: anywhere; overflow: hidden; }
  #out .cmd { color: #ffffff; } #out .agent { color: #7cc4e8; } #out .validio { color: #9fb7d9; }
  #out .kitchen { color: #ffffff; font-weight: 600; } #out .dim { color: #7d8597; } #out .ok { color: #9ad19a; }
  #right { width: ${W - TERM}px; height: ${H}px; position: relative; display: flex; align-items: center;
    justify-content: center; background: #1b1e26; }
  #app { width: ${W - TERM}px; height: ${H}px; border: 0; background: #fff; transition: none; }
  #right.phone #app { width: 390px; height: 844px; border-radius: 34px; box-shadow: 0 0 0 10px #0d0f14, 0 0 0 11px #3b4256; }
  #cursor { position: fixed; left: ${TERM + 640}px; top: 540px; width: 22px; height: 22px; margin: -11px 0 0 -11px;
    border-radius: 50%; background: rgba(47, 93, 138, 0.35); border: 2px solid #2f5d8a; z-index: 9;
    pointer-events: none; transition: left .55s ease, top .55s ease, transform .15s; }
  #cursor.down { transform: scale(.7); }
  #card { position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center;
    background: #161922; color: #d6dae3; font: 600 54px system-ui, sans-serif; }
</style></head><body>
  <div id="term"><div id="bar"><b>kitchen agent</b> &nbsp;terminal</div><pre id="out"></pre></div>
  <div id="right"><iframe id="app" name="app"></iframe></div>
  <div id="cursor"></div><div id="card">Validio</div>
<script>
  const out = document.getElementById("out");
  window.line = (html, cls) => {
    const d = document.createElement("div"); if (cls) d.className = cls; d.innerHTML = html || "&nbsp;";
    out.appendChild(d); while (out.scrollHeight > out.clientHeight && out.firstChild) out.removeChild(out.firstChild);
    return d;
  };
</script></body></html>`;

const browser = await firefox.launch({ headless: true });
mkdirSync(RAW, { recursive: true });
const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: RAW, size: { width: W, height: H } } });
const page = await ctx.newPage();
const recStart = Date.now();
await page.setContent(STAGE);
const frame = () => page.frame({ name: "app" });

async function api(path, init = {}) {
  const r = await fetch(BASE + path, init);
  if (!r.ok) throw new Error(`${init.method || "GET"} ${path} answered ${r.status}`);
  return r.json();
}
const chef = { method: "POST", headers: { "X-Approve-Code": CODE } };

async function settle() {
  await frame().waitForLoadState("networkidle").catch(() => {});
}
async function go(path) {
  await frame().goto(BASE + path, { waitUntil: "networkidle" });
}

// the element for a testid, or the element with that id on the current pages, or null
async function find(id, wait = 1500) {
  await settle();
  const sels = [["testid", `[data-testid="${id}"]`], ["id", `[id="${id}"]`]];
  await frame().locator(sels.map((s) => s[1]).join(", ")).first().waitFor({ timeout: wait }).catch(() => {});
  for (const [kind, sel] of sels) {
    const loc = frame().locator(sel).first();
    if ((await loc.count()) > 0) {
      report[kind].add(id);
      return loc;
    }
  }
  report.missing.add(id);
  if (STRICT) throw new Error(`no element ${id} on ${frame().url()}`);
  console.log(`  missing: ${id} on ${new URL(frame().url()).pathname}`);
  return null;
}

async function cursorTo(x, y) {
  await page.evaluate(([x, y]) => Object.assign(document.getElementById("cursor").style, { left: `${x}px`, top: `${y}px` }), [x, y]);
  await sleep(450);
}

// scroll the element into the middle, move the cursor onto it, hold
async function point(id, hold = 1.5) {
  const loc = await find(id);
  if (!loc) return null;
  await loc.evaluate((e) => e.scrollIntoView({ behavior: "smooth", block: "center" }));
  await sleep(450);
  const b = await loc.boundingBox();
  if (b) await cursorTo(b.x + Math.min(b.width / 2, 180), b.y + Math.min(b.height / 2, 28));
  await sleep(hold * 1000);
  return loc;
}

async function click(id, hold = 0.3) {
  const loc = await point(id, hold);
  if (!loc) return false;
  await page.evaluate(() => document.getElementById("cursor").classList.add("down"));
  await loc.click();
  await sleep(150);
  await page.evaluate(() => document.getElementById("cursor").classList.remove("down"));
  await settle();
  return true;
}

// a click that changes state: the page's button (with the approve code if it asks), else the API
async function act(id, done, fallback) {
  if (await click(id)) {
    const code = frame().locator('[data-testid="code-input"], [id="code-input"]').first();
    if (await code.isVisible({ timeout: 1500 }).catch(() => false)) {
      await code.pressSequentially(CODE, { delay: 90 });
      await click("code-submit");
    }
    await sleep(800);
    if (await done()) return;
  }
  report.fallbacks.push(id);
  if (STRICT) throw new Error(`${id}: the page could not do it`);
  console.log(`  fallback: ${id} done by API`);
  await fallback();
  if (!(await done())) throw new Error(`${id}: not done, not even by API`);
  await frame().goto(frame().url(), { waitUntil: "networkidle" });
}

function classOf(s) {
  if (s.startsWith("agent")) return "agent";
  if (s.startsWith("Validio <-")) return "validio";
  if (s.startsWith("kitchen")) return "kitchen";
  if (/^(model:|transcript:|Validio demo)/.test(s)) return "dim";
  return "";
}

// type the command into the terminal, run the real agent against this server, stream its lines
async function agent(n) {
  const cmd = `make agent SCENE=${n}`;
  await page.evaluate(() => { window.cur = window.line("$ ", "cmd"); });
  for (const ch of cmd) {
    await page.evaluate((c) => { window.cur.textContent += c; }, ch);
    await sleep(40);
  }
  await sleep(300);
  const lines = [];
  let closed = false;
  const p = spawn("uv", ["run", "python", "-W", "ignore", "../../scripts/agent.py", "--scene", String(n), "--base", BASE],
    { cwd: "../backend", env: process.env });
  let buf = "";
  p.stdout.on("data", (d) => { buf += d; const parts = buf.split("\n"); buf = parts.pop(); lines.push(...parts); });
  p.stderr.on("data", (d) => process.stderr.write(d));
  const exit = new Promise((r) => p.on("close", (code) => { closed = true; if (buf) lines.push(buf); r(code); }));
  while (!closed || lines.length) {
    if (!lines.length) { await sleep(50); continue; }
    const s = lines.shift();
    const cls = classOf(s);
    await page.evaluate(([h, c]) => window.line(h, c), [esc(s), cls]);
    await sleep(cls === "agent" || cls === "validio" || cls === "kitchen" ? 260 : 40);
  }
  const code = await exit;
  if (code !== 0) throw new Error(`make agent SCENE=${n} exited ${code}`);
  await page.evaluate(() => window.line(""));
}

async function phone(on) {
  await page.evaluate((on) => document.getElementById("right").classList.toggle("phone", on), on);
  await sleep(400);
}

const SCENES = {
  // Shot 1: the agent's request, then the Spend Pass card
  1: async () => {
    await agent(1);
    await settle();
    await point("inbox-R-1", 1);
    await point("spend-pass", 0.5);
    await point("pass-auto", 1.5);
    await point("pass-cap", 1.5);
  },
  // Shot 2: ordered alone, the ranking and the planted line
  2: async () => {
    await agent(2);
    await go("/");
    await click("inbox-R-1");
    await point("request-status", 1.5);
    await point("live-checked", 1.5);
    await point("option-464306", 2.5);
    await point("option-464401", 1.5);
    await point("option-462921", 2);
    await point("supplier-463047", 2.5);
    await point("reader-463047", 2.5);
  },
  // Shot 3: simulated stock-out, the swap waits, the owner approves on the phone
  3: async () => {
    await go("/");
    await act("stock-out", async () => (await api("/api/demo")).stockOut466375 === true,
      () => api("/api/demo/stock-out", { method: "POST" }));
    await point("stock-out-note", 1.5);
    await agent(3);
    await go("/");
    await click("inbox-R-2");
    for (const p of ["466151", "473986", "468526", "475908"]) await point(`option-${p}`, 0.9);
    await point("option-465256", 2.5);
    const order = (await api("/api/requests/R-2")).orderId;
    const opened = await click("open-approve");
    const at = new URL(frame().url()).pathname;
    if (!opened || (at !== `/approve/${order}` && !(await find("approve")))) {
      report.fallbacks.push(`open-approve (led to ${at})`);
      if (STRICT) throw new Error(`open-approve led to ${at}, not /approve/${order}`);
      console.log(`  fallback: open-approve led to ${at}, going to /approve/${order}`);
      await go(`/approve/${order}`);
    }
    await phone(true);
    await point("approve-question", 2.5);
    await act("approve", async () => (await api(`/api/orders/${order}`)).state === "placed",
      () => api(`/api/orders/${order}/approve`, chef));
    await point("order-steps", 3);
    await phone(false);
  },
  // Shot 4: the Steady Order renews, the parmesan splits, the pancakes wait, the mozzarella is flagged
  4: async () => {
    await go("/");
    if (!(await click("nav-steady-orders")) || !(await click("steady-S-1"))) await go("/steady/S-1");
    await point("simulated-history", 2);
    await act("renew", async () => !!(await api("/api/steady/S-1")).renewedAt,
      () => api("/api/steady/S-1/renew", chef));
    await point("line-464306", 2);
    await point("line-463968", 3);
    await point("line-471376", 2.5);
    await point("line-466375", 3);
    const accepted = async () => (await api("/api/steady/S-1")).lines.find((l) => l.productId === "471376").result === "accepted";
    await act("accept-471376", accepted, () => api("/api/steady/S-1/lines/471376/accept", chef));
    await point("line-471376", 1.5);
  },
  // Shot 5: the Open Ledger with its verified chain
  5: async () => {
    if (!(await click("nav-open-ledger"))) await go("/ledger");
    await point("chain-status", 2.5);
    const led = await find("ledger");
    if (led) {
      await cursorTo(TERM + 640, 900);
      for (let i = 0; i < 6; i++) {
        await frame().evaluate(() => window.scrollBy({ top: 260, behavior: "smooth" }));
        await sleep(1300);
      }
    }
  },
};

let failed = null;
try {
  await api("/api/demo/reset", { method: "POST" });
  await go("/");
  await sleep(1200);
  await page.evaluate(() => document.getElementById("card").remove());
  const t0 = Date.now();
  report.leadSeconds = (t0 - recStart) / 1000;
  for (const shot of shots) {
    const start = Date.now();
    await page.evaluate((s) => {
      document.getElementById("bar").innerHTML = `<b>kitchen agent</b> &nbsp;scene ${s.scene}, ${s.title}`;
    }, shot);
    console.log(`shot ${shot.scene} ${shot.title}`);
    await SCENES[shot.scene]();
    const used = (Date.now() - start) / 1000;
    const left = t0 + (shot.start + shot.seconds) * 1000 - Date.now();
    report.shots.push({ scene: shot.scene, planned: shot.seconds, used: Math.round(used * 10) / 10 });
    console.log(`  ${used.toFixed(1)} s of ${shot.seconds} s${left < 0 ? `, ${(-left / 1000).toFixed(1)} s over` : ""}`);
    if (left > 0) await sleep(left);
  }
  report.totalSeconds = (Date.now() - t0) / 1000;
} catch (e) {
  failed = e;
} finally {
  await ctx.close();
  await browser.close();
}

const summary = {
  leadSeconds: report.leadSeconds,
  totalSeconds: report.totalSeconds,
  shots: report.shots,
  byTestid: [...report.testid],
  byIdOnly: [...report.id].filter((i) => !report.testid.has(i)),
  missing: [...report.missing],
  fallbacks: report.fallbacks,
};
writeFileSync(`${RAW}/run.json`, JSON.stringify(summary, null, 2));
console.log(`found by data-testid: ${summary.byTestid.length}, by id only: ${summary.byIdOnly.length}, missing: ${summary.missing.join(", ") || "none"}`);
console.log(`fallbacks by API: ${summary.fallbacks.join(", ") || "none"}`);
if (failed) {
  console.error(failed);
  process.exit(1);
}
