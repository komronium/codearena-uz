// Country -> city and country -> school pickers of the profile (the school list follows the country only: where
// one studies is not where one lives) (templates/accounts/_place_fields.html). The lists are in
// #places-data (apps/accounts/places.py). A country or city without a list shows a text box instead, and
// "Boshqa…" opens the same box, so nobody is stuck on a missing entry; the server accepts either.
(() => {
  const root = document.querySelector("[data-places]");
  const dataEl = document.getElementById("places-data");
  if (!root || !dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  const OTHER = data.other;
  const $ = (id) => document.getElementById(id);
  const country = $("id_country");
  const city = { select: $("id_location"), other: $("id_location_other") };
  const school = { select: $("id_school"), other: $("id_school_other") };

  const option = (value, text, disabled) => {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = text;
    if (disabled) o.disabled = true;
    return o;
  };

  // groups: [[heading|null, [name, ...]], ...]. `value`/`text` are what to show selected: a listed name, OTHER
  // with the typed text, or an unlisted old value (treated as typed text).
  function fill(box, groups, value, text, placeholder, otherLabel) {
    const names = groups.flatMap(([, list]) => list);
    const typed = value === OTHER ? text : names.includes(value) ? "" : value || text;
    box.select.replaceChildren();
    if (!names.length) {
      box.select.append(option(OTHER, otherLabel));
      box.select.value = OTHER;
      box.select.hidden = true;
      box.other.hidden = false;
      box.other.value = typed;
      return;
    }
    box.select.hidden = false;
    box.select.append(option("", placeholder));
    for (const [heading, list] of groups) {
      let parent = box.select;
      if (heading) {
        parent = document.createElement("optgroup");
        parent.label = heading;
        box.select.append(parent);
      }
      for (const name of list) parent.append(option(name, name));
    }
    box.select.append(option(OTHER, otherLabel));
    const other = value === OTHER || (!!value && !names.includes(value));
    box.select.value = other ? OTHER : value || "";
    box.other.hidden = !other;
    box.other.value = typed;
  }

  const cityGroups = () => data.cities[country.value] || [];
  function fillCity(value, text) {
    fill(city, cityGroups(), value, text, "Shaharni tanlang", "Boshqa shahar…");
  }

  function fillSchool(value, text) {
    if (!school.select) return;
    const groups = data.schools[country.value] || [];
    fill(school, groups, value, text, "O‘quv joyini tanlang", "Boshqa…");
  }

  const initial = (box) => [box.select.dataset.value || "", box.other.dataset.value || ""];
  fillCity(...initial(city));
  if (school.select) fillSchool(...initial(school));

  country.addEventListener("change", () => {
    fillCity("", "");
    fillSchool("", "");
  });
  city.select.addEventListener("change", () => {
    city.other.hidden = city.select.value !== OTHER;
    if (!city.other.hidden) city.other.focus();
  });
  if (school.select) {
    school.select.addEventListener("change", () => {
      school.other.hidden = school.select.value !== OTHER;
      if (!school.other.hidden) school.other.focus();
    });
  }
})();
