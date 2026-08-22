import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders LiveAgent Studio and all four agents", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>LiveAgent Studio · 直播智能工作台<\/title>/i);
  for (const label of ["主播发现", "直播拆解", "直播复盘", "视频编导"]) {
    assert.match(html, new RegExp(label));
  }
  assert.ok(html.indexOf("直播复盘") < html.indexOf("视频编导"));
  assert.doesNotMatch(html, /智能剪辑|ChatCut|Video Editor/);
});

test("keeps the video director workflow wired to real local endpoints", async () => {
  const [page, gateway, layout] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../local_gateway.py", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(page, /type View = .*"director"/);
  assert.match(page, /label="视频编导"/);
  assert.match(page, /\/api\/director\/sources/);
  assert.match(page, /\/api\/director\/douyin-login/);
  assert.match(page, /\/api\/director\/jobs/);
  assert.match(page, /每行一个链接或一整行抖音分享文案/);
  assert.match(page, /登录抖音/);
  assert.match(gateway, /if path == "\/api\/director\/sources"/);
  assert.match(gateway, /if path == "\/api\/director\/douyin-login"/);
  assert.match(gateway, /if path == "\/api\/director\/jobs"/);
  assert.match(gateway, /def extract_source_url/);
  assert.match(gateway, /def write_douyin_cookie_file/);
  assert.match(gateway, /def write_director_outputs/);
  assert.match(layout, /视频编导/);
});
