// A submission turning AC: confetti in the Xon-atlas colours, a short two-note chime and a toast.
// Fires only on the live change (a polled "Tekshirilmoqda" status swapped for an AC one), never
// when an old accepted submission is merely opened. Motion is skipped for prefers-reduced-motion;
// the chime is skipped when localStorage "ca-sound" is "off".
(() => {
  const COLORS = ["#3B30C4", "#C81D5A", "#F2A900", "#087F5B", "#0A7A9A"];

  function chime() {
    try {
      if (localStorage.getItem("ca-sound") === "off") return;
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [[660, 0], [990, 0.12]].forEach(([freq, at]) => {
        const osc = ctx.createOscillator(), gain = ctx.createGain();
        osc.type = "sine"; osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + at);
        gain.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + at + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + at + 0.35);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + at); osc.stop(ctx.currentTime + at + 0.4);
      });
      setTimeout(() => ctx.close(), 1000);
    } catch {}
  }

  function confetti() {
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    canvas.style.cssText = "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:9999";
    document.body.appendChild(canvas);
    const dpr = window.devicePixelRatio || 1, g = canvas.getContext("2d");
    const W = (canvas.width = innerWidth * dpr), H = (canvas.height = innerHeight * dpr);
    const bits = Array.from({ length: 160 }, () => ({
      x: Math.random() * W, y: -Math.random() * H * 0.5, w: (6 + Math.random() * 6) * dpr, h: (8 + Math.random() * 8) * dpr,
      vx: (Math.random() - 0.5) * 3 * dpr, vy: (2 + Math.random() * 4) * dpr, r: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3, c: COLORS[(Math.random() * COLORS.length) | 0],
    }));
    const t0 = performance.now();
    (function frame(t) {
      g.clearRect(0, 0, W, H);
      const fade = Math.max(0, 1 - (t - t0 - 2200) / 800);
      bits.forEach((b) => {
        b.x += b.vx; b.y += b.vy; b.vy += 0.06 * dpr; b.r += b.vr;
        g.save(); g.globalAlpha = fade; g.translate(b.x, b.y); g.rotate(b.r);
        g.fillStyle = b.c; g.fillRect(-b.w / 2, -b.h / 2, b.w, b.h); g.restore();
      });
      if (fade > 0) requestAnimationFrame(frame); else canvas.remove();
    })(t0);
  }

  function toast(text) {
    const el = document.createElement("div");
    el.setAttribute("role", "status");
    el.className = "ca-ac-toast";
    el.textContent = text || "To‘g‘ri! Masala yechildi 🎉";
    document.body.appendChild(el);
    setTimeout(() => el.classList.add("is-out"), 2600);
    setTimeout(() => el.remove(), 3200);
  }

  window.caCelebrate = (text) => {
    chime();
    toast(text);
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) confetti();
  };

  // htmx swaps the polled status block; celebrate the one swap that turns a pending status into AC.
  document.addEventListener("htmx:beforeSwap", (e) => {
    const old = e.detail.target;
    const was = old && old.dataset ? old.dataset.verdict : "";
    if ((was === "PENDING" || was === "RUNNING") && /data-verdict="AC"/.test(e.detail.xhr.responseText || "")) {
      setTimeout(() => window.caCelebrate(), 60);
    }
  });
})();
