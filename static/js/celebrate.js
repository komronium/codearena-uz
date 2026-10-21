// A submission turning AC. While it is judged the card counts the tests one by one (1 / 50, 2 / 50 …) even when the
// poll brings several at once; when it turns AC the check mark draws, a short chord plays and, for the first accepted
// attempt at a problem only, a modest burst of confetti. Later accepts are quiet: the card and the chord. Fires only
// on the live change, never when an old accepted submission is merely opened. Motion is skipped for
// prefers-reduced-motion; the sound is off when localStorage "ca-sound" is "off" (the speaker button on the card).
(() => {
  const COLORS = ["#3B30C4", "#C81D5A", "#F2A900", "#087F5B", "#0A7A9A"];

  const muted = () => { try { return localStorage.getItem("ca-sound") === "off"; } catch { return false; } };
  let audio;

  // C major, rising: C5 E5 G5 C6, 70 ms apart. Sine with a quiet octave on top, a 10 ms attack and a soft tail, run
  // through a low-pass so nothing is shrill; about half a second in all, at a low level.
  function chime() {
    try {
      if (muted() || document.hidden) return;
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
      const t0 = audio.currentTime + 0.02, out = audio.createGain(), lp = audio.createBiquadFilter();
      out.gain.value = 0.11; lp.type = "lowpass"; lp.frequency.value = 3800;
      out.connect(lp).connect(audio.destination);
      [[523.25, 0], [659.25, 0.07], [783.99, 0.14], [1046.5, 0.21]].forEach(([freq, at], i, all) => {
        const last = i === all.length - 1, len = last ? 0.55 : 0.28;
        [[1, 1], [2, 0.18]].forEach(([mult, level]) => {
          const osc = audio.createOscillator(), g = audio.createGain();
          osc.type = "sine"; osc.frequency.value = freq * mult;
          g.gain.setValueAtTime(0.0001, t0 + at);
          g.gain.exponentialRampToValueAtTime(level, t0 + at + 0.01);
          g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + len);
          osc.connect(g).connect(out);
          osc.start(t0 + at); osc.stop(t0 + at + len + 0.05);
        });
      });
    } catch {}
  }

  // Confetti over the whole window, or (with `box`) only inside that element's rectangle: the accepted card keeps it
  // there so the editor and the buttons stay clear.
  function confetti(box) {
    const canvas = document.createElement("canvas"), r = box ? box.getBoundingClientRect() : null;
    canvas.setAttribute("aria-hidden", "true");
    canvas.style.cssText = (r ? `position:fixed;left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;`
      : "position:fixed;inset:0;width:100%;height:100%;")
      + "margin:0;padding:0;border:0;background:transparent;pointer-events:none;z-index:9999;max-width:none;max-height:none";
    document.body.appendChild(canvas);
    // Over an open modal dialog (the tier-up moment) a plain z-index can't win: the dialog sits
    // in the top layer. A manual popover joins the top layer after it, so it paints above.
    if (canvas.showPopover && document.querySelector("dialog[open]")) {
      canvas.popover = "manual";
      canvas.showPopover();
    }
    const dpr = window.devicePixelRatio || 1, g = canvas.getContext("2d");
    const W = (canvas.width = (r ? r.width : innerWidth) * dpr), H = (canvas.height = (r ? r.height : innerHeight) * dpr);
    const bits = Array.from({ length: r ? 60 : 90 }, () => ({
      x: Math.random() * W, y: -Math.random() * H * 0.5, w: (6 + Math.random() * 6) * dpr, h: (8 + Math.random() * 8) * dpr,
      vx: (Math.random() - 0.5) * 3 * dpr, vy: (r ? 1.6 + Math.random() * 2.6 : 2 + Math.random() * 4) * dpr, r: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3, c: COLORS[(Math.random() * COLORS.length) | 0],
    }));
    const t0 = performance.now();
    (function frame(t) {
      g.clearRect(0, 0, W, H);
      const fade = Math.max(0, 1 - (t - t0 - 1300) / 700);
      bits.forEach((b) => {
        b.x += b.vx; b.y += b.vy; b.vy += 0.06 * dpr; b.r += b.vr;
        g.save(); g.globalAlpha = fade; g.translate(b.x, b.y); g.rotate(b.r);
        g.fillStyle = b.c; g.fillRect(-b.w / 2, -b.h / 2, b.w, b.h); g.restore();
      });
      if (fade > 0) requestAnimationFrame(frame); else canvas.remove();
    })(t0);
  }

  // A round's accept: the problem's letter and what it earned, stamped over the middle of the page for about a second.
  function stamp({ label, points }) {
    const el = document.createElement("div");
    el.className = "ca-stamp";
    el.setAttribute("aria-hidden", "true");
    el.innerHTML = "<div><b></b><span></span></div>";
    el.querySelector("b").textContent = label;
    el.querySelector("span").textContent = points;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1300);
  }

  function toast(text) {
    const el = document.createElement("div");
    el.setAttribute("role", "status");
    el.className = "ca-ac-toast";
    el.textContent = text || caT("To‘g‘ri! Masala yechildi 🎉");
    document.body.appendChild(el);
    setTimeout(() => el.classList.add("is-out"), 2600);
    setTimeout(() => el.remove(), 3200);
  }

  // caCelebrate("text") or caCelebrate({ text, toast: false }) — no toast when a dialog already says it.
  window.caCelebrate = (opts = {}) => {
    const { text, toast: withToast = true } = typeof opts === "string" ? { text: opts } : opts;
    chime();
    if (withToast) toast(text);
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) confetti();
  };

  // The tests counted one at a time: `shown` keeps what each submission's card showed last; a poll that brings 19 more
  // runs the number up through every step (about 25 ms each, at most 0.9 s) and the bar with it. Returns how long it
  // takes so the celebration can wait for the last test.
  const shown = {};
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  function countUp(root) {
    let longest = 0;
    root.querySelectorAll(".ca7-cnt").forEach((el) => {
      const card = el.closest("[data-sub]"), id = card ? card.dataset.sub : "", to = +el.dataset.to;
      const from = Math.min(shown[id] || 0, to), bar = el.closest(".ca7-vhero")?.querySelector(".ca7-pg i");
      const total = Math.max(1, +el.dataset.total || to);
      shown[id] = to;
      if (from >= to || reduced()) { el.textContent = to; return; }
      const ms = Math.min(900, (to - from) * 25), t0 = performance.now();
      el.textContent = from;
      if (bar) { bar.style.transition = "none"; bar.style.width = (from / total * 100) + "%"; }
      longest = Math.max(longest, ms);
      (function step(t) {
        const n = Math.min(to, from + Math.floor((t - t0) / ms * (to - from)) + 1);
        el.textContent = n;
        if (bar) bar.style.width = (n / total * 100) + "%";
        if (n < to) requestAnimationFrame(step);
      })(t0);
    });
    return longest;
  }

  // caCelebrate("text") or caCelebrate({ text, toast: false, confetti: false }) — no toast when a dialog or the
  // result card already says it.
  window.caCelebrate = (opts = {}) => {
    const { text, toast: withToast = true, confetti: withConfetti = true } = typeof opts === "string" ? { text: opts } : opts;
    chime();
    if (withToast) toast(text);
    if (withConfetti && !reduced()) confetti();
  };

  // An accepted attempt: the chord always; for the first accept of a problem confetti inside the card; for a round's
  // accept the stamp. { first, stamp: { label, points } | null }
  window.caAccepted = ({ first = false, stamp: st = null } = {}) => {
    chime();
    if (reduced()) { if (st) stamp(st); return; }
    if (first && !st) {
      const card = document.querySelector(".ca7-vhero.is-ac");
      if (card) confetti(card);
    }
    if (st) stamp(st);
  };

  // The speaker button on an accepted card.
  const syncSound = (root) => root.querySelectorAll("[data-sound-toggle]").forEach((b) => {
    b.setAttribute("aria-pressed", muted() ? "false" : "true");
    b.querySelectorAll("[data-snd]").forEach((i) => i.toggleAttribute("hidden", (i.dataset.snd === "on") === muted()));
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-sound-toggle]");
    if (!b) return;
    try { localStorage.setItem("ca-sound", muted() ? "on" : "off"); } catch {}
    syncSound(document);
    if (!muted()) chime();
  });

  // htmx swaps the polled status block: count its tests up, and when it is the swap that turns a pending status into AC
  // celebrate once the count has reached the end.
  let accepted = null;
  document.addEventListener("htmx:beforeSwap", (e) => {
    const old = e.detail.target, was = old && old.dataset ? old.dataset.verdict : "";
    const html = e.detail.xhr.responseText || "";
    const mark = html.match(/data-stamp="([^"]*)" data-pts="([^"]*)"/);
    accepted = (was === "PENDING" || was === "RUNNING") && /data-verdict="AC"/.test(html)
      ? { first: /data-first="1"/.test(html), stamp: mark ? { label: mark[1], points: mark[2] } : null } : null;
  });
  document.addEventListener("htmx:afterSettle", () => {
    const wait = countUp(document);
    syncSound(document);
    if (accepted) {
      const done = accepted;
      accepted = null;
      setTimeout(() => window.caAccepted(done), wait + 150);
    }
  });
})();
