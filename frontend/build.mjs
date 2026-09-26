// Builds CodeArena's static assets from the versions pinned in package.json. The outputs
// are committed, so the Django image never needs Node:
//   static/css/app.css         Tailwind (scans templates + apps) + src/app.css + @font-face
//   static/fonts/*.woff2       Inter, JetBrains Mono, Fira Code (SIL Open Font License)
//   static/vendor/*            htmx, Lucide icons, highlight.js
//   static/vendor/esm/*.js     one ES module per CodeMirror package; every bare import stays
//                              external and resolves through the import map, so each
//                              package loads once (two copies of @codemirror/state break it)
//   templates/_importmap.html  that import map, with {% static %} URLs (hashed in prod)
// `node build.mjs --check` builds into a temp dir and fails when a committed output is stale.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import * as esbuild from "esbuild";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const CHECK = process.argv.includes("--check");
const OUT = CHECK ? fs.mkdtempSync(path.join(os.tmpdir(), "ca-build-")) : ROOT;
const nm = (p) => path.join(HERE, "node_modules", p);
const out = (p) => {
  const f = path.join(OUT, p);
  fs.mkdirSync(path.dirname(f), { recursive: true });
  return f;
};

// Everything the editor imports, directly or through another package.
const ESM = [
  "codemirror", "@codemirror/state", "@codemirror/view", "@codemirror/language", "@codemirror/commands",
  "@codemirror/search", "@codemirror/autocomplete", "@codemirror/lint", "@codemirror/theme-one-dark",
  "@codemirror/lang-python", "@codemirror/lang-cpp", "@codemirror/lang-java", "@codemirror/lang-javascript",
  "@codemirror/lang-sql", "@lezer/common", "@lezer/highlight", "@lezer/lr", "@lezer/python", "@lezer/cpp",
  "@lezer/java", "@lezer/javascript", "style-mod", "w3c-keyname", "crelt", "@marijn/find-cluster-break",
  "@uiw/codemirror-themes", "@uiw/codemirror-theme-github", "@uiw/codemirror-theme-dracula",
  "@uiw/codemirror-theme-monokai", "@uiw/codemirror-theme-nord", "@uiw/codemirror-theme-solarized",
  "@uiw/codemirror-theme-vscode", "@uiw/codemirror-theme-tokyo-night", "@uiw/codemirror-theme-tokyo-night-storm",
  "@uiw/codemirror-theme-material", "@uiw/codemirror-theme-gruvbox-dark", "@uiw/codemirror-theme-atomone",
  "@uiw/codemirror-theme-xcode", "@uiw/codemirror-theme-aura", "@uiw/codemirror-theme-sublime",
  "@uiw/codemirror-theme-copilot", "@uiw/codemirror-theme-andromeda", "@replit/codemirror-vim",
  "@replit/codemirror-vim-core", "@babel/runtime/helpers/extends",
];
const version = (pkg) => JSON.parse(fs.readFileSync(nm(`${pkg}/package.json`), "utf8")).version;
const esmFile = (spec) => spec.replace(/^@/, "").replaceAll("/", "-") + ".js";

// [family we declare, fontsource stylesheets]; only these scripts' subsets are shipped,
// each fetched by the browser only when the page uses its characters (unicode-range).
const FONTS = [
  ["Inter", ["@fontsource-variable/inter/wght.css"]],
  ["JetBrains Mono", ["400", "400-italic", "500", "700"].map((w) => `@fontsource/jetbrains-mono/${w}.css`)],
  ["Fira Code", ["400", "500"].map((w) => `@fontsource/fira-code/${w}.css`)],
];
const SUBSETS = ["latin", "latin-ext", "cyrillic", "cyrillic-ext"];

const VENDOR = {
  "static/vendor/htmx.min.js": "htmx.org/dist/htmx.min.js",
  "static/vendor/highlight.min.js": "@highlightjs/cdn-assets/highlight.min.js",
  "static/vendor/highlight-github-dark.min.css": "@highlightjs/cdn-assets/styles/github-dark.min.css",
  // math in problem statements
  "static/vendor/katex/katex.min.js": "katex/dist/katex.min.js",
  "static/vendor/katex/katex.min.css": "katex/dist/katex.min.css",
  "static/vendor/katex/auto-render.min.js": "katex/dist/contrib/auto-render.min.js",
  // the staff Markdown editor and the icon font its toolbar uses
  "static/vendor/easymde/easymde.min.js": "easymde/dist/easymde.min.js",
  "static/vendor/easymde/easymde.min.css": "easymde/dist/easymde.min.css",
  "static/vendor/fontawesome/css/all.min.css": "@fortawesome/fontawesome-free/css/all.min.css",
};
// The .woff2 files those stylesheets use (their .woff/.ttf fallbacks are dropped below).
const VENDOR_FONTS = {
  "static/vendor/katex/fonts": "katex/dist/fonts",
  "static/vendor/fontawesome/webfonts": "@fortawesome/fontawesome-free/webfonts",
};
const LICENSED = [
  "htmx.org", "lucide", "@highlightjs/cdn-assets", "katex", "easymde", "@fortawesome/fontawesome-free",
  "tailwindcss", "@fontsource-variable/inter",
  "@fontsource/jetbrains-mono", "@fontsource/fira-code", "@babel/runtime",
  ...ESM.filter((s) => !s.startsWith("@babel/")),
];

// Source-map comments point at files we don't ship; Django's manifest storage fails
// collectstatic on a missing map.
// Every browser we support reads woff2; shipping only it keeps collectstatic from needing the rest.
const woff2Only = (css) => css.replace(/,\s*url\([^)]*\.(woff|ttf)\)\s*format\(["']?(woff|truetype)["']?\)/g, "");
const stripMaps = (text) => text.replace(/\n?\/\/# sourceMappingURL=\S+\s*$/m, "").replace(/\/\*# sourceMappingURL=\S+ \*\//g, "");

function fontFaces() {
  const faces = [];
  for (const [family, sheets] of FONTS) {
    for (const sheet of sheets) {
      const css = fs.readFileSync(nm(sheet), "utf8");
      for (const m of css.matchAll(/\/\* ([\w-]+) \*\/\s*@font-face \{([^}]*)\}/g)) {
        const [, name, body] = m;
        if (!SUBSETS.some((s) => new RegExp(`-${s}-(wght|\\d+)-`).test(name))) continue;
        const woff2 = body.match(/url\(\.\/files\/([^)]+\.woff2)\)/)[1];
        fs.copyFileSync(path.join(path.dirname(nm(sheet)), "files", woff2), out(`static/fonts/${woff2}`));
        const keep = body.split(";").map((d) => d.trim()).filter((d) => /^(font-style|font-weight|unicode-range)/.test(d));
        faces.push(`@font-face{font-family:"${family}";font-display:swap;${keep.join(";")};`
          + `src:url("../fonts/${woff2}") format("woff2")}`);
      }
    }
  }
  return faces.join("\n") + "\n";
}

// Lucide ships ~1,800 icons (440 KB); only the names the site uses are bundled. A name
// counts when it sits in a data-lucide attribute or is a quoted string in a template or
// Python file (icons chosen in JS or passed from views); extra matches are harmless.
function* lucideAttrValues(text) {
  // Attribute values may hold template tags with quotes of their own:
  // data-lucide="{% if dir == "asc" %}arrow-up{% else %}arrow-down{% endif %}"
  for (const m of text.matchAll(/data-lucide="/g)) {
    let i = m.index + m[0].length, depth = 0, value = "";
    for (; i < text.length; i++) {
      const two = text.slice(i, i + 2);
      if (two === "{%" || two === "{{") depth++;
      else if (two === "%}" || two === "}}") depth = Math.max(0, depth - 1);
      else if (text[i] === '"' && depth === 0) break;
      value += text[i];
    }
    yield value;
  }
}

async function lucideSubset() {
  // Exported names, aliases included ("history" has no file of its own), -> icon module
  const files = {};
  for (const m of fs.readFileSync(nm("lucide/dist/esm/iconsAndAliases.mjs"), "utf8")
    .matchAll(/export \{([^}]*)\} from '\.\/icons\/([\w-]+)\.mjs'/g)) {
    for (const name of m[1].matchAll(/default as (\w+)/g)) files[name[1]] = m[2];
  }
  const { toPascalCase } = await import(nm("lucide/dist/esm/shared/src/utils/toPascalCase.mjs"));
  const used = new Map();  // exported name -> icon file
  const consider = (word) => {
    const name = toPascalCase(word);
    if (files[name]) used.set(name, files[name]);
  };
  const sources = [...walk(path.join(ROOT, "templates")), ...walk(path.join(ROOT, "apps"))]
    .filter((f) => f.endsWith(".html") || f.endsWith(".py"));
  for (const f of sources) {
    const text = fs.readFileSync(f, "utf8");
    for (const value of lucideAttrValues(text)) for (const w of value.match(/[a-z][a-z0-9-]*/g) || []) consider(w);
    for (const m of text.matchAll(/["'`]([a-z][a-z0-9-]*)["'`]/g)) consider(m[1]);
  }
  const icons = [...used.keys()].sort();
  const dir = nm("lucide/dist/esm/icons");
  const contents = 'import { createIcons } from "lucide";\n'
    + icons.map((n, i) => `import i${i} from ${JSON.stringify(path.join(dir, used.get(n) + ".mjs"))};`).join("\n")
    + `\nconst icons = {${icons.map((n, i) => `${n}: i${i}`).join(",")}};\n`
    + "window.lucide = { createIcons: (options = {}) => createIcons({ ...options, icons }) };\n";
  await esbuild.build({
    stdin: { contents, resolveDir: HERE, loader: "js" }, bundle: true, format: "iife", platform: "browser",
    target: "es2020", minify: true, legalComments: "none", logLevel: "warning", outfile: out("static/vendor/lucide.min.js"),
    banner: { js: `/*! Lucide v${version("lucide")} (ISC), ${icons.length} icons; see THIRD-PARTY-LICENSES.txt */` },
  });
  return icons.length;
}

async function main() {
  // Tailwind: fonts first, then src/app.css (preflight, components, ca-* classes, utilities).
  const input = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "ca-css-")), "app.css");
  fs.writeFileSync(input, fontFaces() + fs.readFileSync(path.join(HERE, "src/app.css"), "utf8"));
  execFileSync(process.execPath, [nm("tailwindcss/lib/cli.js"), "-c", path.join(HERE, "tailwind.config.js"),
    "-i", input, "-o", out("static/css/app.css"), "--minify"],
  // its progress chatter goes to stderr; a failure still throws with the message
  { cwd: HERE, stdio: "pipe", env: { ...process.env, BROWSERSLIST_IGNORE_OLD_DATA: "1" } });

  for (const [dest, src] of Object.entries(VENDOR)) {
    const text = stripMaps(fs.readFileSync(nm(src), "utf8"));
    fs.writeFileSync(out(dest), dest.endsWith(".css") ? woff2Only(text) : text);
  }
  for (const [dest, src] of Object.entries(VENDOR_FONTS)) {
    for (const f of fs.readdirSync(nm(src)).filter((f) => f.endsWith(".woff2"))) {
      fs.copyFileSync(path.join(nm(src), f), out(`${dest}/${f}`));
    }
  }

  const nIcons = await lucideSubset();
  if (!CHECK) console.log(`lucide: ${nIcons} icons`);

  for (const spec of ESM) {
    const result = await esbuild.build({
      entryPoints: [spec], absWorkingDir: HERE, bundle: true, external: ESM.filter((s) => s !== spec),
      platform: "browser", format: "esm", target: "es2020", minify: true, legalComments: "eof",
      logLevel: "warning", metafile: true, outfile: out(`static/vendor/esm/${esmFile(spec)}`),
    });
    // A package inlined here that another module also imports would load twice.
    const own = nm(spec.split("/").slice(0, spec.startsWith("@") ? 2 : 1).join("/"));
    const foreign = Object.keys(result.metafile.inputs).map((i) => path.resolve(HERE, i)).filter((i) => !i.startsWith(own));
    if (foreign.length) console.warn(`${spec} inlines ${foreign.map((i) => path.relative(nm(""), i)).join(", ")}`);
  }
  const entries = ESM.map((s) => `    "${s}": "{% static 'vendor/esm/${esmFile(s)}' %}"`).join(",\n");
  fs.writeFileSync(out("templates/_importmap.html"),
    "{% load static %}{% comment %}Generated by frontend/build.mjs; edit the list there, then run "
    + "`npm run build` in frontend/.{% endcomment %}\n<script type=\"importmap\">\n{\n  \"imports\": {\n"
    + entries + "\n  }\n}\n</script>\n");

  const notices = LICENSED.map((pkg) => {
    const dir = nm(pkg.split("/").slice(0, pkg.startsWith("@") ? 2 : 1).join("/"));
    const file = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"].map((f) => path.join(dir, f)).find(fs.existsSync);
    const version = JSON.parse(fs.readFileSync(path.join(dir, "package.json"), "utf8")).version;
    return `==== ${pkg} ${version} ====\n\n${file ? fs.readFileSync(file, "utf8").trim() : "(see package)"}\n`;
  });
  fs.writeFileSync(out("static/vendor/THIRD-PARTY-LICENSES.txt"), notices.join("\n"));

  if (CHECK) check();
}

function* walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else yield p;
  }
}

function check() {
  const stale = [];
  const built = new Set();
  for (const f of walk(OUT)) {
    const rel = path.relative(OUT, f);
    built.add(rel);
    const committed = path.join(ROOT, rel);
    if (!fs.existsSync(committed) || !fs.readFileSync(committed).equals(fs.readFileSync(f))) stale.push(rel);
  }
  for (const dir of ["static/vendor", "static/fonts"]) {
    for (const f of walk(path.join(ROOT, dir))) {
      const rel = path.relative(ROOT, f);
      if (!built.has(rel)) stale.push(`${rel} (no longer built)`);
    }
  }
  fs.rmSync(OUT, { recursive: true, force: true });
  if (stale.length) {
    console.error("Stale front-end build; run `npm run build` in frontend/ and commit:\n  " + stale.join("\n  "));
    process.exit(1);
  }
  console.log("front-end build is up to date");
}

await main();
