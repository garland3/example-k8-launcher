const $ = (sel) => document.querySelector(sel);

async function refreshRuns() {
  const tbody = $("#runs tbody");
  const r = await fetch("/api/runs");
  const rows = await r.json();
  tbody.innerHTML = "";
  for (const run of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${run.id}</td>
      <td>${run.agent_kind}</td>
      <td>${run.model}</td>
      <td>${run.namespace}</td>
      <td><span class="badge ${run.status}">${run.status}</span></td>
      <td>${new Date(run.created_at).toLocaleString()}</td>
    `;
    tr.addEventListener("click", () => (window.location = `/runs/${run.id}`));
    tbody.appendChild(tr);
  }
}

$("#launch-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  for (const k of ["namespace", "image"]) if (!body[k]) delete body[k];
  $("#launch-status").textContent = "launching…";
  const r = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    $("#launch-status").textContent = "error: " + (await r.text());
    return;
  }
  const { run_id } = await r.json();
  window.location = `/runs/${run_id}`;
});

$("#refresh").addEventListener("click", refreshRuns);
refreshRuns();
setInterval(refreshRuns, 5000);
