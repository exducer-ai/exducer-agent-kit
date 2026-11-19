// Verify the signature of a webhook delivery, in Node.js (no dependency).
//
// Every POST carries `X-Webhook-Signature: t=<unix seconds>,v1=<hex>`, where v1 is HMAC-SHA256 with
// your endpoint's secret over the string "<t>." followed by the raw request body, exactly as received.
//
// The `verify` function is the one on https://exducer.ai/docs/compute/c-webhooks.
// Run this file to see it accept a correctly signed body and refuse a changed one:
//
//     node examples/webhooks/verify.mjs
import { createHmac, timingSafeEqual } from "node:crypto";
import { pathToFileURL } from "node:url";

export function verify(secret, header, rawBody, tolerance = 300) {
  const parts = Object.fromEntries(header.split(",").map((p) => p.split("=", 2)));
  const t = Number(parts.t);
  if (!Number.isFinite(t) || Math.abs(Date.now() / 1000 - t) > tolerance) return false;
  const expected = createHmac("sha256", secret).update(`${t}.`).update(rawBody).digest("hex");
  const given = Buffer.from(parts.v1 ?? "", "hex");
  return given.length === 32 && timingSafeEqual(Buffer.from(expected, "hex"), given);
}

// Express: app.post("/hooks", express.raw({ type: "application/json" }), (req, res) => {
//   if (!verify(SECRET, req.get("X-Webhook-Signature"), req.body)) return res.sendStatus(400);
//   res.sendStatus(204); // answer fast; do the work after
// });

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  // A made-up secret and body, signed here the way the service signs a delivery.
  const secret = "whsec_example_only";
  const body = Buffer.from('{"type":"deployment.state_changed","sandbox":true}');
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", secret).update(`${t}.`).update(body).digest("hex");
  const header = `t=${t},v1=${v1}`;

  const checks = [
    [verify(secret, header, body) === true, "a correctly signed body must pass"],
    [verify(secret, header, Buffer.concat([body, Buffer.from(" ")])) === false, "a changed body must fail"],
    [verify("another secret", header, body) === false, "another secret must fail"],
    [verify(secret, `t=${t - 3600},v1=${v1}`, body) === false, "an old timestamp must fail"],
  ];
  for (const [ok, what] of checks) if (!ok) throw new Error(what);
  console.log("ok: signed body accepted; changed body, wrong secret and old timestamp refused");
}
