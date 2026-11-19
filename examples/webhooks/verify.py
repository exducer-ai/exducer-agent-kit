#!/usr/bin/env python3
"""Verify the signature of a webhook delivery.

Every POST carries `X-Webhook-Signature: t=<unix seconds>,v1=<hex>`, where v1 is HMAC-SHA256 with
your endpoint's secret over the string "<t>." followed by the raw request body, exactly as received.

The `verify` function is the one on https://exducer.ai/docs/compute/c-webhooks.
Run this file to see it accept a correctly signed body and refuse a changed one:

    python3 examples/webhooks/verify.py
"""
import hashlib
import hmac
import time


def verify(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    t = int(parts["t"])
    if abs(time.time() - t) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])


# Flask, FastAPI, Django: pass the raw body, never a re-serialised JSON object
# ok = verify(SECRET, request.headers["X-Webhook-Signature"], request.get_data())


if __name__ == "__main__":
    # A made-up secret and body, signed here the way the service signs a delivery.
    secret = "whsec_example_only"
    body = b'{"type":"deployment.state_changed","sandbox":true}'
    t = int(time.time())
    v1 = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={t},v1={v1}"

    assert verify(secret, header, body), "a correctly signed body must pass"
    assert not verify(secret, header, body + b" "), "a changed body must fail"
    assert not verify("another secret", header, body), "another secret must fail"
    assert not verify(secret, f"t={t - 3600},v1={v1}", body), "an old timestamp must fail"
    print("ok: signed body accepted; changed body, wrong secret and old timestamp refused")
