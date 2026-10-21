// One confirm dialog for every form that needs a "are you sure?" and one guard against double submits.
//   <form method="post" data-confirm="Rostdan ham?">                 asks first
//   <form ... data-confirm="..." data-reason="Sabab (ixtiyoriy):" data-reason-default="">   also asks for a
//                                                                     reason, written to the form's `reason` field
// Every other POST form that is not handled by htmx or by its own script has its button disabled once it goes out,
// so a double click sends one request (re-enabled when the page is shown again from the back button).
(() => {
  let dlg;
  const build = () => {
    dlg = document.createElement("dialog");
    dlg.className = "ca-dialog ca-confirm";
    dlg.setAttribute("aria-labelledby", "ca-confirm-msg");
    dlg.innerHTML = '<form method="dialog" class="ca-confirm-in">' +
      '<p id="ca-confirm-msg" class="ca-confirm-msg"></p>' +
      '<label class="ca-confirm-why" hidden><span></span><textarea rows="2" maxlength="200"></textarea></label>' +
      '<div class="ca-confirm-btns"><button value="no" class="ca-btn ca-btn-ghost">' + caT("Bekor qilish") + '</button>' +
      '<button value="yes" class="ca-btn ca-btn-primary">' + caT("Davom etish") + '</button></div></form>';
    document.body.appendChild(dlg);
  };

  const ask = (form, submitter) => {
    if (!dlg) build();
    const why = dlg.querySelector(".ca-confirm-why");
    const area = why.querySelector("textarea");
    dlg.querySelector(".ca-confirm-msg").textContent = form.dataset.confirm || form.dataset.reason;
    why.hidden = !("reason" in form.dataset);
    if (!why.hidden) {
      why.querySelector("span").textContent = caT("Sabab (ixtiyoriy)");
      area.value = form.dataset.reasonDefault || "";
    }
    dlg.returnValue = "";
    dlg.onclose = () => {
      if (dlg.returnValue !== "yes") return;
      if (!why.hidden && form.elements.reason) form.elements.reason.value = area.value;
      form.dataset.confirmed = "1";
      form.requestSubmit(submitter || undefined);
    };
    dlg.showModal();
    dlg.querySelector('button[value="yes"]').focus();
  };

  // for scripts: caConfirm("Kod o‘chiriladi. Davom etasizmi?").then((yes) => ...)
  window.caConfirm = (message) => new Promise((resolve) => {
    if (!dlg) build();
    const why = dlg.querySelector(".ca-confirm-why");
    why.hidden = true;
    dlg.querySelector(".ca-confirm-msg").textContent = message;
    dlg.returnValue = "";
    dlg.onclose = () => resolve(dlg.returnValue === "yes");
    dlg.showModal();
    dlg.querySelector('button[value="yes"]').focus();
  });

  document.addEventListener("submit", (e) => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement) || f.dataset.confirmed) return;
    if (f.dataset.confirm !== undefined || f.dataset.reason !== undefined) {
      e.preventDefault();
      ask(f, e.submitter);
    }
  }, true);

  document.addEventListener("submit", (e) => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement) || e.defaultPrevented || (f.method || "").toLowerCase() !== "post") return;
    if ([...f.attributes].some((a) => a.name.startsWith("hx-")) || f.hasAttribute("data-multi")) return;
    const btns = [...f.querySelectorAll('button:not([type="button"]), input[type="submit"]')];
    setTimeout(() => {  // after the browser has read the form, so the clicked button's value is still sent
      f.setAttribute("aria-busy", "true");
      btns.forEach((b) => { b.disabled = true; });
    }, 0);
  });

  window.addEventListener("pageshow", (e) => {
    if (!e.persisted) return;
    document.querySelectorAll('form[aria-busy="true"]').forEach((f) => {
      f.removeAttribute("aria-busy"); delete f.dataset.confirmed;
      f.querySelectorAll("button, input[type=submit]").forEach((b) => { b.disabled = false; });
    });
  });
})();
