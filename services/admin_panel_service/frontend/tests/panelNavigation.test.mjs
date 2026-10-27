import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

// Reuse the project's TypeScript compiler, without adding a test framework.
const source = await readFile(new URL("../src/lib/panelNavigation.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { activeNavigationItem, panelSectionUrl, isEducationPath } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const items = [{ id: "client-search" }, { id: "leadreport" }, { id: "education" }];

test("section URL restores selected report after reload", () => {
  const url = new URL(panelSectionUrl("leadreport"), "https://example.org");
  assert.equal(url.search, "?section=leadreport");
  assert.equal(activeNavigationItem(items, url.pathname, url.search).id, "leadreport");
});

test("back/forward selection depends only on current URL, not old state", () => {
  for (const section of ["leadreport", "client-search", "leadreport"]) {
    assert.equal(activeNavigationItem(items, "/admin-panel", `?section=${section}`).id, section);
  }
});

test("education and nested routes override stale query parameters", () => {
  assert.equal(panelSectionUrl("education"), "/admin-panel/education");
  for (const path of ["/admin-panel/education", "/admin-panel/education/trainees/42"]) {
    assert.equal(activeNavigationItem(items, path, "?section=client-search").id, "education");
  }
  assert.equal(isEducationPath("/admin-panel/education-other"), false);
});

test("unknown or forbidden section falls back to first permitted embedded item", () => {
  for (const query of ["", "?section=unknown", "?section=education"]) {
    assert.equal(activeNavigationItem(items, "/admin-panel", query).id, "client-search");
  }
  const permitted = [{ id: "urlshorter" }];
  assert.equal(activeNavigationItem(permitted, "/admin-panel", "?section=leadreport").id, "urlshorter");
  assert.equal(activeNavigationItem(permitted, "/admin-panel/education", ""), undefined);
});

test("no module opens before user permissions are loaded", () => {
  assert.equal(activeNavigationItem([], "/admin-panel", "?section=leadreport"), undefined);
});
