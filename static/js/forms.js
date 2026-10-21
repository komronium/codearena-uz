// Form controls the browser draws in its own language: dates and times (the browser shows mm/dd/yyyy and 12-hour
// times) and file pickers ("Choose File / No file chosen"). Each native control stays in the form, hidden, and keeps
// its name and value; what people see and type is dd.mm.yyyy hh:mm, with quick buttons for the usual choices,
// and an "Fayl tanlash" button.
(() => {
  const pad = (n) => String(n).padStart(2, "0");
  const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const isoLocal = (d) => `${isoDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const show = (iso, withTime) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(iso || "");
    if (!m) return "";
    return withTime ? `${m[3]}.${m[2]}.${m[1]} ${m[4] || "00"}:${m[5] || "00"}` : `${m[3]}.${m[2]}.${m[1]}`;
  };
  const parse = (text, withTime) => {
    const m = /^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:[ T,]+(\d{1,2})[:.](\d{2}))?\s*$/.exec(text);
    if (!m) return null;
    const [, d, mo, y, h = "0", mi = "0"] = m;
    const date = new Date(+y, +mo - 1, +d, +h, +mi);
    if (date.getMonth() !== +mo - 1 || date.getDate() !== +d || +h > 23 || +mi > 59) return null;
    return withTime ? isoLocal(date) : isoDate(date);
  };

  const dateTime = (inp) => {
    const withTime = inp.type === "datetime-local";
    const wrap = document.createElement("div");
    wrap.className = "ca-dt";
    const row = document.createElement("div");
    row.className = "ca-dt-row";
    const text = document.createElement("input");
    text.type = "text"; text.inputMode = "numeric"; text.autocomplete = "off"; text.spellcheck = false;
    text.className = `${inp.className} ca-dt-text`.trim();
    text.placeholder = withTime ? "kk.oo.yyyy ss:dd" : "kk.oo.yyyy";
    text.value = show(inp.value, withTime);
    const label = inp.id && document.querySelector(`label[for="${inp.id}"]`);
    text.setAttribute("aria-label", (label ? label.textContent.trim() : inp.getAttribute("aria-label")) || (withTime ? "Sana va vaqt" : "Sana"));
    const pick = document.createElement("button");
    pick.type = "button"; pick.className = "ca-btn ca-btn-soft ca-dt-pick"; pick.title = caT("Kalendardan tanlash"); pick.setAttribute("aria-label", caT("Kalendardan tanlash"));
    pick.innerHTML = '<i data-lucide="calendar" class="lu" aria-hidden="true"></i>';
    row.append(text, pick);
    inp.before(wrap); wrap.append(row, inp);
    inp.classList.add("ca-dt-native"); inp.tabIndex = -1; inp.setAttribute("aria-hidden", "true");
    const required = inp.required; inp.required = false; text.required = required;

    const set = (iso, fromNative) => {
      inp.value = iso || "";
      if (!fromNative) text.value = show(iso, withTime);
      text.setCustomValidity("");
      if (inp.min && iso && iso < inp.min) text.setCustomValidity(caT("Sana {d} dan oldin bo‘lmasin").replace("{d}", show(inp.min, withTime)));
      if (inp.max && iso && iso > inp.max) text.setCustomValidity(caT("Sana {d} dan keyin bo‘lmasin").replace("{d}", show(inp.max, withTime)));
    };
    text.addEventListener("input", () => {
      const iso = parse(text.value, withTime);
      if (iso) set(iso, true);
      else { inp.value = ""; text.setCustomValidity(text.value.trim() ? caT("Sanani kk.oo.yyyy shaklida yozing") : ""); }
    });
    text.addEventListener("blur", () => { const iso = parse(text.value, withTime); if (iso) set(iso); });
    inp.addEventListener("change", () => { text.value = show(inp.value, withTime); set(inp.value, true); });
    pick.addEventListener("click", () => { try { inp.showPicker(); } catch { inp.focus(); } });

    const presets = withTime
      ? [[caT("Hozir"), () => new Date()], [caT("Bugun 23:59"), () => { const d = new Date(); d.setHours(23, 59, 0, 0); return d; }],
         [caT("+7 kun 23:59"), () => { const d = new Date(); d.setDate(d.getDate() + 7); d.setHours(23, 59, 0, 0); return d; }]]
      : [[caT("Bugun"), () => new Date()], [caT("Ertaga"), () => { const d = new Date(); d.setDate(d.getDate() + 1); return d; }]];
    const quick = document.createElement("div");
    quick.className = "ca-dt-quick";
    for (const [name, make] of presets) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = name;
      b.addEventListener("click", () => { const d = make(); set(withTime ? isoLocal(d) : isoDate(d)); text.focus(); });
      quick.append(b);
    }
    wrap.insertBefore(quick, inp);
  };

  const file = (inp) => {
    const wrap = document.createElement("label");
    wrap.className = "ca-file";
    const btn = document.createElement("span"); btn.className = "ca-btn ca-btn-soft ca-file-btn"; btn.textContent = caT("Fayl tanlash");
    const name = document.createElement("span"); name.className = "ca-file-name"; name.textContent = caT("Fayl tanlanmagan");
    inp.before(wrap); wrap.append(btn, name, inp);
    inp.classList.add("ca-file-native");
    inp.addEventListener("change", () => {
      const n = inp.files ? inp.files.length : 0;
      name.textContent = n === 0 ? caT("Fayl tanlanmagan") : n === 1 ? inp.files[0].name : caT("{n} ta fayl tanlandi").replace("{n}", n);
    });
  };

  // A multiple <select> ("hold Ctrl to pick several") becomes a searchable list of checkboxes with a count; the select stays
  // in the form, hidden, and carries the values.
  const multi = (sel) => {
    const wrap = document.createElement("div");
    wrap.className = "ca-multi";
    const q = document.createElement("input");
    q.type = "search"; q.className = "ca-input ca-multi-q"; q.placeholder = caT("Qidirish…"); q.autocomplete = "off"; q.spellcheck = false;
    q.setAttribute("aria-label", caT("Ro‘yxatdan qidirish"));
    const list = document.createElement("div");
    list.className = "ca-multi-list"; list.setAttribute("role", "group");
    const count = document.createElement("p");
    count.className = "ca-multi-n";
    const sync = () => { count.textContent = `${[...sel.options].filter((o) => o.selected).length} ta tanlandi`; };
    [...sel.options].forEach((o) => {
      if (!o.value) return;
      const row = document.createElement("label");
      row.className = "ca-multi-row"; row.dataset.text = o.textContent.toLowerCase();
      const box = document.createElement("input");
      box.type = "checkbox"; box.checked = o.selected;
      box.addEventListener("change", () => { o.selected = box.checked; sync(); });
      row.append(box, document.createTextNode(" " + o.textContent));
      list.append(row);
    });
    q.addEventListener("input", () => {
      const v = q.value.trim().toLowerCase();
      list.querySelectorAll(".ca-multi-row").forEach((r) => { r.hidden = v !== "" && !r.dataset.text.includes(v); });
    });
    q.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });
    sel.before(wrap); wrap.append(q, list, count, sel);
    sel.classList.add("ca-multi-native"); sel.tabIndex = -1; sel.setAttribute("aria-hidden", "true");
    sync();
  };

  const run = (root = document) => {
    root.querySelectorAll('input[type="datetime-local"], input[type="date"]').forEach((i) => { if (!i.closest(".ca-dt")) dateTime(i); });
    root.querySelectorAll('input[type="file"]:not(.sr-only)').forEach((i) => { if (!i.closest(".ca-file")) file(i); });
    root.querySelectorAll("select[multiple]").forEach((i) => { if (!i.closest(".ca-multi")) multi(i); });
    if (window.caIcons) window.caIcons();
  };
  run();
  document.addEventListener("htmx:afterSettle", (e) => run(e.target));
})();
