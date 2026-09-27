// Command palette (Ctrl/⌘ K or "/"): pages, actions and an instant problem search in one list,
// grouped, arrow keys to move, Enter to open. Plus two-key shortcuts ("g p" → problems) and "?"
// for the list of them. The pages and actions come from base.html (#ca-palette-data), which knows
// the URLs and who is signed in; problems come from /problems/suggest/.
(() => {
  const dlg = document.getElementById("ca-palette");
  const input = document.getElementById("ca-palette-q");
  const list = document.getElementById("ca-palette-list");
  const keysDlg = document.getElementById("ca-keys");
  if (!dlg || !input || !list) return;
  let data = { items: [], suggest: "", all: "" };
  try { data = JSON.parse(document.getElementById("ca-palette-data").textContent); } catch {}

  // "o‘", "g‘", apostrophes and case don't matter: "ogil" finds "O‘g‘il", "reyt" finds "Reyting".
  const norm = (s) => (s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/[‘’ʻʼ'`]/g, "").replace(/\s+/g, " ").trim();
  const score = (item, q) => {
    if (!q) return item.quick ? 0 : 1;
    const hay = norm(item.label + " " + (item.words || ""));
    const label = norm(item.label);
    if (label.startsWith(q)) return 0;
    if (hay.split(" ").some((w) => w.startsWith(q))) return 1;
    if (hay.includes(q)) return 2;
    if (q.length < 3) return -1;
    let i = 0;  // letters in order, within the name only: "msl" → "masalalar"
    for (const ch of label) if (ch === q[i]) i++;
    return i === q.length ? 3 : -1;
  };

  let rows = [], active = 0, problems = [], lastQ = "", timer = null, ctrl = null;
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function render() {
    const q = norm(input.value);
    const local = data.items.map((it) => ({ it, s: score(it, q) })).filter((x) => x.s >= 0)
      .filter((x) => q || x.it.quick || x.it.group !== "Amallar")
      .sort((a, b) => a.s - b.s);
    // Order: quick picks, then whichever of pages/actions or problems matches better (a page whose
    // name starts with the query beats a title that merely contains it); "all problems" goes last.
    const groups = new Map();
    const add = (group, row) => { if (!groups.has(group)) groups.set(group, []); groups.get(group).push(row); };
    local.filter((x) => x.it.quick).slice(0, 4).forEach((x) => add("Tezkor", x.it));
    const pages = local.filter((x) => !x.it.quick).slice(0, q ? 8 : 12);
    const addPages = () => pages.forEach((x) => add(x.it.group, x.it));
    const addProblems = () => problems.forEach((p) => add("Masalalar", { label: p.title, url: p.url, icon: p.solved ? "circle-check" : "file-code-2",
      hint: `${p.difficulty_label} · #${String(p.id).padStart(4, "0")}`, level: p.difficulty, solved: p.solved }));
    const pagesFirst = !q || (pages.length && pages[0].s <= 1) || !problems.length;
    if (pagesFirst) { addPages(); addProblems(); } else { addProblems(); addPages(); }
    if (q) add("Masalalar", { label: `«${input.value.trim()}» bo‘yicha barcha masalalar`, url: `${data.all}?q=${encodeURIComponent(input.value.trim())}`, icon: "search" });

    rows = [];
    let html = "";
    for (const [group, items] of groups) {
      html += `<div class="ca-pal-group" role="presentation">${esc(group)}</div>`;
      for (const it of items) {
        const i = rows.push(it) - 1;
        html += `<a id="ca-pal-${i}" role="option" class="ca-pal-item${it.level ? " ca-pal-lvl-" + it.level : ""}" href="${esc(it.url || "#")}" data-i="${i}" aria-selected="false">`
          + `<i data-lucide="${esc(it.icon || "arrow-right")}" class="lu${it.solved ? " text-ok" : ""}" aria-hidden="true"></i>`
          + `<span class="ca-pal-label">${esc(it.label)}</span>`
          + (it.hint ? `<span class="ca-pal-hint">${esc(it.hint)}</span>` : "")
          + (it.keys ? `<kbd class="ca-kbd">${esc(it.keys)}</kbd>` : "") + "</a>";
      }
    }
    list.innerHTML = html || `<p class="ca-pal-empty">Hech narsa topilmadi. Boshqa so‘z bilan urinib ko‘ring.</p>`;
    window.caIcons?.();
    setActive(Math.min(active, rows.length - 1));
  }

  function setActive(i) {
    active = Math.max(0, i);
    list.querySelectorAll("[role=option]").forEach((el) => el.setAttribute("aria-selected", String(+el.dataset.i === active)));
    const el = document.getElementById(`ca-pal-${active}`);
    input.setAttribute("aria-activedescendant", el ? el.id : "");
    el?.scrollIntoView({ block: "nearest" });
  }

  function run(i) {
    const it = rows[i];
    if (!it) return;
    if (it.action === "keys") { dlg.close(); keysDlg?.showModal(); return; }
    if (it.action?.startsWith("theme:")) { window.caSetTheme?.(it.action.slice(6)); dlg.close(); return; }
    window.location.href = it.url;
  }

  function fetchProblems() {
    const q = input.value.trim();
    if (q === lastQ) return;
    lastQ = q;
    ctrl?.abort();
    if (!q) { problems = []; render(); return; }
    ctrl = new AbortController();
    fetch(`${data.suggest}?q=${encodeURIComponent(q)}`, { signal: ctrl.signal, headers: { Accept: "application/json" } })
      .then((r) => r.json()).then((j) => { problems = j.results || []; render(); }).catch(() => {});
  }

  input.addEventListener("input", () => {
    active = 0;
    render();
    clearTimeout(timer);
    timer = setTimeout(fetchProblems, 140);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((active + 1) % Math.max(rows.length, 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((active - 1 + rows.length) % Math.max(rows.length, 1)); }
    else if (e.key === "Enter") { e.preventDefault(); run(active); }
  });
  list.addEventListener("mousemove", (e) => { const a = e.target.closest("[data-i]"); if (a && +a.dataset.i !== active) setActive(+a.dataset.i); });
  list.addEventListener("click", (e) => {
    const a = e.target.closest("[data-i]");
    if (!a) return;
    const it = rows[+a.dataset.i];
    if (it?.action) { e.preventDefault(); run(+a.dataset.i); }
  });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });  // backdrop

  const open = () => {
    if (dlg.open) return;
    document.querySelectorAll("dialog[open]").forEach((d) => d.id !== "ca-tier-up" && d.close());
    input.value = ""; lastQ = ""; problems = []; active = 0;
    render();
    dlg.showModal();
    input.focus();
  };
  window.caPalette = open;
  document.querySelectorAll("[data-palette-open]").forEach((b) => b.addEventListener("click", open));

  // keyboard: Ctrl/⌘ K anywhere; "/", "?" and "g <key>" only when not typing
  const typing = (t) => t.closest?.("input, textarea, select, [contenteditable], .cm-editor");
  let g = 0;
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k") { e.preventDefault(); dlg.open ? dlg.close() : open(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target) || document.querySelector("dialog[open]")) return;
    if (e.key === "/") { e.preventDefault(); open(); return; }
    if (e.key === "?") { e.preventDefault(); keysDlg?.showModal(); return; }
    if (e.key === "g") { g = Date.now(); return; }
    if (Date.now() - g < 1200) {
      const it = data.items.find((x) => x.go === e.key.toLowerCase());
      g = 0;
      if (it) { e.preventDefault(); window.location.href = it.url; }
    }
  });
})();
