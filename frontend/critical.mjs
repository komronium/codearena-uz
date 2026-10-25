// Cuts static/css/app.css down to the rules a page really used (tools/critical_css.py measures that in a real
// browser and hands the start offsets of the used rules over), keeping the @media wrappers of what stays, the fonts
// of the families the page uses and the keyframes its rules name. The order is the stylesheet's own, so the
// cascade is the same as with the whole file.
//   node critical.mjs used.json out.css FAMILY...
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import postcss from "postcss";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [usedFile, outFile, ...families] = process.argv.slice(2);
const source = fs.readFileSync(path.join(HERE, "..", "static/css/app.css"), "utf8");
const used = new Set(JSON.parse(fs.readFileSync(usedFile, "utf8")));
const root = postcss.parse(source);

const keyframes = new Set();
const keep = (node) => {
  if (node.type === "rule") {
    if (!used.has(node.source.start.offset)) return false;
    node.walkDecls(/^animation(-name)?$/, (d) => d.value.split(/[\s,]+/).forEach((w) => keyframes.add(w)));
    return true;
  }
  if (node.type === "atrule" && node.name === "media") {
    node.each((child) => { if (!keep(child)) child.remove(); });
    return node.nodes.length > 0;
  }
  return false;
};

const kept = [];
root.each((node) => {
  if (node.type === "atrule" && node.name === "font-face") {
    let family = "";
    node.walkDecls("font-family", (d) => { family = d.value.replace(/["']/g, ""); });
    if (families.includes(family)) kept.push(node);
  } else if (node.type !== "atrule" || node.name === "media") {
    if (keep(node)) kept.push(node);
  }
});
// keyframes come after the rules that use them were found, but stay where the stylesheet has them
const out = [];
root.each((node) => {
  if (kept.includes(node)) out.push(node.toString());
  else if (node.type === "atrule" && node.name === "keyframes" && keyframes.has(node.params)) out.push(node.toString());
});
const hash = crypto.createHash("md5").update(source).digest("hex").slice(0, 12);
fs.writeFileSync(outFile, `/*app:${hash}*/` + out.join(""));
console.log(`${source.length} -> ${fs.statSync(outFile).size} bytes (app:${hash})`);
