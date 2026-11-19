#!/usr/bin/env python3
"""turbo — command-line client for the ExducerAI cloud (cloud.exducer.ai).

Single file, Python 3.9+, standard library only. Install:
    curl -sSL https://exducer.ai/cli/install.sh | sh

Auth: an API key from the console (Account -> API keys), stored by
`turbo login` in ~/.config/turbo/config.json, or TURBO_API_KEY in the
environment. TURBO_API overrides the API base (default https://api.exducer.ai).
The key's scope decides what it may do: a read key lists (deployments, billing,
keys); `book`, `stop` and `chat` need a write key; `ssh-keys add/remove` and
`storage create/revoke` change credentials and need an admin key (or the console).

Every rental is reached over SSH, so a request needs an SSH public key:
`turbo book --ssh-key ~/.ssh/id_ed25519.pub`, or one saved with `turbo ssh-keys add`.
`turbo templates` lists the images a rental can run; ask us for another.
A sandbox key (tml_test_…) runs the same commands against the simulated lifecycle:
`turbo deployments` marks those rows and `turbo ssh` refuses them (no SSH endpoint
exists in sandbox mode). `turbo book --idempotency-key K` makes a retry safe.

For scripts and coding agents: every command takes --json; `book`, `extend` and `stop`
ask before they spend or delete and exit 2 when nobody can answer (pass --yes);
`turbo wait ID` blocks until a deployment runs; `turbo ssh ID --batch -- CMD` never
prompts and checks the host key against the fingerprint the API publishes;
`turbo mcp` serves the MCP tools over stdio; `turbo agent setup` installs the agent
skills and registers the MCP server for the coding agents on this machine.
Exit codes: 0 done, 1 error, 2 confirmation needed, 3 and 4 from `turbo wait`.
"""
import argparse, base64, hashlib, json, os, shutil, sys, subprocess, time, urllib.request, urllib.error, getpass, datetime

VERSION = "0.3.0"
DEFAULT_API = "https://api.exducer.ai"
SITE_BASE = "https://exducer.ai"   # public, read-only site endpoints (availability)
CONF = os.path.expanduser("~/.config/turbo/config.json")


def load_conf():
    try:
        with open(CONF) as f:
            return json.load(f)
    except Exception:
        return {}


def save_conf(c):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    with open(CONF, "w") as f:
        json.dump(c, f, indent=2)
    os.chmod(CONF, 0o600)


def api_base():
    return os.environ.get("TURBO_API") or load_conf().get("api") or DEFAULT_API


def api_key():
    return os.environ.get("TURBO_API_KEY") or load_conf().get("key") or ""


def site_base():
    """The public site of the brand the API belongs to (api.<brand> -> <brand>); TURBO_SITE overrides."""
    if os.environ.get("TURBO_SITE"):
        return os.environ["TURBO_SITE"].rstrip("/")
    base = api_base().rstrip("/")
    return base.replace("://api.", "://", 1) if "://api." in base else (SITE_BASE if base == DEFAULT_API else base)


def is_sandbox_key():
    return api_key().startswith("tml_test_")


REPLAYED = False     # the last answer was the stored answer to an earlier use of the same Idempotency-Key


def call(method, path, body=None, auth=True, base=None, extra_headers=None):
    global REPLAYED
    url = (base or api_base()).rstrip("/") + path
    headers = {"Accept": "application/json", "User-Agent": f"turbo-cli/{VERSION}"}
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if auth:
        k = api_key()
        if not k:
            die("no API key: run `turbo login` (Account -> API keys on the console) or set TURBO_API_KEY")
        headers["Authorization"] = "Bearer " + k
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            REPLAYED = (r.headers.get("Idempotent-Replayed") or "").lower() == "true"
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail")
        except Exception:
            detail = e.reason
        if e.code == 401:
            die("not authenticated — the API key is missing, revoked, or for another environment (run `turbo login`)")
        if e.code == 403 and isinstance(detail, dict) and detail.get("code") == "api_key_scope":
            # The API enforces key scopes: read < write < admin (credentials need admin).
            need = detail.get("required") or "write"
            die(f"{detail.get('message') or 'this API key cannot make this request'}\n"
                f"  create a key with the {need} scope on the console (Account -> API keys) and run "
                f"`turbo login` with it" + (", or make this change on the console" if need == "admin" else ""))
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("code") or json.dumps(detail)
        die(f"HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        die(f"cannot reach {url}: {e.reason}")


def contact():
    """The support address of the brand the API belongs to (api.<brand> -> hello@<brand>)."""
    host = api_base().split("://", 1)[-1].split("/", 1)[0]
    return "hello@" + (host[4:] if host.startswith("api.") else host)


# The key types the GPU coordinator takes (the backend's start_checks.KEY_TYPES).
KEY_TYPES = ("ssh-ed25519", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
             "sk-ssh-ed25519@openssh.com", "sk-ecdsa-sha2-nistp256@openssh.com", "ssh-rsa")
KEY_RULE = "use an ed25519 or ECDSA key, a security key (sk-...), or RSA of at least 3072 bits"


def _rsa_bits(blob):
    """Bit length of the modulus in an ssh-rsa key blob (string type, mpint e, mpint n)."""
    i, parts = 0, []
    for _ in range(3):
        n = int.from_bytes(blob[i:i + 4], "big"); parts.append(blob[i + 4:i + 4 + n]); i += 4 + n
    return int.from_bytes(parts[2], "big").bit_length()


def read_pubkey(path):
    """The public key line(s) in `path`, checked the way the API checks them, or exit with why."""
    try:
        with open(os.path.expanduser(path)) as f:
            text = f.read().strip()
    except OSError as e:
        die(f"cannot read {path}: {e.strerror}")
    if "PRIVATE KEY" in text:
        die(f"{path} is a private key: pass the public key, the .pub file next to it")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        die(f"{path} is empty: pass your SSH public key (.pub)")
    for ln in lines:
        kind, _, rest = ln.partition(" ")
        if kind not in KEY_TYPES:
            die(f"{path}: key type {kind[:40]!r} is not accepted; {KEY_RULE}")
        if kind == "ssh-rsa":
            try:
                bits = _rsa_bits(base64.b64decode(rest.split()[0]))
            except Exception:
                die(f"{path}: not a valid OpenSSH public key")
            if bits < 3072:
                die(f"{path}: this RSA key has {bits} bits; {KEY_RULE}")
    return "\n".join(lines)


def die(msg, code=1):
    print(f"turbo: {msg}", file=sys.stderr)
    sys.exit(code)


def say(*lines):
    """Progress for a person. With --json it goes to stderr, so stdout stays one JSON document."""
    for ln in lines:
        print(ln, file=sys.stderr if ARGS.json else sys.stdout)


def confirm(question, yes):
    """True when the action may go ahead. --yes answers for a script; otherwise a person is asked,
    and when nobody can answer (no input: a script, a coding agent) the command exits 2."""
    if yes:
        return True
    stream = sys.stderr if ARGS.json else sys.stdout      # with --json, stdout is for the answer only
    stream.write(question)
    stream.flush()
    line = sys.stdin.readline()
    if not line:                                           # end of input: nobody is there
        stream.write("\n")
        die("nobody answered the confirmation: pass --yes once the action is approved", 2)
    return line.strip().lower() == "y"


def out(obj, rows=None, cols=None):
    """--json prints the raw object; otherwise a plain table."""
    if ARGS.json:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
        return
    if rows is None:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
        return
    if not rows:
        print("(none)")
        return
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
    print("  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def money(v):
    # Every amount the API returns is in the console's billing currency, CAD (fields named *Usd /
    # *_usd are legacy names and carry CAD).
    return "—" if v is None else f"CA${float(v):,.2f}"


def when(iso):
    if not iso:
        return "—"
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def left(iso):
    if not iso:
        return "—"
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        s = (d - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        if s <= 0:
            return "expired"
        h, m = int(s // 3600), int(s % 3600 // 60)
        return f"{h}h {m:02d}m"
    except Exception:
        return "—"


# ---------------------------------------------------------------- commands
def cmd_login(a):
    key = a.api_key or getpass.getpass("API key (tml_…): ").strip()
    if not key.startswith("tml_"):
        die("that does not look like a ExducerAI API key (expected tml_…)")
    conf = load_conf()
    conf["key"] = key
    if a.api:
        conf["api"] = a.api
    save_conf(conf)
    me = call("GET", "/api/account")
    if ARGS.json:
        return out({"email": me.get("email"), "api": api_base(), "sandbox_key": key.startswith("tml_test_"), "config": CONF})
    print(f"logged in as {me.get('email')} ({api_base()}) — key saved to {CONF}"
          + (" — sandbox key: everything is simulated" if key.startswith("tml_test_") else ""))


def cmd_logout(a):
    conf = load_conf(); conf.pop("key", None); save_conf(conf); print("key removed")


def cmd_whoami(a):
    me = call("GET", "/api/account")
    bal = call("GET", "/api/billing/credits/balance")
    out({**me, "balance": bal, "currency": "CAD", "sandbox_key": is_sandbox_key(), "api": api_base()}, rows=[[me.get("email"), me.get("company"), me.get("accountType"), money(bal.get("balanceUsd")), "on" if me.get("twoFactorEnabled") else "off", api_base()]],
        cols=["email", "company", "type", "prepaid credit", "2fa", "api"])


def cmd_availability(a):
    # Availability, not fleet size: one yes/no per GPU model. Reads the site's public shape
    # ({"skus": [{"available": bool}]}) and, from an API host that still sends the older per-node
    # shape, reduces it the same way ("sold_out" = no free GPU).
    d = call("GET", "/api/v1/public/availability", auth=False, base=SITE_BASE)
    skus = d.get("skus")
    if skus is None:
        skus = [{"sku": x.get("sku"), "gpu_model": x.get("gpu_model"), "location": x.get("location"), "available": x.get("status") != "sold_out"}
                for x in d.get("available", []) if x.get("status") in ("available", "limited", "sold_out")]
    rows = [[x.get("sku"), x.get("gpu_model"), x.get("location"), "yes" if x.get("available") else "no"] for x in skus]
    out({"generated_at": d.get("generated_at"), "skus": skus}, rows, ["sku", "gpu", "region", "available now"])


def cmd_servers(a):
    d = call("GET", "/api/servers")
    # Availability is one boolean per server (`available`); the server rows carry no GPU counts.
    rows = [[s["id"], s.get("displayName") or s.get("name"), s.get("gpuModel"), ("yes" if s.get("available") else "no") if "available" in s else "—", money(s.get("pricePerGpuHour")) + "/GPU·h", s.get("location") or "CA-QC"] for s in (d if isinstance(d, list) else d.get("servers", []))]
    out(d, rows, ["server", "name", "gpu", "free now", "on-demand", "region"])


def cmd_templates(a):
    # The API lists only templates whose image runs today, plus "Bring your own image"
    # (no image of its own: --image, which takes only an image that runs).
    d = call("GET", "/api/v1/templates", auth=False)
    items = d if isinstance(d, list) else d.get("templates", [])
    if a.category:
        items = [t for t in items if a.category.lower() in str(t.get("category_slug", "")).lower()]
    rows = [[t["slug"], t.get("name"), t.get("category_slug", ""), t.get("default_volume_gb"), (t.get("image") or "your --image")[:48]] for t in items]
    out(d, rows, ["slug", "name", "category", "vol GB", "image"])
    if not ARGS.json and items:
        print(f"\nEvery rental is reached over SSH. Need another image? Email {contact()} and we add it.")


def cmd_deployments(a):
    d = call("GET", "/api/v1/deployments")
    # `status` is the state (phase); provisioning_state is the older, finer-grained column.
    rows = [[x["id"], "sandbox" if x.get("sandbox") else "live", x.get("template_slug") or (x.get("image") or "")[:24], x["gpu_count"],
             x.get("status") or x.get("provisioning_state"), money(x.get("hourly_rate_usd")), money(x.get("accrued_cost_usd")),
             when(x.get("ends_at")), left(x.get("ends_at")) if (x.get("status") or x.get("provisioning_state")) == "running" else "—"] for x in d]
    out(d, rows, ["id", "mode", "template", "gpus", "state", "rate", "accrued", "ends", "left"])


def cmd_deployment(a):
    d = call("GET", f"/api/v1/deployments/{a.id}")
    if ARGS.json:
        return out(d)
    for k in ("id", "label", "sku", "gpu_count", "template_slug", "image", "status", "phase", "state_reason", "provisioning_state",
              "provisioning_progress_pct", "started_at", "ends_at", "currency", "hourly_rate_usd", "accrued_cost_usd",
              "billing_ended_at", "ssh_host", "ssh_port", "sandbox"):
        print(f"{k:26s} {d.get(k)}")
    for ep in d.get("http_endpoints") or []:
        print(f"{'endpoint':26s} {ep.get('name')}: {ep.get('url')}")
    fp = ((d.get("access") or {}).get("ssh") or {}).get("host_key_fingerprint")
    if fp:
        print(f"{'host key':26s} {fp}")
    if d.get("sandbox"):
        print(f"{'note':26s} sandbox deployment: simulated, nothing is charged, no SSH endpoint exists")
    elif d.get("ssh_host") and d.get("ssh_port"):
        print(f"{'ssh':26s} ssh -p {d['ssh_port']} root@{d['ssh_host']}")


def cmd_events(a):
    d = call("GET", f"/api/v1/deployments/{a.id}/events")
    out(d, [[when(e.get("at")), e.get("from_state") or "—", e.get("to_state"), e.get("reason") or "", e.get("actor") or "", e.get("message") or ""] for e in d],
        ["at", "from", "to", "reason", "actor", "message"])


def cmd_stop(a):
    # POST /api/rentals/{id}/stop withdraws a request (requested -> cancelled, our team
    # is told), releases a queued rental and stops a running one on its host: the
    # container and its NVMe scratch disk are deleted. DELETE /api/v1/deployments/{id}
    # now does the same stop (it used to only mark the deployment). Both need a write key.
    if not a.yes:
        r = call("GET", f"/api/rentals/{a.id}")
        if r.get("status") == "requested":
            q = f"withdraw request {a.id}? nothing has been charged [y/N] "
        elif r.get("status") == "queued":
            q = f"stop rental {a.id} before it starts? nothing has been charged for it [y/N] "
        else:
            q = (f"stop deployment {a.id}? billing ends now, and its container and NVMe scratch disk "
                 f"are deleted and cannot be recovered (copy your data off first) [y/N] ")
        if not confirm(q, False):
            return
    out(call("POST", f"/api/rentals/{a.id}/stop"))


def cmd_extend(a):
    # POST /api/v1/deployments/{id}/extend: the same rental, node and connection details run longer;
    # billing stays per minute, so stopping early still costs nothing extra. 720 h ahead at most.
    if not confirm(f"extend deployment {a.id} by {a.hours} h? billing continues per minute until the new end [y/N] ", a.yes):
        return
    d = call("POST", f"/api/v1/deployments/{a.id}/extend", {"hours": a.hours},
             extra_headers={"Idempotency-Key": a.idempotency_key} if a.idempotency_key else None)
    if ARGS.json:
        out(d)
        return
    if REPLAYED:
        print(f"already extended with this idempotency key: nothing was added again; {d.get('id')} ends {when(d.get('ends_at'))}")
        return
    print(f"extended {d.get('id')} by {a.hours} h: ends {when(d.get('ends_at'))} ({d.get('duration_hours')} h in all); state {d.get('status')}")


def cmd_renew(a):
    # PATCH /api/v1/deployments/{id}: the term renews itself at its end (30 days at a time unless --hours)
    # while prepaid credit covers an hour of the node; off, it ends at ends_at as booked.
    body = {"auto_renew": a.state == "on"}
    if a.state == "on" and a.hours:
        body["renew_hours"] = a.hours
    d = call("PATCH", f"/api/v1/deployments/{a.id}", body)
    if ARGS.json:
        out(d)
        return
    if d.get("auto_renew"):
        print(f"{d.get('id')}: renews itself every {d.get('renew_hours')} h at the end of its term while credit lasts "
              f"(current term ends {when(d.get('ends_at'))}); turn off with: turbo renew {a.id} off")
    else:
        print(f"{d.get('id')}: automatic renewal off; it ends {when(d.get('ends_at'))} (extend with: turbo extend {a.id} --hours N)")


def pinned_known_hosts(d):
    """(path, None) of a known_hosts file that holds only the host keys of this deployment whose
    SHA256 fingerprint is the one the API publishes, or (None, why). A key that answers on the
    port but has another fingerprint is never written: "mismatch" means do not connect."""
    want = ((d.get("access") or {}).get("ssh") or {}).get("host_key_fingerprint")
    if not want:
        return None, "the API publishes no host key fingerprint for this deployment"
    try:
        scan = subprocess.run(["ssh-keyscan", "-T", "10", "-p", str(d["ssh_port"]), d["ssh_host"]],
                              capture_output=True, text=True, timeout=40).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, "ssh-keyscan is missing or did not answer"
    seen, good = 0, []
    for line in scan.splitlines():
        parts = line.split()
        if line.startswith("#") or len(parts) < 3:
            continue
        try:
            fp = "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(parts[2])).digest()).decode().rstrip("=")
        except Exception:
            continue
        seen += 1
        if fp == want:
            good.append(line)
    if not good:
        return None, ("mismatch" if seen else "the host did not present a key")
    folder = os.path.join(os.path.dirname(CONF), "known_hosts")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "".join(c for c in str(d.get("id")) if c.isalnum() or c in "_-"))
    with open(path, "w") as f:
        f.write("\n".join(good) + "\n")
    return path, None


def cmd_ssh(a):
    d = call("GET", f"/api/v1/deployments/{a.id}")
    if d.get("sandbox"):
        die(f"deployment {a.id} is a sandbox deployment: no SSH endpoint exists in sandbox mode")
    if not d.get("ssh_host") or not d.get("ssh_port"):
        die(f"deployment {a.id} is {d.get('status') or d.get('provisioning_state')} — no SSH endpoint yet")
    # argparse hands everything after the id to `rest`, options included: take --batch back out,
    # then drop the "--" that separates the remote command.
    rest, batch = list(a.rest), a.batch
    while rest[:1] == ["--batch"]:
        batch, rest = True, rest[1:]
    if rest[:1] == ["--"]:
        rest = rest[1:]
    opts = []
    known, why = pinned_known_hosts(d)
    if why == "mismatch":
        die(f"the host key at {d['ssh_host']}:{d['ssh_port']} does not match the fingerprint the API publishes for "
            f"{a.id}: not connecting. Write to {contact()}.")
    if known:
        # Only the verified key is trusted for this connection: no trust-on-first-use prompt.
        opts += ["-o", f"UserKnownHostsFile={known}", "-o", "StrictHostKeyChecking=yes"]
    elif batch:
        die(f"cannot verify the host key of {a.id} ({why}); --batch connects only to a verified host")
    else:
        print(f"turbo: host key not verified ({why}); ssh asks you to check it", file=sys.stderr)
    if batch:
        opts += ["-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
    cmd = ["ssh", *opts, "-p", str(d["ssh_port"]), f"root@{d['ssh_host']}"] + rest
    os.execvp("ssh", cmd)


def book_body(a):
    return {"serverId": a.server, "gpus": a.gpus, "pricing": "ondemand", "durationHours": a.hours, "storageGb": getattr(a, "volume", None) or 0}


def cmd_quote(a):
    # POST /api/bookings/preview: the price of a booking, tax included. No key, nothing is booked.
    q = call("POST", "/api/bookings/preview", book_body(a), auth=False)
    if ARGS.json:
        return out(q)
    print(f"{q.get('serverName')} · {a.gpus} × GPU · {a.hours} h")
    print(f"GPU {money(q.get('gpuCost'))}  storage {money(q.get('storageCost'))}  tax {money(q.get('tax'))}  total {money(q.get('total'))}")
    print("a quote books nothing; send the request with: turbo book (same options)")


WAIT_FINAL = ("stopped", "ended", "failed", "cancelled")


def cmd_wait(a):
    # Polls GET /api/v1/deployments/{id} until the state is reached. Exit 0 reached, 3 the
    # deployment ended some other way, 4 the timeout passed and it is still on its way.
    deadline = time.time() + a.timeout
    last = None
    while True:
        d = call("GET", f"/api/v1/deployments/{a.id}")
        state = d.get("status") or d.get("phase") or d.get("provisioning_state")
        if state != last:
            reason = f" ({d.get('state_reason')})" if d.get("state_reason") else ""
            print(f"{datetime.datetime.now().strftime('%H:%M:%S')}  {a.id}  {state}{reason}", file=sys.stderr)
            last = state
        if state == a.until:
            code = 0
        elif state in WAIT_FINAL:
            code = 3
        elif time.time() >= deadline:
            code = 4
        else:
            time.sleep(max(1, min(a.interval, deadline - time.time())))
            continue
        if ARGS.json:
            out(d)
        elif code == 0:
            print(f"{a.id} is {state}" + (f": ssh -p {d['ssh_port']} root@{d['ssh_host']}" if d.get("ssh_host") and not d.get("sandbox") else ""))
        elif code == 3:
            print(f"{a.id} is {state}, not {a.until}: see turbo events {a.id}")
        else:
            print(f"{a.id} is still {state} after {a.timeout} s; run the same command again to keep waiting")
        sys.exit(code)


def cmd_book(a):
    # Your GPUs are reached over SSH only, so a request needs a key: the one passed here, else the
    # keys saved on the account. Checked before the quote, so nothing is asked for in vain.
    ssh_key = None
    if a.ssh_key:
        ssh_key = read_pubkey(a.ssh_key)
    elif is_sandbox_key():
        # A sandbox key reaches sandbox objects only: it cannot read the keys saved on the account.
        die("a sandbox key needs --ssh-key: pass any SSH public key (.pub); a sandbox key cannot read the keys "
            "saved on the account")
    else:
        saved = call("GET", "/api/account/ssh-keys")
        if not saved:
            die("an SSH public key is required: your GPUs are reached over SSH only. Pass --ssh-key "
                "~/.ssh/id_ed25519.pub, or save one with `turbo ssh-keys add ~/.ssh/id_ed25519.pub`.")
        say(f"using the {len(saved)} SSH key(s) saved on your account (turbo ssh-keys)")
    body = book_body(a)
    quote = call("POST", "/api/bookings/preview", body)
    say(f"{quote.get('serverName')} · {a.gpus} × GPU · {a.hours} h · volume {f'{a.volume} GB' if a.volume else 'as the template sets'}",
        f"GPU {money(quote.get('gpuCost'))}  storage {money(quote.get('storageCost'))}  tax {money(quote.get('tax'))}  total {money(quote.get('total'))}")
    if not confirm("send this request? [y/N] ", a.yes):
        return
    body.update({"templateSlug": a.template, "docker": a.image, "sshKey": ssh_key, "notes": a.notes})
    if a.client_reference:
        body["clientReference"] = a.client_reference
    if a.scenario or a.speed:
        # Sandbox keys only: the lifecycle to rehearse, and how much faster than real time.
        body["sandbox"] = {k: v for k, v in (("scenario", a.scenario), ("speed", a.speed)) if v}
    # Idempotency-Key: the same key with the same body replays the first answer (a retry never books twice).
    r = call("POST", "/api/bookings", body, extra_headers={"Idempotency-Key": a.idempotency_key} if a.idempotency_key else None)
    rid = r.get("id")
    st = r.get("status") or r.get("provisioningState")
    replayed = REPLAYED
    if ARGS.json:
        return out({"quote": quote, "booking": r, "replayed": replayed})
    if replayed:
        # The same Idempotency-Key was used before: this is that first answer, nothing new was booked.
        print(f"Already sent ({rid}): this idempotency key was used before, so nothing new was booked. "
              f"Its state now: turbo deployment {rid}. For another booking, use a new --idempotency-key.")
    elif r.get("sandbox"):
        print(f"Sandbox deployment {rid} ({st}): simulated, nothing is charged. Follow with: turbo wait {rid}")
    elif st == "requested":
        # Request mode: our team places it; nothing provisions or bills before that.
        print(f"Request received ({rid}). Our team places it and emails you a start time. "
              "Nothing is charged until your GPUs run.")
        print(f"Withdraw with: turbo stop {rid}")
    elif st in ("pending_payment", "unpaid"):
        # The 201 carries no invoice link: GPU time is drawn from prepaid credit,
        # and a top-up made now does not start this booking.
        site = api_base().replace("https://api.", "https://cloud.")
        print(f"Not started ({rid}): your prepaid credit does not cover this booking. Nothing has been charged.")
        print(f"Add prepaid credit on {site}/portal/billing, then book again.")
    else:
        print(f"booked {rid} — state {st}")
        print(f"provisioning; follow with: turbo wait {rid}")


def cmd_ssh_keys(a):
    # The keys a request uses when `turbo book` gets no --ssh-key (the API checks each one).
    if a.action == "add":
        if not a.arg:
            die("usage: turbo ssh-keys add <path to .pub> [--name NAME]")
        k = call("POST", "/api/account/ssh-keys", {"name": a.name or os.path.basename(a.arg), "publicKey": read_pubkey(a.arg)})
        if ARGS.json:
            return out(k)
        print(f"saved {k.get('id')} ({k.get('keyType')}, {k.get('fingerprint')})")
    elif a.action == "remove":
        if not a.arg:
            die("usage: turbo ssh-keys remove <id>")
        out(call("DELETE", f"/api/account/ssh-keys/{a.arg}"))
    else:
        d = call("GET", "/api/account/ssh-keys")
        out(d, [[k["id"], k.get("name"), k.get("keyType"), k.get("fingerprint"), when(k.get("createdAt"))] for k in d], ["id", "name", "type", "fingerprint", "added"])


def cmd_webhooks(a):
    # Signed POSTs of every deployment state change (docs: Compute -> Webhooks).
    # add / remove / pause / resume / rotate need the admin scope (or the console).
    act = a.action
    if act == "add":
        if not a.arg:
            die("usage: turbo webhooks add <https URL> [--description TEXT]")
        body = {"url": a.arg}
        if a.description:
            body["description"] = a.description
        h = call("POST", "/api/v1/webhooks", body)
        if ARGS.json:
            out(h)
            return
        print(f"registered {h.get('id')} -> {h.get('url')}")
        print(f"signing secret (shown once; it signs every delivery): {h.get('secret')}")
    elif act in ("remove", "test", "pause", "resume", "rotate", "deliveries"):
        if not a.arg:
            die(f"usage: turbo webhooks {act} <endpoint id>")
        if act == "remove":
            out(call("DELETE", f"/api/v1/webhooks/{a.arg}"))
        elif act == "test":
            d = call("POST", f"/api/v1/webhooks/{a.arg}/test", {})
            if ARGS.json:
                out(d)
                return
            print(f"queued {d.get('id')}: a signed ping is posted within seconds (turbo webhooks deliveries {a.arg})")
        elif act in ("pause", "resume"):
            h = call("PATCH", f"/api/v1/webhooks/{a.arg}", {"enabled": act == "resume"})
            if ARGS.json:
                out(h)
                return
            print(f"{h.get('id')} {'enabled' if h.get('enabled') else 'paused'}")
        elif act == "rotate":
            r = call("POST", f"/api/v1/webhooks/{a.arg}/rotate-secret", {})
            if ARGS.json:
                out(r)
                return
            print(f"new signing secret (shown once; the old one stops at the next delivery): {r.get('secret')}")
        else:
            d = call("GET", f"/api/v1/webhooks/{a.arg}/deliveries?limit=20")
            out(d, [[x.get("id"), x.get("event_type"), x.get("state"), x.get("last_status") or x.get("last_error") or "—",
                     x.get("attempts"), when(x.get("delivered_at") or x.get("created_at"))] for x in d],
                ["id", "event", "state", "answer", "attempts", "at"])
    else:
        d = call("GET", "/api/v1/webhooks")
        out(d, [[h["id"], h.get("url"), "on" if h.get("enabled") else (h.get("disabled_reason") or "off"),
                 h.get("failure_count") or 0, when(h.get("last_success_at"))] for h in d],
            ["id", "url", "state", "failures", "last delivered"])


def cmd_storage(a):
    if a.action == "keys":
        d = call("GET", "/api/account/s3-keys")
        out(d, [[k["id"], k["label"], k["accessKey"], when(k.get("createdAt")), "revoked" if k.get("revoked") else ("paused" if k.get("suspended") else "active")] for k in d], ["id", "label", "access key", "created", "status"])
    elif a.action == "create":
        d = call("POST", "/api/account/s3-keys", {"label": a.name or "turbo-cli"})
        if ARGS.json:
            return out(d)
        print(f"access key: {d['accessKey']}\nsecret key: {d['secretKey']}\nendpoint:   https://s3.exducer.ai   (path-style, region us-east-1)\nthe secret is shown once — store it now")
    elif a.action == "revoke":
        out(call("DELETE", f"/api/account/s3-keys/{a.name}"))
    else:
        d = call("GET", "/api/account/s3-keys/usage")
        if ARGS.json:
            return out(d)
        gb = d.get("gbUsed", 0)
        print(f"stored {gb:.3f} GB across {d.get('activeKeys')} key(s) · {money(d.get('pricePerGbMonth'))}/GB-month · this month {money(d.get('billedThisMonthUsd'))}" + (" · PAUSED (prepaid credit used up: keys paused, objects kept)" if d.get("suspended") else ""))


def cmd_billing(a):
    bal = call("GET", "/api/billing/credits/balance")
    led = call("GET", "/api/billing/credits/ledger")
    if ARGS.json:
        return out({"balance": bal, "currency": "CAD", "ledger": led[: a.n]})
    print(f"prepaid balance {money(bal.get('balanceUsd'))}")
    out(led, [[when(e["createdAt"]), e["kind"], money(e["amountUsd"]), e.get("description") or ""] for e in led[: a.n]], ["at", "kind", "amount", "description"])


def cmd_invoices(a):
    d = call("GET", "/api/billing/invoices")
    out(d, [[i["id"], i.get("period"), i.get("status"), money(i.get("amount") if "amount" in i else i.get("amount_usd"))] for i in d], ["invoice", "period", "status", "amount"])


def cmd_chat(a):
    prompt = a.prompt or sys.stdin.read()
    # No model pinned: the API fills in the one it serves (GET /api/v1/maas/health says which).
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": a.max_tokens}
    if a.model:
        body["model"] = a.model
    r = call("POST", "/api/v1/maas/chat/completions", body)
    if ARGS.json:
        return out(r)
    print(r["choices"][0]["message"]["content"])


def cmd_mcp(a):
    # The MCP server over stdio: each JSON-RPC line read from stdin is posted to the hosted server
    # (<site>/mcp) with the key this CLI holds, and the answer is written as one line on stdout.
    # Nothing else is ever printed on stdout; the key is not copied into the agent's settings.
    url = a.url or site_base() + "/mcp"
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "User-Agent": f"turbo-cli/{VERSION} (mcp)"}
    if api_key():
        headers["Authorization"] = "Bearer " + api_key()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=line.encode(), method="POST", headers=headers), timeout=120) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raw = e.read()                      # a JSON-RPC error travels with a 4xx
        except (urllib.error.URLError, OSError) as e:
            raw = b""
            try:
                msg = json.loads(line)
            except ValueError:
                msg = None
            if isinstance(msg, dict) and "id" in msg:
                raw = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32000, "message": f"cannot reach {url}: {getattr(e, 'reason', e)}"}}).encode()
        if not raw.strip():
            continue                            # a notification: 202, nothing to pass on
        try:
            text = json.dumps(json.loads(raw), ensure_ascii=False)
        except ValueError:
            continue
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


# Where each coding agent reads personal skills, and how its MCP server list is changed. The
# universal folder is read by the agents that follow the shared convention.
AGENT_HOMES = {"claude": "~/.claude", "codex": "~/.codex", "cursor": "~/.cursor"}
UNIVERSAL_SKILLS = "~/.agents/skills"
MCP_NAME = "turbo"
AGENT_STATE = os.path.join(os.path.dirname(CONF), "agent.json")


def _fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": f"turbo-cli/{VERSION}"}), timeout=60) as r:
            return r.read()
    except (urllib.error.URLError, OSError) as e:
        die(f"cannot fetch {url}: {getattr(e, 'reason', e)}")


def _skills():
    """[(name, text)] from the site's skills index, each checked against its published digest."""
    try:
        index = json.loads(_fetch(site_base() + "/.well-known/agent-skills/index.json"))
    except ValueError:
        die("the skills index is not valid JSON")
    got = []
    for s in index.get("skills", []):
        name = str(s.get("name", ""))
        if not name or any(not (c.isalnum() or c == "-") for c in name) or not str(s.get("url", "")).startswith(("https://", "http://127.0.0.1")):
            die(f"the skills index lists an entry this CLI does not accept: {name!r}")
        body = _fetch(s["url"])
        if "sha256:" + hashlib.sha256(body).hexdigest() != s.get("digest"):
            die(f"skill {name}: the file does not match the digest in the index; nothing was installed")
        got.append((name, body.decode("utf-8")))
    if not got:
        die("the skills index is empty")
    return got


def _turbo_command():
    """How an agent starts this CLI: `turbo` when it is on PATH, else this file's full path."""
    return "turbo" if shutil.which("turbo") else os.path.abspath(sys.argv[0])


def _agents(a):
    """The agents to set up: the ones named with --agent, else every one whose folder exists."""
    if a.agent:
        return list(AGENT_HOMES) if "all" in a.agent else list(dict.fromkeys(a.agent))
    return [n for n, home in AGENT_HOMES.items() if os.path.isdir(os.path.expanduser(home))]


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def _cursor_mcp(change):
    """Read ~/.cursor/mcp.json, apply change(servers) and write it back. Returns the path."""
    path = os.path.expanduser("~/.cursor/mcp.json")
    try:
        with open(path) as f:
            conf = json.load(f)
    except FileNotFoundError:
        conf = {}
    except ValueError:
        die(f"{path} is not valid JSON; fix it or add the server by hand")
    if not isinstance(conf, dict):
        die(f"{path} does not hold a JSON object; fix it or add the server by hand")
    servers = conf.setdefault("mcpServers", {})
    if change(servers):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(conf, f, indent=2)
            f.write("\n")
    return path


def _register_mcp(agent, command, dry):
    """Register `turbo mcp` with one agent. Returns a line saying what happened."""
    manual = f'add this MCP server by hand: {{"mcpServers": {{"{MCP_NAME}": {{"command": "{command}", "args": ["mcp"]}}}}}}'
    if agent == "cursor":
        if dry:
            return "would add the server to ~/.cursor/mcp.json"
        def add(servers):
            want = {"command": command, "args": ["mcp"]}
            if servers.get(MCP_NAME) == want:
                return False
            servers[MCP_NAME] = want
            return True
        return f"MCP server in {_cursor_mcp(add)}"
    binary = shutil.which(agent)
    if not binary:
        return f"the `{agent}` command is not on PATH; {manual}"
    add = [binary, "mcp", "add", "--scope", "user", MCP_NAME, "--", command, "mcp"] if agent == "claude" else [binary, "mcp", "add", MCP_NAME, "--", command, "mcp"]
    if dry:
        return "would run: " + " ".join(add)
    if _run([binary, "mcp", "get", MCP_NAME])[0] == 0:
        return "MCP server already registered"
    code, output = _run(add)
    return "MCP server registered" if code == 0 else f"`{' '.join(add[1:])}` failed ({output.splitlines()[-1] if output else code}); {manual}"


def cmd_agent(a):
    # setup: copy the skills the site publishes into each coding agent's skills folder and register
    # `turbo mcp` as an MCP server. status: what is installed. remove: undo setup.
    try:
        with open(AGENT_STATE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    installed = state.get("skills", [])           # every SKILL.md folder a setup wrote
    if a.action == "status":
        rows = []
        for name in ["universal", *AGENT_HOMES]:
            folder = os.path.expanduser(UNIVERSAL_SKILLS if name == "universal" else AGENT_HOMES[name] + "/skills")
            have = sorted(os.path.basename(p) for p in installed if os.path.dirname(p) == folder and os.path.isfile(os.path.join(p, "SKILL.md")))
            mcp = "—"
            if name == "cursor":
                try:
                    with open(os.path.expanduser("~/.cursor/mcp.json")) as f:
                        mcp = "yes" if MCP_NAME in (json.load(f).get("mcpServers") or {}) else "no"
                except (OSError, ValueError, AttributeError):
                    mcp = "no"
            elif name in ("claude", "codex"):
                binary = shutil.which(name)
                mcp = ("yes" if _run([binary, "mcp", "get", MCP_NAME])[0] == 0 else "no") if binary else "not installed"
            rows.append([name, folder, ", ".join(have) or "none", mcp])
        return out({"version": state.get("version"), "installed_at": state.get("installed_at"),
                    "agents": [dict(zip(["agent", "skills_folder", "skills", "mcp_server"], r)) for r in rows]},
                   rows, ["agent", "skills folder", "skills", "MCP server"])
    if a.action == "remove":
        done = []
        for p in installed:
            if os.path.basename(p).startswith("turbo-") and os.path.isfile(os.path.join(p, "SKILL.md")):
                if not a.dry_run:
                    shutil.rmtree(p)
                done.append(("would remove " if a.dry_run else "removed ") + p)
        if not a.no_mcp:
            if os.path.isfile(os.path.expanduser("~/.cursor/mcp.json")) and not a.dry_run:
                _cursor_mcp(lambda servers: servers.pop(MCP_NAME, None) is not None)
            for name, cmd in (("claude", ["mcp", "remove", "--scope", "user", MCP_NAME]), ("codex", ["mcp", "remove", MCP_NAME])):
                binary = shutil.which(name)
                if binary and not a.dry_run and _run([binary, *cmd])[0] == 0:
                    done.append(f"removed the MCP server from {name}")
        if not a.dry_run and os.path.isfile(AGENT_STATE):
            os.remove(AGENT_STATE)
        return out({"removed": done}) if ARGS.json else print("\n".join(done) or "nothing to remove")
    # setup
    agents = _agents(a)
    folders = [("universal", os.path.expanduser(UNIVERSAL_SKILLS))] + [(n, os.path.expanduser(AGENT_HOMES[n] + "/skills")) for n in agents]
    skills = _skills()
    written, lines = [], []
    for name, folder in folders:
        for skill, text in skills:
            target = os.path.join(folder, skill)
            written.append(target)
            if a.dry_run:
                continue
            os.makedirs(target, exist_ok=True)
            with open(os.path.join(target, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(text)
        lines.append(f"{name}: {'would install' if a.dry_run else 'installed'} {len(skills)} skills in {folder}")
    mcp = {}
    if not a.no_mcp:
        command = _turbo_command()
        for n in agents:
            mcp[n] = _register_mcp(n, command, a.dry_run)
            lines.append(f"{n}: {mcp[n]}")
    if not a.dry_run:
        # Skills an earlier setup wrote and the site no longer publishes are removed.
        for p in installed:
            if p not in written and os.path.basename(p).startswith("turbo-") and os.path.isfile(os.path.join(p, "SKILL.md")):
                shutil.rmtree(p)
        os.makedirs(os.path.dirname(AGENT_STATE), exist_ok=True)
        with open(AGENT_STATE, "w") as f:
            json.dump({"version": VERSION, "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "source": site_base(), "skills": written}, f, indent=2)
    if ARGS.json:
        return out({"dry_run": a.dry_run, "skills": [n for n, _ in skills], "folders": [f for _, f in folders], "mcp": mcp,
                    "key": "sandbox" if is_sandbox_key() else ("live" if api_key() else "none")})
    print("\n".join(lines))
    if not agents:
        print("no coding agent folder found (~/.claude, ~/.codex, ~/.cursor): the skills are in the universal folder only; "
              "name one with --agent claude|codex|cursor to set it up anyway")
    if not api_key():
        print("no API key yet: run `turbo login` so the MCP server can act for you (the public tools work without one)")
    if not a.dry_run:
        print("start a new session of your agent to load the skills and the MCP tools")


def cmd_status(a):
    site = api_base().replace("https://api.", "https://")
    d = call("GET", "/api/v1/public/status", auth=False, base=site)
    rows = [[s.get("name"), s.get("status"), f"{(s.get('uptime') or 0):.2f}%"] for s in d.get("services", [])]
    if ARGS.json:
        return out(d)
    print(f"{d.get('headline') or d.get('overall') or d.get('status') or ''}".strip())
    out(d, rows, ["service", "status", "uptime 90d"])


# ---------------------------------------------------------------- parser
p = argparse.ArgumentParser(prog="turbo", description="ExducerAI cloud CLI")
p.add_argument("--json", action="store_true", help="print raw JSON")
p.add_argument("--version", action="version", version=f"turbo {VERSION}")
common = argparse.ArgumentParser(add_help=False)
common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print raw JSON")
class _Sub:
    """subparsers that all accept --json after the command name too"""
    def __init__(self, sp): self.sp = sp
    def add_parser(self, *a, **k): k.setdefault("parents", [common]); return self.sp.add_parser(*a, **k)
sp = _Sub(p.add_subparsers(dest="cmd", required=True))
s = sp.add_parser("login", help="store an API key"); s.add_argument("--api-key"); s.add_argument("--api", help="API base, e.g. https://api.exducer.ai"); s.set_defaults(fn=cmd_login)
sp.add_parser("logout", help="forget the stored key").set_defaults(fn=cmd_logout)
sp.add_parser("whoami", help="account, balance, API in use").set_defaults(fn=cmd_whoami)
sp.add_parser("availability", help="is each GPU model free right now (yes/no)").set_defaults(fn=cmd_availability)
sp.add_parser("servers", help="bookable servers (ids for `book`)").set_defaults(fn=cmd_servers)
s = sp.add_parser("templates", help="templates you can request, and the image each runs"); s.add_argument("--category"); s.set_defaults(fn=cmd_templates)
sp.add_parser("deployments", help="your deployments").set_defaults(fn=cmd_deployments)
s = sp.add_parser("deployment", help="one deployment in detail"); s.add_argument("id"); s.set_defaults(fn=cmd_deployment)
s = sp.add_parser("events", help="state transitions of a deployment"); s.add_argument("id"); s.set_defaults(fn=cmd_events)
s = sp.add_parser("stop", help="stop a deployment now, or withdraw a request"); s.add_argument("id"); s.add_argument("-y", "--yes", action="store_true"); s.set_defaults(fn=cmd_stop)
s = sp.add_parser("extend", help="run a deployment longer: push the end of its term (same machine, same connection details)")
s.add_argument("id"); s.add_argument("--hours", type=int, required=True, help="1-720; the new end may not be more than 720 h away")
s.add_argument("-y", "--yes", action="store_true"); s.add_argument("--idempotency-key", help="8-128 characters: a retry with the same key never extends twice"); s.set_defaults(fn=cmd_extend)
s = sp.add_parser("renew", help="renew a deployment automatically at the end of its term (on/off), while prepaid credit lasts")
s.add_argument("id"); s.add_argument("state", choices=["on", "off"]); s.add_argument("--hours", type=int, help="the renewal block, 1-720 (default 720: 30 days at a time)"); s.set_defaults(fn=cmd_renew)
s = sp.add_parser("ssh", help="ssh into a running deployment, or run one command there: turbo ssh ID -- nvidia-smi")
s.add_argument("id"); s.add_argument("--batch", action="store_true", help="never prompt: connect only when the host key matches the fingerprint the API publishes")
s.add_argument("rest", nargs=argparse.REMAINDER); s.set_defaults(fn=cmd_ssh)
s = sp.add_parser("quote", help="the price of a booking, tax included; books nothing and needs no key")
s.add_argument("--server", required=True, help="server id from `turbo servers`"); s.add_argument("--gpus", type=int, default=8); s.add_argument("--hours", type=int, default=1); s.set_defaults(fn=cmd_quote)
s = sp.add_parser("wait", help="block until a deployment reaches a state (exit 0), ends otherwise (3) or the timeout passes (4)")
s.add_argument("id"); s.add_argument("--until", default="running", choices=["requested", "queued", "provisioning", "running", "stopped", "ended", "failed", "cancelled"])
s.add_argument("--timeout", type=int, default=1800, help="seconds (default 1800)"); s.add_argument("--interval", type=int, default=15, help="seconds between reads (default 15)"); s.set_defaults(fn=cmd_wait)
s = sp.add_parser("book", help="request GPUs (quote, confirm, send); our team places it and emails you a start time")
s.add_argument("--server", required=True, help="server id from `turbo servers`"); s.add_argument("--gpus", type=int, default=8, help="8 or 16: GPUs are rented per 8-GPU node"); s.add_argument("--hours", type=int, default=1)
s.add_argument("--template", help="template slug from `turbo templates` (default: the image that runs today)")
s.add_argument("--image", help="container image to run; only an image a template already runs (see `turbo templates`), ask us for another")
s.add_argument("--volume", type=int, help="NVMe volume GB")
s.add_argument("--ssh-key", help="path to your SSH public key (.pub); required unless you saved one with `turbo ssh-keys add`: ed25519, ECDSA, sk-* or RSA >= 3072 bits")
s.add_argument("--notes"); s.add_argument("-y", "--yes", action="store_true")
s.add_argument("--idempotency-key", help="8-128 characters: the same key with the same body replays the first answer, so a retry never books twice")
s.add_argument("--client-reference", help="your own reference for this deployment (unique among your live deployments)")
s.add_argument("--scenario", choices=["immediate", "busy", "marketplace_release", "fail_start", "host_unreachable", "insufficient_credit", "capacity_timeout", "slow_start"], help="sandbox keys only: the lifecycle to rehearse")
s.add_argument("--speed", type=int, help="sandbox keys only: 1-60, shortens every simulated wait")
s.set_defaults(fn=cmd_book)
s = sp.add_parser("ssh-keys", help="SSH keys saved on your account (used when `book` gets no --ssh-key)")
s.add_argument("action", choices=["list", "add", "remove"], nargs="?", default="list"); s.add_argument("arg", nargs="?", help="add: path to a .pub file; remove: key id")
s.add_argument("--name", help="add: a name for the key (default: the file name)"); s.set_defaults(fn=cmd_ssh_keys)
s = sp.add_parser("webhooks", help="signed POSTs of every deployment state change (docs: Compute -> Webhooks)")
s.add_argument("action", choices=["list", "add", "remove", "test", "deliveries", "pause", "resume", "rotate"], nargs="?", default="list")
s.add_argument("arg", nargs="?", help="add: the https URL; the others: the endpoint id (whe_...)")
s.add_argument("--description", help="add: a note shown in the list"); s.set_defaults(fn=cmd_webhooks)
s = sp.add_parser("storage", help="object storage keys and usage"); s.add_argument("action", choices=["usage", "keys", "create", "revoke"], nargs="?", default="usage"); s.add_argument("name", nargs="?"); s.set_defaults(fn=cmd_storage)
s = sp.add_parser("billing", help="prepaid balance and ledger"); s.add_argument("-n", type=int, default=15); s.set_defaults(fn=cmd_billing)
sp.add_parser("invoices", help="invoices").set_defaults(fn=cmd_invoices)
s = sp.add_parser("chat", help="ask the hosted model"); s.add_argument("prompt", nargs="?"); s.add_argument("--model", default=None, help="a model id; default: the one the API serves (GET /api/v1/maas/health)"); s.add_argument("--max-tokens", type=int, default=400); s.set_defaults(fn=cmd_chat)
sp.add_parser("status", help="public service status").set_defaults(fn=cmd_status)
s = sp.add_parser("mcp", help="serve the MCP tools over stdio for a coding agent (register with: claude mcp add turbo -- turbo mcp)")
s.add_argument("--url", help="the MCP endpoint (default: the site's /mcp)"); s.set_defaults(fn=cmd_mcp)
s = sp.add_parser("agent", help="set up coding agents: install the skills and register the MCP server")
s.add_argument("action", choices=["setup", "status", "remove"])
s.add_argument("--agent", action="append", choices=["claude", "codex", "cursor", "all"], help="set up this agent (repeatable); default: every agent whose folder exists")
s.add_argument("--no-mcp", action="store_true", help="skills only: leave the MCP server lists alone")
s.add_argument("--dry-run", action="store_true", help="print what would change and change nothing"); s.set_defaults(fn=cmd_agent)

ARGS = p.parse_args()
if not hasattr(ARGS, "json"): ARGS.json = False
ARGS.fn(ARGS)
