// Contest times are Tashkent times (UTC+5). For a visitor whose own clock differs, the first <time class="ca-zt">
// of a run says so and adds their local time: "18:35 UTC+5 · sizda 13:35". Nothing changes for UTC+5 viewers.
(() => {
  const HOME = -300;  // Date#getTimezoneOffset() of UTC+5
  const here = (d) => new Date(d.getTime()).getTimezoneOffset();
  const stamp = (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  const run = () => {
    document.querySelectorAll("time.ca-zt:not([data-zt])").forEach((el) => {
      el.dataset.zt = "1";
      const d = new Date(el.getAttribute("datetime"));
      if (isNaN(d) || here(d) === HOME) return;
      const tag = document.createElement("span");
      tag.className = "ca-zt-note";
      tag.textContent = ` UTC+5 · sizda ${stamp(d)}`;
      el.after(tag);
    });
  };
  document.addEventListener("DOMContentLoaded", run);
  document.addEventListener("htmx:afterSwap", run);
})();
