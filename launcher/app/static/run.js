const runId = Number(window.location.pathname.split("/").pop());
const $ = (sel) => document.querySelector(sel);

let lastEventId = 0;
let runStatus = "pending";

async function loadRun() {
  const r = await fetch(`/api/runs/${runId}`);
  if (!r.ok) return;
  const run = await r.json();
  runStatus = run.status;
  $("#run-id").textContent = "#" + run.id;
  const status = $("#run-status");
  status.textContent = run.status;
  status.className = "badge " + run.status;

  $("#run-meta").innerHTML = `
    <dt>kind</dt><dd>${run.agent_kind}</dd>
    <dt>model</dt><dd>${run.model}</dd>
    <dt>namespace</dt><dd>${run.namespace}</dd>
    <dt>image</dt><dd><code>${run.image}</code></dd>
    <dt>job</dt><dd><code>${run.job_name || "—"}</code></dd>
    <dt>created</dt><dd>${new Date(run.created_at).toLocaleString()}</dd>
  `;
  $("#run-prompt").textContent = run.prompt;
}

function renderEvent(ev) {
  const div = document.createElement("div");
  div.className = "event " + ev.kind;
  const ts = new Date(ev.ts).toLocaleTimeString();
  let body;
  if (typeof ev.payload === "object") {
    if (ev.kind === "stdout" || ev.kind === "stderr") {
      body = ev.payload.line || JSON.stringify(ev.payload);
    } else if (ev.kind === "tool") {
      const args = ev.payload.args ? " " + JSON.stringify(ev.payload.args) : "";
      body = (ev.payload.name || "tool") + args;
    } else {
      body = JSON.stringify(ev.payload);
    }
  } else {
    body = String(ev.payload);
  }
  div.innerHTML = `<span class="kind">${ev.kind} ${ts}</span>${escapeHtml(body)}`;
  return div;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function pollEvents() {
  const r = await fetch(`/api/runs/${runId}/events?after=${lastEventId}`);
  if (!r.ok) return;
  const events = await r.json();
  const container = $("#events");
  for (const ev of events) {
    container.appendChild(renderEvent(ev));
    lastEventId = ev.id;
  }
  if (events.length) window.scrollTo(0, document.body.scrollHeight);
}

async function tick() {
  await loadRun();
  await pollEvents();
  if (["succeeded", "failed", "gone"].includes(runStatus)) {
    setTimeout(tick, 5000);
  } else {
    setTimeout(tick, 1000);
  }
}

tick();
