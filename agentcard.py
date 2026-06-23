#!/usr/bin/env python3
"""
AgentCard — self-describing capability manifest & negotiation protocol for agents.

Think `robots.txt`, but for AI agents. An agent publishes a small JSON "card"
describing who it is, what it can do, what it costs, its rate limits and its
trust level — served at /.well-known/agent-card.json. Before delegating work,
another agent (or an orchestrator) fetches that card and *negotiates*: does this
agent have the capabilities I need, within my cost budget, at a trust level I
accept? Yes/no, with reasons.

Pure Python standard library. Zero dependencies.

Domains: multi-agent orchestration · trust/security gating · cross-vendor
interop & discovery · agent marketplaces.
"""
import argparse
import json
import sys
import urllib.request

TRUST_LEVELS = ["unverified", "self-attested", "verified", "certified"]
WELL_KNOWN = "/.well-known/agent-card.json"


def trust_rank(level):
    return TRUST_LEVELS.index(level) if level in TRUST_LEVELS else -1


def validate_card(card):
    errors = []
    for field in ("id", "name", "version", "trust", "capabilities"):
        if field not in card:
            errors.append(f"missing required field: {field}")
    if "trust" in card and card["trust"] not in TRUST_LEVELS:
        errors.append(f"trust must be one of {TRUST_LEVELS}, got {card['trust']!r}")
    caps = card.get("capabilities")
    if not isinstance(caps, list):
        errors.append("capabilities must be a list")
    else:
        for i, c in enumerate(caps):
            if not isinstance(c, dict):
                errors.append(f"capability[{i}] must be an object"); continue
            for f in ("name", "input", "output"):
                if f not in c:
                    errors.append(f"capability[{i}] missing '{f}'")
            if "cost_usd" in c and not isinstance(c["cost_usd"], (int, float)):
                errors.append(f"capability[{i}].cost_usd must be a number")
    return errors


def cmd_init(args):
    card = {
        "id": args.id,
        "name": args.name,
        "version": args.version,
        "trust": args.trust,
        "endpoint": args.endpoint or f"https://{args.id}",
        "contact": args.contact or "",
        "rate_limit": args.rate_limit or "60/min",
        "capabilities": [],
    }
    out = json.dumps(card, indent=2)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out + "\n")
        print(f"wrote {args.out}")
    else:
        print(out)
    return 0


def cmd_add_capability(args):
    card = json.load(open(args.card, encoding="utf-8"))
    cap = {"name": args.name, "input": args.input, "output": args.output}
    if args.cost is not None:
        cap["cost_usd"] = args.cost
    if args.rate:
        cap["rate"] = args.rate
    if args.desc:
        cap["description"] = args.desc
    card.setdefault("capabilities", [])
    card["capabilities"] = [c for c in card["capabilities"] if c.get("name") != args.name]
    card["capabilities"].append(cap)
    open(args.card, "w", encoding="utf-8").write(json.dumps(card, indent=2) + "\n")
    print(f"added capability '{args.name}' to {args.card}")
    return 0


def cmd_validate(args):
    card = json.load(open(args.card, encoding="utf-8"))
    errs = validate_card(card)
    if args.format == "json":
        print(json.dumps({"valid": not errs, "errors": errs}, indent=2))
    elif errs:
        print("INVALID:")
        for e in errs:
            print("  - " + e)
    else:
        print(f"VALID — {card['name']} ({card['id']}) "
              f"trust={card['trust']} caps={len(card.get('capabilities', []))}")
    return 1 if errs else 0


def cmd_negotiate(args):
    card = json.load(open(args.card, encoding="utf-8"))
    errs = validate_card(card)
    if errs:
        print("cannot negotiate against an invalid card:", file=sys.stderr)
        for e in errs:
            print("  - " + e, file=sys.stderr)
        return 2
    required = [r.strip() for r in args.require.split(",") if r.strip()]
    by_name = {c["name"]: c for c in card["capabilities"]}
    matched = [r for r in required if r in by_name]
    missing = [r for r in required if r not in by_name]

    over_budget = []
    if args.max_cost is not None:
        for r in matched:
            cost = by_name[r].get("cost_usd")
            if cost is not None and cost > args.max_cost:
                over_budget.append((r, cost))

    trust_ok = True
    if args.min_trust:
        trust_ok = trust_rank(card["trust"]) >= trust_rank(args.min_trust)

    satisfied = not missing and not over_budget and trust_ok
    res = {
        "agent": card["id"], "satisfied": satisfied,
        "matched": matched, "missing": missing,
        "over_budget": [{"capability": c, "cost_usd": v} for c, v in over_budget],
        "trust": card["trust"], "trust_required": args.min_trust, "trust_ok": trust_ok,
    }
    if args.format == "json":
        print(json.dumps(res, indent=2))
    else:
        print(f"agent: {card['name']} ({card['id']})  trust={card['trust']}")
        print(f"  matched   : {matched or '—'}")
        print(f"  missing   : {missing or '—'}")
        if over_budget:
            print(f"  over budget: {[f'{c} ${v}' for c, v in over_budget]}")
        if args.min_trust:
            print(f"  trust     : need >= {args.min_trust} -> {'OK' if trust_ok else 'FAIL'}")
        print(f"\n  DECISION: {'ACCEPT — can delegate' if satisfied else 'REJECT'}")
    return 0 if satisfied else 1


def _fetch(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read().decode("utf-8")


def cmd_discover(args):
    url = args.url.rstrip("/")
    tried = [url]
    body = None
    try:
        body = _fetch(url)
        json.loads(body)
    except Exception:
        body = None
    if body is None and WELL_KNOWN not in url:
        wk = url + WELL_KNOWN
        tried.append(wk)
        try:
            body = _fetch(wk)
        except Exception as e:
            print(f"could not fetch a card from: {tried} ({e})", file=sys.stderr)
            return 2
    if body is None:
        print(f"could not fetch a card from: {tried}", file=sys.stderr)
        return 2
    try:
        card = json.loads(body)
    except json.JSONDecodeError:
        print("fetched resource is not valid JSON", file=sys.stderr)
        return 2
    errs = validate_card(card)
    if args.format == "json":
        print(json.dumps({"valid": not errs, "errors": errs, "card": card}, indent=2))
    else:
        status = "VALID" if not errs else f"INVALID ({len(errs)} errors)"
        print(f"discovered: {card.get('name')} ({card.get('id')})  [{status}]")
        print(f"  trust={card.get('trust')}  capabilities:")
        for c in card.get("capabilities", []):
            cost = f" ${c['cost_usd']}" if "cost_usd" in c else ""
            print(f"    - {c.get('name')}: {c.get('input')} -> {c.get('output')}{cost}")
    return 0 if not errs else 1


def cmd_serve(args):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    card_bytes = open(args.card, "rb").read()
    json.loads(card_bytes)  # fail fast if invalid JSON

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", WELL_KNOWN):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(card_bytes)))
                self.end_headers()
                self.wfile.write(card_bytes)
            else:
                self.send_error(404, "no card here")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"serving {args.card} at http://{args.host}:{args.port}{WELL_KNOWN}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="agentcard", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["text", "json"], default="text")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", parents=[common], help="scaffold a new agent card")
    s.add_argument("--id", required=True); s.add_argument("--name", required=True)
    s.add_argument("--version", default="0.1.0")
    s.add_argument("--trust", choices=TRUST_LEVELS, default="self-attested")
    s.add_argument("--endpoint"); s.add_argument("--contact")
    s.add_argument("--rate-limit"); s.add_argument("--out")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("add-capability", parents=[common], help="add/replace a capability")
    s.add_argument("card")
    s.add_argument("--name", required=True); s.add_argument("--input", required=True)
    s.add_argument("--output", required=True)
    s.add_argument("--cost", type=float, default=None); s.add_argument("--rate")
    s.add_argument("--desc")
    s.set_defaults(func=cmd_add_capability)

    s = sub.add_parser("validate", parents=[common], help="validate a card")
    s.add_argument("card"); s.set_defaults(func=cmd_validate)

    s = sub.add_parser("negotiate", parents=[common], help="can this card satisfy my needs?")
    s.add_argument("--card", required=True)
    s.add_argument("--require", required=True, help="comma-separated capability names")
    s.add_argument("--max-cost", type=float, default=None)
    s.add_argument("--min-trust", choices=TRUST_LEVELS, default=None)
    s.set_defaults(func=cmd_negotiate)

    s = sub.add_parser("discover", parents=[common], help="fetch + validate a remote card")
    s.add_argument("url"); s.set_defaults(func=cmd_discover)

    s = sub.add_parser("serve", parents=[common], help="serve a card over HTTP")
    s.add_argument("card"); s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(func=cmd_serve)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
