"""
Spare Parts Desk — Kaveri Spares & Hydraulics
================================================
Backend: ONLY Python (Standard Library — no Flask, no packages to install)
Frontend: HTML + CSS + JavaScript (separate files in /static)

Run:  python3 app.py
Open: http://localhost:8000
"""
import csv, json, math, re
from collections import defaultdict
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

BASE = Path(__file__).parent
DATA, STATIC = BASE / "data", BASE / "static"
REQ_FILE = DATA / "requests.json"
DAYS = 60  # sales history: 2026-09-17 to 2026-11-15
LOC_ORDER = ["Gokak", "Belgaum", "Hubli", "Dharwad", "Bijapur", "Bagalkot", "Belgaum WH", "Hubli WH"]

def read_csv(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------- Load & compute (once at startup) ----------------
products  = read_csv("products.csv")
inventory = read_csv("inventory.csv")
sales     = read_csv("sales.csv")
suppliers = read_csv("suppliers.csv")
orders    = read_csv("purchase_orders.csv")

prod = {p["sku"]: p for p in products}
locations = [l for l in LOC_ORDER if any(r["location"] == l for r in inventory)]

stock_sku, stock_loc, detail = defaultdict(int), defaultdict(int), defaultdict(dict)
for r in inventory:
    s = int(r["stock"]); stock_sku[r["sku"]] += s; stock_loc[r["location"]] += s
    detail[r["sku"]][r["location"]] = s

sold_sku, sold_loc, sold_sku_loc = defaultdict(int), defaultdict(int), defaultdict(int)
for r in sales:
    q = int(r["qty_sold"]); sold_sku[r["sku"]] += q; sold_loc[r["location"]] += q
    sold_sku_loc[(r["sku"], r["location"])] += q

sup_sku = defaultdict(list)
for s in suppliers:
    sup_sku[s["sku"]].append({"supplier": s["supplier"], "price": float(s["price"]),
                              "lead": int(s["lead_time_days"]), "moq": int(s["moq"])})
for k in sup_sku: sup_sku[k].sort(key=lambda x: (x["price"], x["lead"]))

ITEMS = []
for p in products:
    sku = p["sku"]; total = stock_sku[sku]; sold = sold_sku[sku]
    daily = round(sold / DAYS, 2); cover = round(total / daily, 1) if daily else 999
    status = "Out of Stock" if total == 0 else "Critical" if cover < 7 else "Low Stock" if cover < 21 else "In Stock"
    best = sup_sku[sku][0] if sup_sku[sku] else {"supplier": "—", "price": 0, "lead": 0, "moq": 0}
    rec_qty = rec_cost = 0
    if daily and cover < 21:
        rec_qty = max(best["moq"], math.ceil(daily * (best["lead"] + 14) - total)); rec_cost = round(rec_qty * best["price"], 2)
    mine = [{"location": l, "stock": detail[sku].get(l, 0)} for l in locations]
    ITEMS.append({**p, "total_stock": total, "sold_60d": sold, "daily_demand": daily, "days_cover": cover,
                  "status": status, "best_supplier": best["supplier"], "price": best["price"], "lead": best["lead"],
                  "moq": best["moq"], "rec_qty": rec_qty, "rec_cost": rec_cost, "stock_by_loc": mine,
                  "suppliers": sup_sku[sku],
                  "loc_out": sum(1 for m in mine if m["stock"] == 0),
                  "loc_low": sum(1 for m in mine if 1 <= m["stock"] <= 10)})
ITEM_BY_SKU = {i["sku"]: i for i in ITEMS}

LOC_ITEMS = []
for r in inventory:
    sku, loc, st = r["sku"], r["location"], int(r["stock"])
    sold = sold_sku_loc[(sku, loc)]; daily = round(sold / DAYS, 2)
    LOC_ITEMS.append({"sku": sku, "product": prod[sku]["product_name"], "model": prod[sku]["machine_model"],
                      "category": prod[sku]["category"], "location": loc, "stock": st, "sold_60d": sold,
                      "daily_demand": daily, "days_cover": round(st / daily, 1) if daily else 999,
                      "status": "Out of Stock" if st == 0 else "Low Stock" if st <= 10 else "In Stock"})
LOC_ITEMS.sort(key=lambda x: (x["stock"], -x["daily_demand"]))

TRANSFERS = []
for l in LOC_ITEMS:
    if l["location"].endswith("WH") or l["stock"] > 3 or not l["daily_demand"]: continue
    donor = max((x for x in LOC_ITEMS if x["sku"] == l["sku"] and x["location"] != l["location"]),
                key=lambda x: x["stock"], default=None)
    if donor and donor["stock"] > 10:
        qty = int(min(donor["stock"] - 5, max(5, round(l["daily_demand"] * 14))))
        if qty > 0: TRANSFERS.append({"sku": l["sku"], "product": l["product"], "from_loc": donor["location"],
                                      "from_stock": donor["stock"], "to_loc": l["location"], "to_stock": l["stock"],
                                      "qty": qty, "daily_demand": l["daily_demand"]})
TRANSFERS.sort(key=lambda x: -x["daily_demand"])

KPI = {"total_sku": len(products), "total_units": sum(stock_sku.values()),
       "avail_loc": sum(1 for r in inventory if int(r["stock"]) > 10),
       "low_loc": sum(1 for r in inventory if 1 <= int(r["stock"]) <= 10),
       "out_loc": sum(1 for r in inventory if int(r["stock"]) == 0),
       "inventory_value": round(sum(i["total_stock"] * i["price"] for i in ITEMS)),
       "open_po": sum(1 for o in orders if o["status"] in ("Open", "Confirmed"))}
CAT_STOCK = {}
for i in ITEMS: CAT_STOCK[i["category"]] = CAT_STOCK.get(i["category"], 0) + i["total_stock"]

# ---------------- Requests (persisted to data/requests.json) ----------------
def seed_requests():
    reqs, seen = [], set()
    for po in orders:
        i = ITEM_BY_SKU.get(po["sku"], {})
        price = next((s["price"] for s in sup_sku[po["sku"]] if s["supplier"] == po["supplier"]), i.get("price", 0))
        reqs.append({"id": po["po"], "sku": po["sku"], "product": i.get("product_name", po["sku"]),
                     "model": i.get("machine_model", "—"), "category": i.get("category", "—"), "supplier": po["supplier"],
                     "qty": int(po["qty"]), "cost": round(int(po["qty"]) * price, 2), "expected": po["expected_date"],
                     "status": "Approved" if po["status"] == "Received" else "Pending",
                     "source": "Purchase Order", "note": po["status"], "requested_by": "Purchase Order", "decided_by": ""}); seen.add(po["sku"])
    n = 5001
    for i in sorted(ITEMS, key=lambda x: x["days_cover"]):
        if i["rec_qty"] and i["sku"] not in seen:
            reqs.append({"id": f"REQ-{n}", "sku": i["sku"], "product": i["product_name"], "model": i["machine_model"],
                         "category": i["category"], "supplier": i["best_supplier"], "qty": i["rec_qty"],
                         "cost": i["rec_cost"], "expected": "—", "status": "Pending",
                         "source": "AI Recommendation", "note": f"{i['status']} • {i['days_cover']} days cover", "requested_by": "AI", "decided_by": ""}); n += 1
    return reqs

def load_requests():
    if REQ_FILE.exists():
        try: return json.loads(REQ_FILE.read_text())
        except Exception: pass
    reqs = seed_requests(); save_requests(reqs); return reqs

def save_requests(reqs): REQ_FILE.write_text(json.dumps(reqs, indent=2))

REQUESTS = load_requests()

# ---------------- AI Assistant (rule-based, queries real data) ----------------
def ai_reply(msg):
    t, sku_m = msg.lower(), re.search(r"[A-Z]{3}-\d{4}", msg.upper())
    item = ITEM_BY_SKU.get(sku_m.group()) if sku_m else None
    if item:
        locs = ", ".join(f"{m['location']}: {m['stock']}" for m in item["stock_by_loc"])
        r = (f"{item['sku']} — {item['product_name']} ({item['machine_model']}, {item['category']})\n"
             f"• Total stock: {item['total_stock']} units  •  Sold (60d): {item['sold_60d']}  •  Demand: {item['daily_demand']}/day\n"
             f"• Days cover: {item['days_cover']}  •  Status: {item['status']}\n• Locations: {locs}\n"
             f"• Best supplier: {item['best_supplier']} @ ₹{item['price']:,.0f} (lead {item['lead']}d, MOQ {item['moq']})")
        if item["rec_qty"]: r += f"\n• 💡 Recommendation: order {item['rec_qty']} units (₹{item['rec_cost']:,.0f})."
        return r
    if "out of stock" in t:
        z = [l for l in LOC_ITEMS if l["stock"] == 0]
        return f"🔴 {len(z)} SKU-location slots are at ZERO:\n" + "\n".join(
            f"• {l['sku']} {l['product']} at {l['location']} (demand {l['daily_demand']}/day)" for l in z[:15]) + \
            "\n\nNo SKU is zero network-wide — try a Transfer (see Recommendations) before buying."
    if "reorder" in t or "recommend" in t or "order first" in t:
        recs = [i for i in sorted(ITEMS, key=lambda x: x["days_cover"]) if i["rec_qty"]]
        return "💡 Reorder first:\n" + "\n".join(
            f"{n+1}. {i['sku']} {i['product_name']} — stock {i['total_stock']}, cover {i['days_cover']}d → order {i['rec_qty']} from {i['best_supplier']} (₹{i['rec_cost']:,.0f})"
            for n, i in enumerate(recs[:8])) + "\n\n🔀 Also check Transfer Recommendations — most shortages are location imbalance."
    if "transfer" in t:
        return "🔀 Top transfers (move, don't buy):\n" + "\n".join(
            f"• {x['sku']} {x['product']}: move {x['qty']} from {x['from_loc']} ({x['from_stock']}) → {x['to_loc']} ({x['to_stock']} left)" for x in TRANSFERS[:8])
    if "low stock" in t:
        cat = next((c for c in CAT_STOCK if c.lower().split()[0] in t), None)
        l = [x for x in LOC_ITEMS if x["status"] != "In Stock" and (not cat or x["category"] == cat)]
        return f"⚠️ {len(l)} low/out slots{f' in {cat}' if cat else ''}:\n" + "\n".join(
            f"• {x['sku']} {x['product']} at {x['location']} — {x['stock']} left ({x['status']})" for x in l[:12])
    if "cheapest" in t or "supplier" in t:
        return "Tell me a SKU, e.g. 'Cheapest supplier for BLT-1003?' I compare all 205 supplier offers on price + lead time."
    if "location" in t or "warehouse" in t:
        return "🏬 Stock by location:\n" + "\n".join(f"• {l}: {stock_loc[l]:,} units" for l in locations)
    if "top sell" in t or "fast" in t or "best sell" in t:
        top = sorted(ITEMS, key=lambda x: -x["sold_60d"])[:8]
        return "🔥 Top sellers (60 days):\n" + "\n".join(f"{n+1}. {i['sku']} {i['product_name']} — {i['sold_60d']} sold, stock {i['total_stock']}" for n, i in enumerate(top))
    if "pending" in t or "approval" in t or "request" in t:
        p = [r for r in REQUESTS if r["status"] == "Pending"]
        return f"⏳ {len(p)} requests pending approval worth ₹{sum(r['cost'] for r in p):,.0f}. Open Requests & Approvals to Approve / Reject."
    return ("I can help with:\n• Any SKU — 'stock of BRG-1000'\n• 'Which items are out of stock?'\n• 'What should I reorder first?' / 'Show transfers'\n"
            "• 'Cheapest supplier for BLT-1003?'  • 'Top selling products'  • 'Which location has lowest stock?'")

# ---------------- HTTP + REST API ----------------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=str(STATIC), **kw)
    def log_message(self, *a): pass
    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", len(body)); self.end_headers()
        self.wfile.write(body)
    def body_json(self):
        n = int(self.headers.get("Content-Length", 0)); return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path); path, q = u.path, parse_qs(u.query)
        if path == "/": self.path = "/index.html"; return super().do_GET()
        if not path.startswith("/api/"): return super().do_GET()
        if path == "/api/health": return self.send_json({"status": "ok", "app": "Spare Parts Desk"})
        if path == "/api/dashboard":
            return self.send_json({"kpi": KPI, "locations": locations, "stock_by_loc": dict(stock_loc),
                "cat_stock": CAT_STOCK, "fast": sorted(ITEMS, key=lambda x: -x["sold_60d"])[:10],
                "urgent": LOC_ITEMS[:12], "pending_requests": sum(1 for r in REQUESTS if r["status"] == "Pending")})
        if path == "/api/inventory":
            items = ITEMS
            if q.get("search"): items = [i for i in items if q["search"][0].lower() in f"{i['sku']} {i['product_name']} {i['machine_model']} {i['category']}".lower()]
            for key, field in (("category", "category"), ("model", "machine_model"), ("status", "status")):
                if q.get(key): items = [i for i in items if i[field] == q[key][0]]
            s = q.get("sort", ["cover"])[0]
            items = sorted(items, key={"cover": lambda x: x["days_cover"], "stockAsc": lambda x: x["total_stock"],
                             "stockDesc": lambda x: -x["total_stock"], "demand": lambda x: -x["daily_demand"],
                             "name": lambda x: x["product_name"]}.get(s, lambda x: x["days_cover"]))
            return self.send_json({"count": len(items), "items": items,
                                   "categories": sorted({i["category"] for i in ITEMS}),
                                   "models": sorted({i["machine_model"] for i in ITEMS})})
        if path.startswith("/api/inventory/"):
            item = ITEM_BY_SKU.get(unquote(path.split("/")[-1])); return self.send_json(item or {"error": "SKU not found"}, 200 if item else 404)
        if path == "/api/recommendations":
            return self.send_json({"reorders": [i for i in sorted(ITEMS, key=lambda x: x["days_cover"]) if i["rec_qty"]], "transfers": TRANSFERS})
        if path == "/api/requests": return self.send_json({"requests": REQUESTS})
        if path == "/api/suppliers": return self.send_json({"items": ITEMS, "suppliers": suppliers})
        if path == "/api/purchase-orders": return self.send_json({"orders": orders})
        return self.send_json({"error": "API endpoint not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/chat":
            return self.send_json({"reply": ai_reply(self.body_json().get("message", ""))})
        if path == "/api/requests":
            d = self.body_json(); item = ITEM_BY_SKU.get(str(d.get("sku", "")).upper())
            if not item: return self.send_json({"error": "Invalid SKU"}, 400)
            qty = int(d.get("qty") or item["rec_qty"] or item["moq"])
            req = {"id": f"REQ-{5000 + sum(1 for r in REQUESTS if r['id'].startswith('REQ')) + 1}", "sku": item["sku"],
                   "product": item["product_name"], "model": item["machine_model"], "category": item["category"],
                   "supplier": item["best_supplier"], "qty": qty, "cost": round(qty * item["price"], 2),
                   "expected": "—", "status": "Pending", "source": "Manual", "note": d.get("note", "Manual request") or "Manual request",
                   "requested_by": str(d.get("name") or "Team Member"), "decided_by": ""}
            REQUESTS.insert(0, req); save_requests(REQUESTS); return self.send_json(req, 201)
        return self.send_json({"error": "Not found"}, 404)

    def do_PUT(self):  # approve / reject:  PUT /api/requests/<id>  {"status":"Approved"}
        path = urlparse(self.path).path
        if path.startswith("/api/requests/"):
            payload = self.body_json(); rid, status = unquote(path.split("/")[-1]), payload.get("status"); decider = str(payload.get("name") or "")
            if status not in ("Approved", "Rejected", "Pending"): return self.send_json({"error": "Status must be Approved / Rejected / Pending"}, 400)
            name = decider
            for r in REQUESTS:
                if r["id"] == rid: r["status"] = status; r["decided_by"] = name or r.get("decided_by", ""); save_requests(REQUESTS); return self.send_json(r)
            return self.send_json({"error": "Request not found"}, 404)
        return self.send_json({"error": "Not found"}, 404)

if __name__ == "__main__":
    print("=" * 62)
    print("  SPARE PARTS DESK — Kaveri Spares & Hydraulics")
    print("  Website : http://localhost:8000")
    print("  API     : http://localhost:8000/api/dashboard")
    print("=" * 62)
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
