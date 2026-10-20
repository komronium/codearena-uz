// Small accessibility fixes that belong to no single page:
//  - a sorted column header says so (aria-sort), read from the visible arrow link
//  - a form that comes back with errors puts the cursor on the first wrong field
(() => {
  const ready = (fn) => (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", fn) : fn());
  ready(() => {
    document.querySelectorAll("th a.ca-sort-on").forEach((a) => {
      const th = a.closest("th");
      if (!th || th.hasAttribute("aria-sort")) return;
      th.setAttribute("aria-sort", /o‘sish/.test(a.textContent) ? "ascending" : "descending");
    });
    const bad = document.querySelector('form [aria-invalid="true"]');
    if (bad && (document.activeElement === document.body || !document.activeElement)) {
      bad.focus({ preventScroll: false });
    }
  });
})();
