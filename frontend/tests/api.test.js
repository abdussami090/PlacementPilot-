import test from "node:test";
import assert from "node:assert/strict";
import { apiRequest, apiBlobRequest } from "../src/api.js";

const originalFetch = globalThis.fetch;

test("apiRequest sends bearer token and JSON body", async () => {
  let capturedUrl;
  let capturedOptions;
  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    const result = await apiRequest("/health", {
      token: "test-token",
      method: "POST",
      body: { ready: true },
    });
    assert.deepEqual(result, { ok: true });
    assert.equal(capturedUrl, "/api/health");
    assert.equal(capturedOptions.headers.Authorization, "Bearer test-token");
    assert.equal(capturedOptions.headers["Content-Type"], "application/json");
    assert.equal(capturedOptions.body, JSON.stringify({ ready: true }));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("apiRequest exposes HTTP status and API detail on errors", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Admin access required" }), {
    status: 403,
    headers: { "content-type": "application/json" },
  });

  try {
    await assert.rejects(
      apiRequest("/admin-test"),
      (error) => error.status === 403 && error.message === "Admin access required",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("apiBlobRequest returns a downloaded PDF blob", async () => {
  globalThis.fetch = async () => new Response(new Blob(["%PDF-test"], { type: "application/pdf" }), {
    status: 200,
    headers: { "content-type": "application/pdf" },
  });

  try {
    const blob = await apiBlobRequest("/resume/download", { token: "test-token" });
    assert.equal(blob.type, "application/pdf");
    assert.equal(await blob.text(), "%PDF-test");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
