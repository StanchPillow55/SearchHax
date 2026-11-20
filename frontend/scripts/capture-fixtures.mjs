#!/usr/bin/env node
// Capture REAL read-only responses from a running exploration API as test fixtures.
// Usage: node scripts/capture-fixtures.mjs http://127.0.0.1:8010 inv_a inv_b ...
// Only GET requests are made. Nothing is created, stepped, or searched.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const [, , base, ...ids] = process.argv;
if (!base || !ids.length) {
  console.error("usage: capture-fixtures.mjs <api-base> <investigation-id>...");
  process.exit(2);
}
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "test", "fixtures");
for (const id of ids) {
  const dir = join(out, id);
  mkdirSync(dir, { recursive: true });
  for (const [name, path] of [
    ["export", ""],
    ["trace", "/trace"],
    ["branches", "/branches"],
  ]) {
    const url = `${base}/api/exploration/investigations/${id}${path}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
    writeFileSync(join(dir, `${name}.json`), JSON.stringify(await res.json()));
    console.log(`captured ${id}/${name}.json`);
  }
}
writeFileSync(
  join(out, "SOURCE.md"),
  `Real responses captured with GET requests from a local exploration API (${new Date().toISOString().slice(0, 10)}).\n` +
    `Investigations: ${ids.join(", ")}.\nRegenerate with scripts/capture-fixtures.mjs. Do not hand-edit.\n`,
);
