"use strict";

const assert = require("node:assert/strict");
const { Readable } = require("node:stream");
const { test } = require("node:test");
const FC = require("@alicloud/fc20230330");
const CAS = require("@alicloud/cas20200407");

process.env.CERT_GENERATOR_FUNCTION_NAME = "cert-generator-test";
process.env.CUSTOM_DOMAIN_REGIONS = "cn-hangzhou";
const { handler } = require("../index");
const context = {
  accountId: "123456", region: "cn-hangzhou",
  credentials: { accessKeyId: "test-key", accessKeySecret: "test-secret", securityToken: "token" },
};

function mockWorkflow(t, domains, { fail = false, response = "123" } = {}) {
  const calls = { invocations: [], updates: [], details: [] };
  t.mock.method(FC.default.prototype, "listCustomDomainsWithOptions", async () => ({
    body: { customDomains: domains },
  }));
  t.mock.method(FC.default.prototype, "invokeFunctionWithOptions", async (name, request) => {
    let contents = "";
    for await (const chunk of request.body) contents += chunk;
    calls.invocations.push({ name, event: JSON.parse(contents) });
    return {
      headers: fail ? { "x-fc-error-type": "UnhandledInvocationError" } : {},
      body: Readable.from([Buffer.from(response)]),
    };
  });
  t.mock.method(CAS.default.prototype, "getUserCertificateDetailWithOptions", async (request) => {
    calls.details.push(request);
    return { body: { cert: "new-chain", key: "new-private-key" } };
  });
  t.mock.method(FC.default.prototype, "updateCustomDomainWithOptions", async (name, request) => {
    calls.updates.push({ name, request });
    return {};
  });
  return calls;
}

test("renews a wildcard certificate even with one bound custom domain", async (t) => {
  const certName = "devs-certbot-generated-w-3-abcdefgh";
  const calls = mockWorkflow(t, [{
    domainName: "app.example.com", protocol: "HTTP,HTTPS",
    certConfig: { certName, certificate: "old-chain" },
  }], { response: '"123"' });
  let completed = false;
  await handler(null, context, (error, result) => {
    assert.equal(error, null);
    assert.equal(result, "done");
    completed = true;
  });
  assert.equal(completed, true);
  assert.deepEqual(calls.invocations, [{
    name: "cert-generator-test", event: { certName, domainName: "*.example.com" },
  }]);
  assert.equal(calls.details[0].certId, "123");
  assert.equal(calls.updates[0].request.body.certConfig.certificate, "new-chain");
  assert.equal(calls.updates[0].request.body.certConfig.privateKey, "new-private-key");
});

test("ignores domains without managed HTTPS certificate configuration", async (t) => {
  const calls = mockWorkflow(t, [
    { domainName: "http.example.com", protocol: "HTTP" },
    { domainName: "missing.example.com", protocol: "HTTPS" },
    { domainName: "other.example.com", protocol: "HTTPS", certConfig: { certName: "manual" } },
  ]);
  await handler(null, context, () => {});
  assert.equal(calls.invocations.length, 0);
});

test("reuses current certificate without updating the custom domain", async (t) => {
  const calls = mockWorkflow(t, [{
    domainName: "app.example.com", protocol: "HTTPS",
    certConfig: { certName: "devs-certbot-generated-test", certificate: "new-chain" },
  }]);
  await handler(null, context, () => {});
  assert.equal(calls.invocations[0].event.domainName, "app.example.com");
  assert.equal(calls.updates.length, 0);
});

test("failed certificate invocation never changes domain configuration", async (t) => {
  const calls = mockWorkflow(t, [{
    domainName: "app.example.com", protocol: "HTTPS",
    certConfig: { certName: "devs-certbot-generated-test", certificate: "old-chain" },
  }], { fail: true });
  await assert.rejects(handler(null, context, () => {}), /Failed to check cert/);
  assert.equal(calls.details.length, 0);
  assert.equal(calls.updates.length, 0);
});

test("invalid certificate id never reaches CAS or domain updates", async (t) => {
  const calls = mockWorkflow(t, [{
    domainName: "app.example.com", protocol: "HTTPS",
    certConfig: { certName: "devs-certbot-generated-test", certificate: "old-chain" },
  }], { response: '{"error":"failed"}' });
  await assert.rejects(handler(null, context, () => {}), /Failed to find cert/);
  assert.equal(calls.details.length, 0);
  assert.equal(calls.updates.length, 0);
});
