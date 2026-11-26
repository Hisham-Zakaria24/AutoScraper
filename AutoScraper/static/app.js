// AutoScraper dashboard - made by Hisham-Zakaria
const $ = (s) => document.querySelector(s);
const form = $("#jobForm");
let jobs = [], currentId = null, page = 1, wasRunning = false, toastTimer;

function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text; // textContent: scraped data never becomes HTML
  if (cls) node.className = cls;
  return node;
}

function toast(message, isError) {
  const box = $("#toast");
  box.textContent = message;
  box.className = "show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.className = ""), 4000);
}

async function api(url, method = "GET", data) {
  const options = { method };
  if (method !== "GET") {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(data || {});
  }
  const res = await fetch(url, options);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || "Request failed: " + res.status);
  return json;
}

// Wrap event handlers so every error is shown to the user.
const safe = (fn) => async (...args) => {
  try { await fn(...args); } catch (e) { toast(e.message, true); }
};

function addField(name = "", selector = "") {
  const row = el("div", undefined, "field-row");
  const a = el("input"); a.placeholder = "Field name"; a.value = name; a.className = "f-name";
  const b = el("input"); b.placeholder = "CSS selector"; b.value = selector; b.className = "f-sel";
  const x = el("button", "✕", "danger"); x.type = "button"; x.title = "Remove field";
  x.onclick = () => row.remove();
  row.append(a, b, x);
  $("#fields").append(row);
}

function fillForm(job) {
  form.reset();
  $("#fields").replaceChildren();
  for (const key of ["name", "url", "item_selector", "next_selector", "max_pages", "delay", "interval_minutes"]) {
    if (job && job[key] !== undefined) form.elements[key].value = job[key];
  }
  form.elements.respect_robots.checked = job ? job.respect_robots !== false : true;
  Object.entries(job ? job.fields : { title: "" }).forEach(([n, s]) => addField(n, s));
  $("#previewCard").hidden = true;
}

function readForm() {
  const data = Object.fromEntries(new FormData(form));
  data.respect_robots = form.elements.respect_robots.checked;
  data.fields = {};
  for (const row of document.querySelectorAll(".field-row")) {
    const name = row.querySelector(".f-name").value.trim();
    if (name in data.fields) throw new Error("Field names unique hone chahiye");
    data.fields[name] = row.querySelector(".f-sel").value.trim();
  }
  return data;
}

function renderTable(table, headers, rows, emptyText) {
  table.replaceChildren();
  const head = el("tr");
  headers.forEach((h) => head.append(el("th", h)));
  table.append(head);
  if (!rows.length) {
    const tr = el("tr"), td = el("td", emptyText);
    td.colSpan = headers.length;
    tr.append(td);
    table.append(tr);
  }
  for (const cells of rows) {
    const tr = el("tr");
    for (const value of cells) {
      const td = el("td");
      if (value instanceof Node) td.append(value);
      else if (/^https?:\/\/\S+$/i.test(value)) {
        const link = el("a", value);
        link.href = value; link.target = "_blank"; link.rel = "noopener noreferrer";
        td.append(link);
      } else td.textContent = value;
      tr.append(td);
    }
    table.append(tr);
  }
}

const when = (t) => new Date(t * 1000).toLocaleString();

async function loadJobs() {
  jobs = await api("/api/jobs");
  $("#sJobs").textContent = jobs.length;
  $("#sItems").textContent = jobs.reduce((n, j) => n + j.total, 0);
  $("#sSched").textContent = jobs.filter((j) => j.interval_minutes).length;
  $("#sRun").textContent = jobs.filter((j) => j.running).length;
  const list = $("#jobList");
  list.replaceChildren();
  if (!jobs.length) list.append(el("li", "Abhi koi job nahi. Form bhar kar Save karein.", "hint"));
  for (const job of jobs) {
    const button = el("button", job.name, job.id === currentId ? "active" : "");
    const status = job.running ? "running" : job.last_status || "not run yet";
    const info = `${job.total} items · ${status}` + (job.interval_minutes ? ` · every ${job.interval_minutes}m` : "");
    button.append(el("small", info));
    button.onclick = safe(() => selectJob(job.id));
    const li = el("li");
    li.append(button);
    list.append(li);
  }
  const current = jobs.find((j) => j.id === currentId);
  $("#runBtn").disabled = !!current?.running;
  $("#runBtn").textContent = current?.running ? "Running..." : "▶ Run now";
}

async function loadData() {
  const id = currentId;
  if (!id) return;
  const q = encodeURIComponent($("#search").value);
  const [data, runs] = await Promise.all([
    api(`/api/jobs/${id}/items?page=${page}&q=${q}`),
    api(`/api/jobs/${id}/runs`),
  ]);
  if (id !== currentId) return; // user switched jobs meanwhile
  const pages = Math.max(1, Math.ceil(data.total / 25));
  if (page > pages) { page = pages; return loadData(); }
  renderTable($("#dataTable"), [...data.fields, "First seen"],
    data.rows.map((r) => [...data.fields.map((f) => r[f] ?? ""), when(r._first_seen)]),
    "Koi data nahi. 'Run now' dabayein.");
  $("#pageInfo").textContent = `Page ${page} / ${pages} · ${data.total} items`;
  $("#prev").disabled = page <= 1;
  $("#next").disabled = page >= pages;
  renderTable($("#runTable"), ["Started", "Status", "Pages", "Found", "New", "Message"],
    runs.map((r) => [when(r.started), el("span", r.status, r.status), r.pages, r.found, r.added, r.error]),
    "Abhi tak koi run nahi.");
}

async function selectJob(id) {
  currentId = id;
  page = 1;
  $("#search").value = "";
  await loadJobs();
  const job = jobs.find((j) => j.id === id);
  if (!job) return;
  fillForm(job);
  $("#formTitle").textContent = "Edit job";
  $("#detailName").textContent = job.name;
  $("#detail").hidden = false;
  document.querySelectorAll("[data-fmt]").forEach((a) => (a.href = `/api/jobs/${id}/export/${a.dataset.fmt}`));
  await loadData();
}

function newJob() {
  currentId = null;
  fillForm(null);
  $("#formTitle").textContent = "New job";
  $("#detail").hidden = true;
}

form.onsubmit = safe(async (event) => {
  event.preventDefault();
  const data = readForm();
  let id = currentId;
  if (id) await api(`/api/jobs/${id}`, "PUT", data);
  else id = (await api("/api/jobs", "POST", data)).id;
  toast("Job save ho gayi");
  await selectJob(id);
});

$("#previewBtn").onclick = safe(async () => {
  if (!form.reportValidity()) return;
  const button = $("#previewBtn");
  button.disabled = true;
  button.textContent = "Testing...";
  try {
    const result = await api("/api/preview", "POST", readForm());
    $("#previewCard").hidden = false;
    $("#previewTitle").textContent = `Preview: page 1 par ${result.count} items (max 10 dikh rahe hain)`;
    renderTable($("#previewTable"), result.fields,
      result.rows.map((r) => result.fields.map((f) => r[f])), "Kuch nahi mila. Selectors check karein.");
  } finally {
    button.disabled = false;
    button.textContent = "Test selectors";
  }
});

$("#exampleBtn").onclick = () => fillForm({
  name: "Quotes (practice site)", url: "https://quotes.toscrape.com/", item_selector: "div.quote",
  next_selector: "li.next a", max_pages: 3, delay: 1, interval_minutes: 0,
  fields: { quote: "span.text", author: "small.author", author_link: "span a@href" },
});
$("#newBtn").onclick = safe(async () => { newJob(); await loadJobs(); });
$("#addField").onclick = () => addField();
$("#runBtn").onclick = safe(async () => {
  await api(`/api/jobs/${currentId}/run`, "POST");
  wasRunning = true;
  toast("Scraping start ho gayi");
  await loadJobs();
});
$("#delBtn").onclick = safe(async () => {
  if (!confirm("Job aur uska sara data delete karein?")) return;
  await api(`/api/jobs/${currentId}`, "DELETE");
  newJob();
  await loadJobs();
});
$("#clearBtn").onclick = safe(async () => {
  if (!confirm("Is job ka sara saved data delete karein?")) return;
  await api(`/api/jobs/${currentId}/items`, "DELETE");
  await loadJobs();
  await loadData();
});
$("#prev").onclick = safe(async () => { page--; await loadData(); });
$("#next").onclick = safe(async () => { page++; await loadData(); });
$("#search").oninput = safe(async () => { page = 1; await loadData(); });

// Live status: refresh the list, and the data when a run is active or just ended.
let ticks = 0;
async function poll() {
  try {
    await loadJobs();
    const running = jobs.some((j) => j.running);
    if (running || wasRunning || ++ticks % 5 === 0) await loadData();
    wasRunning = running;
  } catch (e) { /* server stopped; try again */ }
  setTimeout(poll, 3000);
}

newJob();
poll();
