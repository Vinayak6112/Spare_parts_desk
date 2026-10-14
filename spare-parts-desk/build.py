import csv, json, collections, math, os
BASE="/home/user/uploads"
OUT="/home/user/spare-parts-desk/index.html"

products=list(csv.DictReader(open(f"{BASE}/products.csv")))
inventory=list(csv.DictReader(open(f"{BASE}/inventory.csv")))
sales=list(csv.DictReader(open(f"{BASE}/sales.csv")))
suppliers=list(csv.DictReader(open(f"{BASE}/suppliers.csv")))
pos=list(csv.DictReader(open(f"{BASE}/purchase_orders.csv")))

prod={p['sku']:p for p in products}
locations=sorted(set(r['location'] for r in inventory), key=lambda x: ["Gokak","Belgaum","Hubli","Dharwad","Bijapur","Bagalkot","Belgaum WH","Hubli WH"].index(x) if x in ["Gokak","Belgaum","Hubli","Dharwad","Bijapur","Bagalkot","Belgaum WH","Hubli WH"] else 99)
# stock per sku, per sku-loc
stock_by_sku=collections.defaultdict(int)
stock_by_loc=collections.defaultdict(int)
stock_detail=collections.defaultdict(dict)  # sku -> loc -> stock
for r in inventory:
    s=int(r['stock']); stock_by_sku[r['sku']]+=s; stock_by_loc[r['location']]+=s; stock_detail[r['sku']][r['location']]=s

# sales 60 days 2026-09-17 to 2026-11-15 = 60 days
DAYS=60
sold_by_sku=collections.defaultdict(int)
sold_by_sku_loc=collections.defaultdict(int)
sold_by_loc=collections.defaultdict(int)
sold_by_cat=collections.defaultdict(int)
for r in sales:
    q=int(r['qty_sold']); sold_by_sku[r['sku']]+=q; sold_by_loc[r['location']]+=q
    sold_by_sku_loc[(r['sku'],r['location'])]+=q
    if r['sku'] in prod: sold_by_cat[prod[r['sku']]['category']]+=q

# suppliers per sku sorted by price then lead
sup_by_sku=collections.defaultdict(list)
for s in suppliers:
    sup_by_sku[s['sku']].append({"supplier":s['supplier'],"price":float(s['price']),"lead":int(s['lead_time_days']),"moq":int(s['moq'])})
for k in sup_by_sku: sup_by_sku[k].sort(key=lambda x:(x['price'],x['lead']))

items=[]
for p in products:
    sku=p['sku']; total=stock_by_sku.get(sku,0); sold=sold_by_sku.get(sku,0); daily=round(sold/DAYS,2) if sold else 0
    cover= round(total/daily,1) if daily>0 else 999
    if total==0: status="Out of Stock"
    elif cover<7: status="Critical"
    elif cover<21: status="Low Stock"
    else: status="In Stock"
    best=sup_by_sku.get(sku,[None])[0]
    # reorder: cover lead+14 days safety
    rec_qty=0; rec_cost=0
    if best and daily>0 and cover<21:
        need=math.ceil(daily*(best['lead']+14)-total)
        rec_qty=max(best['moq'], need) if need>0 else best['moq']
        # round up to moq multiple? keep at least moq
        rec_cost=round(rec_qty*best['price'],2)
    elif best and total==0:
        rec_qty=best['moq']; rec_cost=round(rec_qty*best['price'],2)
    items.append({**p,"total_stock":total,"sold_60d":sold,"daily_demand":daily,"days_cover":cover,"status":status,
                  "best_supplier":best["supplier"] if best else "—","price":best["price"] if best else 0,"lead":best["lead"] if best else 0,"moq":best["moq"] if best else 0,
                  "rec_qty":rec_qty,"rec_cost":rec_cost,
                  "stock_by_loc":{loc:stock_detail[sku].get(loc,0) for loc in locations},
                  "suppliers":sup_by_sku.get(sku,[])})
items_sorted=sorted(items, key=lambda x:(x['days_cover'], -x['daily_demand']))
# location-level detail (the real problem: imbalance across stores)
loc_items=[]
for r in inventory:
    sku=r['sku']; loc=r['location']; st=int(r['stock']); sold=sold_by_sku_loc.get((sku,loc),0); daily=round(sold/DAYS,2) if sold else 0
    cover=round(st/daily,1) if daily>0 else 999
    status="Out of Stock" if st==0 else ("Low Stock" if st<=10 else "In Stock")
    loc_items.append({"sku":sku,"product":prod.get(sku,{}).get('product_name',''),"model":prod.get(sku,{}).get('machine_model',''),"category":prod.get(sku,{}).get('category',''),"location":loc,"stock":st,"sold_60d":sold,"daily_demand":daily,"days_cover":cover,"status":status})
loc_items_sorted=sorted(loc_items, key=lambda x:(x['stock'], -x['daily_demand']))
for i in items:
    mine=[l for l in loc_items if l['sku']==i['sku']]
    i['loc_out']=sum(1 for l in mine if l['stock']==0); i['loc_low']=sum(1 for l in mine if 1<=l['stock']<=10)
# transfer recommendations: donor (WH / surplus) -> empty/low store
transfers=[]
for l in loc_items:
    if l['location'].endswith('WH'): continue
    if l['stock']<=3 and l['daily_demand']>0:
        donors=sorted([x for x in loc_items if x['sku']==l['sku'] and x['location']!=l['location']], key=lambda x:-x['stock'])
        d=donors[0] if donors else None
        if d and d['stock']>10:
            qty=int(min(d['stock']-5, max(5, round(l['daily_demand']*14))))
            if qty>0: transfers.append({"sku":l['sku'],"product":l['product'],"from_loc":d['location'],"from_stock":d['stock'],"to_loc":l['location'],"to_stock":l['stock'],"qty":qty,"daily_demand":l['daily_demand']})
transfers=sorted(transfers, key=lambda x:-x['daily_demand'])[:30]

# KPI at sku-location level
loc_rows=inventory
out_loc=sum(1 for r in loc_rows if int(r['stock'])==0)
low_loc=sum(1 for r in loc_rows if 1<=int(r['stock'])<=10)
avail_loc=sum(1 for r in loc_rows if int(r['stock'])>10)
out_sku=sum(1 for i in items if i['status']=="Out of Stock")
low_sku=sum(1 for i in items if i['status'] in ("Low Stock","Critical"))
in_sku=sum(1 for i in items if i['status']=="In Stock")
total_units=sum(stock_by_sku.values())
inv_value=sum(i['total_stock']*i['price'] for i in items)
cat_stock=collections.defaultdict(int)
for i in items: cat_stock[i['category']]+=i['total_stock']

requests=[]
for po in pos:
    sku=po['sku']; p=prod.get(sku,{})
    sup_price=next((s['price'] for s in sup_by_sku.get(sku,[]) if s['supplier']==po['supplier']), items[[x['sku'] for x in items].index(sku)]['price'] if sku in prod else 0)
    status_map={"Open":"Pending","Confirmed":"Pending","Received":"Approved"}
    requests.append({"id":po['po'],"sku":sku,"product":p.get('product_name',sku),"category":p.get('category','—'),"model":p.get('machine_model','—'),
                     "supplier":po['supplier'],"qty":int(po['qty']),"expected":po['expected_date'],"status":status_map.get(po['status'],"Pending"),"po_status":po['status'],
                     "cost":round(int(po['qty'])*float(sup_price),2) if sup_price else 0,"source":"Purchase Order"})
# add AI reorder requests not already in pending POs
pending_skus={r['sku'] for r in requests if r['status']=="Pending"}
rid=5001
for i in items_sorted:
    if i['status'] in ("Critical","Out of Stock","Low Stock") and i['sku'] not in pending_skus and i['rec_qty']>0:
        requests.append({"id":f"REQ-{rid}","sku":i['sku'],"product":i['product_name'],"category":i['category'],"model":i['machine_model'],
                         "supplier":i['best_supplier'],"qty":i['rec_qty'],"expected":"—","status":"Pending","po_status":"AI Recommended",
                         "cost":i['rec_cost'],"source":"AI Recommendation"}); rid+=1
        if rid>5025: break

DATA={"items":items,"items_sorted":items_sorted,"loc_items":loc_items_sorted,"transfers":transfers,"locations":locations,"stock_by_loc":dict(stock_by_loc),"sold_by_loc":dict(sold_by_loc),
      "cat_stock":dict(cat_stock),"sold_by_cat":dict(sold_by_cat),"requests":requests,"pos":pos,
      "kpi":{"total_sku":len(products),"total_units":total_units,"inv_value":round(inv_value),"avail_loc":avail_loc,"low_loc":low_loc,"out_loc":out_loc,
             "in_sku":in_sku,"low_sku":low_sku,"out_sku":out_sku,"open_po":sum(1 for r in pos if r['status'] in ('Open','Confirmed'))}}

html = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spare Parts Desk — Kaveri Spares & Hydraulics</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Arial,sans-serif;background:#f4f6fb;color:#17233b}
a{color:#2563eb}.layout{display:flex;min-height:100vh}
.sidebar{width:250px;background:#0f2044;color:#fff;padding:22px 16px;position:fixed;height:100vh;overflow:auto}
.logo{font-size:22px;font-weight:900;line-height:1.1}.logo span{color:#ffb020}.sub{color:#a9b8d8;font-size:12px;margin:8px 0 20px;line-height:1.5}
.nav button{display:flex;gap:10px;width:100%;background:transparent;border:0;color:#dbe6ff;padding:12px 12px;border-radius:10px;cursor:pointer;font-size:14px;text-align:left;margin:3px 0}
.nav button.active,.nav button:hover{background:#1d3a78;color:#fff}
.badge{margin-left:auto;background:#ff4757;color:#fff;font-size:11px;padding:2px 7px;border-radius:20px}
.main{margin-left:250px;flex:1;padding:22px 26px 40px;max-width:1600px}
.top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:16px}
h1{margin:0;font-size:26px}h2{margin:4px 0 12px}h3{margin:0 0 8px}
.muted{color:#68779a;font-size:13px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}
.card{background:#fff;border-radius:16px;padding:18px;box-shadow:0 4px 20px rgba(15,32,68,.06);border:1px solid #e6ebf5}
.card b{font-size:30px;display:block;margin:6px 0}.card small{color:#68779a}
.green{color:#0a9d62}.orange{color:#e67e00}.red{color:#e03131}.blue{color:#2563eb}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid3{display:grid;grid-template-columns:1.2fr .8fr;gap:14px}
.panel{background:#fff;border-radius:16px;padding:18px;box-shadow:0 4px 20px rgba(15,32,68,.06);border:1px solid #e6ebf5;margin-bottom:14px}
table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:#68779a;font-weight:700;padding:10px 8px;border-bottom:1px solid #e6ebf5;white-space:nowrap}td{padding:10px 8px;border-bottom:1px solid #eef1f8;vertical-align:top}
.pill{display:inline-block;padding:4px 9px;border-radius:20px;font-size:11px;font-weight:800}.p-in{background:#e6f7ef;color:#087f4d}.p-low{background:#fff3d6;color:#9a6200}.p-crit{background:#ffe1e1;color:#b42318}.p-out{background:#17233b;color:#fff}.p-pend{background:#e8efff;color:#1d4ed8}.p-app{background:#e6f7ef;color:#087f4d}.p-rej{background:#ffe1e1;color:#b42318}
input,select,textarea{padding:10px 12px;border:1px solid #d6deee;border-radius:10px;font-size:14px;background:#fff}
.btn{background:#2563eb;color:#fff;border:0;padding:10px 16px;border-radius:10px;cursor:pointer;font-weight:700}.btn:hover{background:#1d4ed8}.btn.ghost{background:#fff;color:#2563eb;border:1px solid #c7d4f5}.btn.greenb{background:#0a9d62}.btn.redb{background:#e03131}.btn.small{padding:7px 11px;font-size:12px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}.toolbar input{flex:1;min-width:200px}
.page{display:none}.page.active{display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;margin-top:10px}.dot{width:11px;height:11px;border-radius:50%;display:inline-block;margin-right:6px}
.chat{height:420px;overflow:auto;background:#f8faff;border:1px solid #e6ebf5;border-radius:14px;padding:14px}
.msg{max-width:85%;padding:11px 13px;border-radius:14px;margin:8px 0;line-height:1.55;font-size:14px;white-space:pre-wrap}.msg.ai{background:#fff;border:1px solid #e6ebf5}.msg.user{background:#2563eb;color:#fff;margin-left:auto}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.chip{background:#eef3ff;border:1px solid #c7d4f5;padding:7px 11px;border-radius:20px;cursor:pointer;font-size:12px}
.rec{border-left:5px solid #e03131;background:#fff7f7;padding:13px;border-radius:10px;margin:10px 0}.rec.low{border-color:#e67e00;background:#fffaf0}.rec.good{border-color:#0a9d62;background:#f3fbf7}
.progress{height:8px;background:#eef1f8;border-radius:10px;overflow:hidden}.bar{height:100%}
footer{color:#8a97b3;font-size:12px;text-align:center;margin-top:20px}
@media(max-width:900px){.sidebar{position:relative;width:100%;height:auto}.layout{flex-direction:column}.main{margin:0}.cards,.grid2,.grid3{grid-template-columns:1fr}}
</style></head>
<body><div class="layout">
<aside class="sidebar"><div class="logo">⚙️ Spare Parts <span>Desk</span></div><div class="sub">Kaveri Spares &amp; Hydraulics<br>Stock snapshot: 16 Nov 2026 • Sales: 17 Sep – 15 Nov 2026 (60 days)<br>6 stores + 2 warehouses</div>
<div class="nav">
<button class="active" onclick="showPage('dashboard',this)">📊 Dashboard</button>
<button onclick="showPage('inventory',this)">📦 Inventory <span class="badge" id="navLow"></span></button>
<button onclick="showPage('ai',this)">🤖 AI Assistant &amp; Recommendations</button>
<button onclick="showPage('requests',this)">✅ Requests &amp; Approvals <span class="badge" id="navReq"></span></button>
<button onclick="showPage('suppliers',this)">🏭 Suppliers &amp; Orders</button>
</div>
<div style="margin-top:22px;background:#162d5e;padding:13px;border-radius:12px;font-size:12px;line-height:1.6"><b>How stock health works</b><br>• In Stock: &gt;21 days cover<br>• Low: 7–21 days cover<br>• Critical: &lt;7 days cover<br>• Out: zero stock<br><span style="color:#a9b8d8">Days cover = total stock ÷ avg daily sales (60d)</span></div>
</aside>

<main class="main">
<div class="top"><div><h1 id="pageTitle">Dashboard</h1><div class="muted">Available, low &amp; out-of-stock visibility across all locations — powered by your real dataset</div></div><div><button class="btn ghost" onclick="exportCSV()">⬇ Export Inventory CSV</button> <button class="btn" onclick="showPage('requests',document.querySelectorAll('.nav button')[3])">Review Requests →</button></div></div>

<!-- DASHBOARD -->
<section id="dashboard" class="page active">
<div class="cards">
<div class="card"><small>📦 TOTAL PRODUCTS (SKUs)</small><b id="kSku"></b><small>Across 8 categories • 8 machine models</small></div>
<div class="card"><small>✅ AVAILABLE STOCK</small><b class="green" id="kAvail"></b><small id="kUnits"></small></div>
<div class="card"><small>⚠️ LOW STOCK (1–10 units)</small><b class="orange" id="kLow"></b><small>SKU-location slots at risk</small></div>
<div class="card"><small>🔴 OUT OF STOCK (0 units)</small><b class="red" id="kOut"></b><small id="kOutLoc"></small></div>
<div class="card"><small>💰 INVENTORY VALUE (at best price)</small><b class="blue" id="kVal"></b><small>Cheapest supplier price × stock</small></div>
<div class="card"><small>🧾 OPEN PURCHASE ORDERS</small><b id="kPO"></b><small>Open + Confirmed • awaiting receipt</small></div>
<div class="card"><small>⏳ PENDING APPROVALS</small><b class="orange" id="kPend"></b><small>Requests waiting for your decision</small></div>
<div class="card"><small>🏬 LOCATIONS TRACKED</small><b>8</b><small>Gokak, Belgaum, Hubli, Dharwad, Bijapur, Bagalkot + 2 WH</small></div>
</div>

<div class="grid3">
<div class="panel"><h3>🥧 Pie Chart — Stock Health (1,008 SKU × Location slots)</h3><div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap"><div id="pie1"></div><div id="pie1Legend" class="legend" style="flex-direction:column;gap:8px"></div></div><p class="muted">Available &gt;10 units • Low 1–10 units • Out = 0 units. This shows the real problem: stock exists, but not always at the right store.</p></div>
<div class="panel"><h3>🍩 Stock by Category (units)</h3><div id="pie2"></div><div id="pie2Legend" class="legend"></div></div>
</div>

<div class="grid2">
<div class="panel"><h3>🏬 Stock by Location (units)</h3><div id="locBars"></div></div>
<div class="panel"><h3>🔥 Top 10 Fast-Moving Parts (sold in 60 days)</h3><table><thead><tr><th>SKU</th><th>Product</th><th>Sold</th><th>Stock</th><th>Cover</th><th>Status</th></tr></thead><tbody id="fastBody"></tbody></table></div>
</div>

<div class="panel"><h3>🚨 Urgent Attention — Empty / Lowest Stock Locations</h3><p class="muted">Store-level shortages (sorted by local demand). Stock may be available at a warehouse or another store — see Transfer Recommendations in the AI page.</p><table><thead><tr><th>SKU</th><th>Product</th><th>Location</th><th>Stock</th><th>Local Demand</th><th>Status</th><th>Action</th></tr></thead><tbody id="urgentBody"></tbody></table></div>
</section>

<!-- INVENTORY -->
<section id="inventory" class="page">
<div class="panel"><h2>📦 Inventory — All Product Details</h2><p class="muted">126 products • Click a row's “Locations” to see stock at every store &amp; warehouse. Filter, search and sort instantly.</p>
<div class="toolbar"><input id="q" placeholder="Search SKU, product, model…" oninput="renderInv()"><select id="fCat" onchange="renderInv()"><option value="">All Categories</option></select><select id="fModel" onchange="renderInv()"><option value="">All Machine Models</option></select><select id="fStatus" onchange="renderInv()"><option value="">All Status</option><option>In Stock</option><option>Low Stock</option><option>Critical</option><option>Out of Stock</option></select><select id="sortBy" onchange="renderInv()"><option value="cover">Sort: Lowest Cover</option><option value="stockAsc">Stock: Low → High</option><option value="stockDesc">Stock: High → Low</option><option value="demand">Demand: High → Low</option><option value="name">Name A–Z</option></select></div>
<div class="muted" id="invCount"></div><div style="overflow:auto;max-height:640px"><table><thead><tr><th>SKU</th><th>Product</th><th>Machine Model</th><th>Category</th><th>Total Stock</th><th>Sold 60d</th><th>Daily Demand</th><th>Days Cover</th><th>Status</th><th>Best Supplier (₹ / Lead)</th><th></th></tr></thead><tbody id="invBody"></tbody></table></div></div>
</section>

<!-- AI -->
<section id="ai" class="page">
<div class="grid2">
<div class="panel"><h2>🤖 AI Assistant</h2><p class="muted">Ask in plain English — I query your live inventory, sales &amp; supplier data. Try the quick questions below.</p>
<div class="chips"><span class="chip" onclick="askQuick(this)">Which items are out of stock?</span><span class="chip" onclick="askQuick(this)">What should I reorder first?</span><span class="chip" onclick="askQuick(this)">Show low stock belts</span><span class="chip" onclick="askQuick(this)">Cheapest supplier for BLT-1003?</span><span class="chip" onclick="askQuick(this)">Which location has lowest stock?</span><span class="chip" onclick="askQuick(this)">Top selling products</span></div>
<div class="chat" id="chat"></div>
<div style="display:flex;gap:8px;margin-top:10px"><input id="chatIn" style="flex:1" placeholder="Ask: stock of BRG-1000, low stock filters, supplier for HYD-…, reorder advice…" onkeydown="if(event.key==='Enter')sendChat()"><button class="btn" onclick="sendChat()">Send ➤</button></div><p class="muted">Tip: mention any SKU (e.g. FLT-1001), category (Belts, Filters…), location (Hubli, Belgaum WH…) or words like “reorder”, “cheapest”, “out of stock”.</p></div>
<div class="panel"><h2>💡 AI Recommendations</h2><p class="muted">Auto-generated reorder plan: quantity covers lead time + 14 safety days, rounded up to supplier MOQ. Sorted by urgency.</p><div id="recSummary"></div><div id="recList" style="max-height:720px;overflow:auto"></div></div>
</div></section>

<!-- REQUESTS -->
<section id="requests" class="page">
<div class="cards" style="grid-template-columns:repeat(4,1fr)"><div class="card"><small>⏳ PENDING</small><b class="orange" id="rPend"></b></div><div class="card"><small>✅ APPROVED</small><b class="green" id="rApp"></b></div><div class="card"><small>❌ REJECTED</small><b class="red" id="rRej"></b></div><div class="card"><small>💰 PENDING VALUE</small><b class="blue" id="rVal"></b></div></div>
<div class="panel"><h2>➕ Create New Request</h2><div style="display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:10px"><select id="nrSku"></select><input id="nrQty" type="number" min="1" placeholder="Qty"><input id="nrNote" placeholder="Note / reason (optional)"><button class="btn" onclick="createRequest()">Create Request</button></div><p class="muted">Supplier, price &amp; cost auto-fill from the cheapest supplier for that SKU. New requests start as <b>Pending</b>.</p></div>
<div class="panel"><h2>✅ Requests — Approve / Reject Required Items</h2><div class="toolbar"><select id="rFilter" onchange="renderReq()"><option value="">All Requests</option><option>Pending</option><option>Approved</option><option>Rejected</option></select><select id="rSource" onchange="renderReq()"><option value="">All Sources</option><option>Purchase Order</option><option>AI Recommendation</option><option>Manual</option></select><input id="rQ" placeholder="Search SKU / product / supplier…" oninput="renderReq()"></div>
<table><thead><tr><th>Request</th><th>Product</th><th>Supplier</th><th>Qty</th><th> Est. Cost</th><th>Expected</th><th>Source</th><th>Status</th><th>Decision</th></tr></thead><tbody id="reqBody"></tbody></table><p class="muted">Approving/rejecting updates counts instantly and is saved in your browser (localStorage), so decisions survive a refresh on this device.</p></div>
</section>

<!-- SUPPLIERS -->
<section id="suppliers" class="page">
<div class="grid2"><div class="panel"><h2>🏭 Purchase Orders (43)</h2><table><thead><tr><th>PO</th><th>Supplier</th><th>SKU</th><th>Qty</th><th>Expected</th><th>Status</th></tr></thead><tbody id="poBody"></tbody></table></div>
<div class="panel"><h2>💲 Best Supplier per Product</h2><p class="muted">Cheapest price wins; lead time &amp; MOQ shown. Full 205 supplier offers are used by the AI for every recommendation.</p><div style="max-height:600px;overflow:auto"><table><thead><tr><th>SKU</th><th>Product</th><th>Best Supplier</th><th>Price ₹</th><th>Lead</th><th>MOQ</th><th>Options</th></tr></thead><tbody id="supBody"></tbody></table></div></div></div>
</section>

<footer>Kaveri Spares &amp; Hydraulics • Spare Parts Desk • Built from inventory.csv, products.csv, sales.csv, suppliers.csv, purchase_orders.csv • Snapshot 16 Nov 2026</footer>
</main></div>
<script>
const DATA=__DATA__;
let requests=JSON.parse(localStorage.getItem('spd_requests')||'null')||DATA.requests;
let invExpanded=null;
const fmt=n=>Number(n).toLocaleString('en-IN');
const inr=n=>'₹'+Number(n).toLocaleString('en-IN',{maximumFractionDigits:0});
function pill(s){return s==='In Stock'?'<span class="pill p-in">● In Stock</span>':s==='Low Stock'?'<span class="pill p-low">● Low Stock</span>':s==='Critical'?'<span class="pill p-crit">● Critical</span>':'<span class="pill p-out">● Out of Stock</span>'}
function rpill(s){return s==='Pending'?'<span class="pill p-pend">⏳ Pending</span>':s==='Approved'?'<span class="pill p-app">✅ Approved</span>':'<span class="pill p-rej">❌ Rejected</span>'}
function showPage(id,btn){document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active'));if(btn)btn.classList.add('active');document.getElementById('pageTitle').textContent={dashboard:'Dashboard',inventory:'Inventory',ai:'AI Assistant & Recommendations',requests:'Requests & Approvals',suppliers:'Suppliers & Orders'}[id];window.scrollTo(0,0)}
function saveReq(){localStorage.setItem('spd_requests',JSON.stringify(requests))}
// KPIs
const K=DATA.kpi;
kSku.textContent=K.total_sku; kAvail.textContent=fmt(K.avail_loc)+' slots'; kUnits.textContent=fmt(K.total_units)+' total units in stock'; kLow.textContent=fmt(K.low_loc)+' slots'; kOut.textContent=fmt(K.out_loc)+' slots'; kOutLoc.textContent=`Across ${new Set(DATA.loc_items.filter(l=>l.stock===0).map(l=>l.sku)).size} different SKUs • total network stock still ${fmt(K.total_units)} units — a distribution problem`; kVal.textContent=inr(K.inv_value); kPO.textContent=K.open_po;
function refreshBadges(){let p=requests.filter(r=>r.status==='Pending').length;kPend.textContent=p;rPend.textContent=p;navReq.textContent=p;navLow.textContent=K.low_loc+K.out_loc;rApp.textContent=requests.filter(r=>r.status==='Approved').length;rRej.textContent=requests.filter(r=>r.status==='Rejected').length;rVal.textContent=inr(requests.filter(r=>r.status==='Pending').reduce((a,r)=>a+r.cost,0))}
// PIE (SVG donut)
function donut(el,legendEl,data,colors){let total=data.reduce((a,d)=>a+d.v,0),a0=-Math.PI/2,paths='',cx=110,cy=110,r=82,r2=52;data.forEach((d,i)=>{let frac=total?d.v/total:0,a1=a0+frac*Math.PI*2;let large=frac>.5?1:0;let x0=cx+r*Math.cos(a0),y0=cy+r*Math.sin(a0),x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1),xi1=cx+r2*Math.cos(a1),yi1=cy+r2*Math.sin(a1),xi0=cx+r2*Math.cos(a0),yi0=cy+r2*Math.sin(a0);if(frac>0.001)paths+=`<path d="M${x0} ${y0} A${r} ${r} 0 ${large} 1 ${x1} ${y1} L${xi1} ${yi1} A${r2} ${r2} 0 ${large} 0 ${xi0} ${yi0} Z" fill="${colors[i]}" stroke="#fff" stroke-width="2"><title>${d.label}: ${d.v} (${(frac*100).toFixed(1)}%)</title></path>`;a0=a1});el.innerHTML=`<svg width="220" height="220" viewBox="0 0 220 220">${paths}<text x="110" y="106" text-anchor="middle" font-weight="900" font-size="20">${fmt(total)}</text><text x="110" y="126" text-anchor="middle" fill="#68779a" font-size="11">total</text></svg>`;legendEl.innerHTML=data.map((d,i)=>`<span><span class="dot" style="background:${colors[i]}"></span>${d.label}: <b>${fmt(d.v)}</b> (${total?(d.v/total*100).toFixed(1):0}%)</span>`).join('')}
donut(pie1,pie1Legend,[{label:'Available (>10)',v:K.avail_loc},{label:'Low Stock (1–10)',v:K.low_loc},{label:'Out of Stock (0)',v:K.out_loc}],['#0a9d62','#f5a623','#e03131']);
let catData=Object.entries(DATA.cat_stock).sort((a,b)=>b[1]-a[1]).map(([label,v])=>({label,v}));donut(pie2,pie2Legend,catData,['#2563eb','#0a9d62','#f5a623','#e03131','#7c3aed','#0891b2','#db2777','#65a30d']);
// Location bars
locBars.innerHTML=DATA.locations.map(loc=>{let v=DATA.stock_by_loc[loc]||0,mx=Math.max(...Object.values(DATA.stock_by_loc));return `<div style="margin:9px 0"><div style="display:flex;justify-content:space-between;font-size:13px"><span>${loc}</span><b>${fmt(v)} units</b></div><div class="progress"><div class="bar" style="width:${v/mx*100}%;background:#2563eb"></div></div></div>`}).join('');
// fast + urgent
let fast=[...DATA.items].sort((a,b)=>b.sold_60d-a.sold_60d).slice(0,10);fastBody.innerHTML=fast.map(i=>`<tr><td><b>${i.sku}</b></td><td>${i.product_name}</td><td>${i.sold_60d}</td><td>${i.total_stock}</td><td>${i.days_cover>900?'∞':i.days_cover+'d'}</td><td>${pill(i.status)}</td></tr>`).join('');
function urgentRows(list){return list.map(i=>`<tr><td><b>${i.sku}</b></td><td>${i.product_name}<br><span class="muted">${i.machine_model}</span></td><td>${i.category}</td><td>${i.total_stock}</td><td>${i.daily_demand}/day</td><td>${i.days_cover>900?'∞':i.days_cover+' days'}</td><td>${pill(i.status)}</td><td><button class="btn small" onclick="quickRequest('${i.sku}')">Request</button></td></tr>`).join('')}
urgentBody.innerHTML=DATA.loc_items.slice(0,12).map(l=>`<tr><td><b>${l.sku}</b></td><td>${l.product}<br><span class='muted'>${l.model}</span></td><td>${l.location}</td><td><b>${l.stock}</b></td><td>${l.daily_demand}/day (${l.sold_60d} in 60d)</td><td>${pill(l.status)}</td><td><button class='btn small' onclick="quickRequest('${l.sku}')">Request</button></td></tr>`).join('');
// INVENTORY
let cats=[...new Set(DATA.items.map(i=>i.category))],models=[...new Set(DATA.items.map(i=>i.machine_model))];fCat.innerHTML+=[...cats].sort().map(c=>`<option>${c}</option>`).join('');fModel.innerHTML+=models.sort().map(m=>`<option>${m}</option>`).join('');nrSku.innerHTML=DATA.items.map(i=>`<option value="${i.sku}">${i.sku} — ${i.product_name} (${i.machine_model}) • Stock ${i.total_stock}</option>`).join('');
function renderInv(){let qy=q.value.toLowerCase(),list=DATA.items.filter(i=>(!qy||(i.sku+' '+i.product_name+' '+i.machine_model+' '+i.category).toLowerCase().includes(qy))&&(!fCat.value||i.category===fCat.value)&&(!fModel.value||i.machine_model===fModel.value)&&(!fStatus.value||i.status===fStatus.value));let s=sortBy.value;list.sort((a,b)=>s==='cover'?a.days_cover-b.days_cover:s==='stockAsc'?a.total_stock-b.total_stock:s==='stockDesc'?b.total_stock-a.total_stock:s==='demand'?b.daily_demand-a.daily_demand:a.product_name.localeCompare(b.product_name));invCount.textContent=`Showing ${list.length} of 126 products`;invBody.innerHTML=list.map(i=>`<tr><td><b>${i.sku}</b></td><td>${i.product_name}</td><td>${i.machine_model}</td><td>${i.category}</td><td><b>${i.total_stock}</b><br><span class='muted'>${i.loc_out} loc out • ${i.loc_low} low</span></td><td>${i.sold_60d}</td><td>${i.daily_demand}</td><td>${i.days_cover>900?'∞':i.days_cover+'d'}</td><td>${pill(i.status)}</td><td>${i.best_supplier}<br><span class="muted">${inr(i.price)} • ${i.lead}d • MOQ ${i.moq}</span></td><td><button class="btn ghost small" onclick="toggleLoc('${i.sku}')">Locations ▾</button></td></tr>${invExpanded===i.sku?`<tr><td colspan="11" style="background:#f8faff">🏬 ${DATA.locations.map(l=>`${l}: <b>${i.stock_by_loc[l]}</b>`).join(' &nbsp;|&nbsp; ')}<br><span class="muted">Suppliers: ${i.suppliers.map(s=>`${s.supplier} — ${inr(s.price)}, ${s.lead}d, MOQ ${s.moq}`).join(' | ')}</span></td></tr>`:''}`).join('')||'<tr><td colspan="11">No products match your filters.</td></tr>'}
function toggleLoc(sku){invExpanded=invExpanded===sku?null:sku;renderInv()}
renderInv();
// RECOMMENDATIONS
let recs=DATA.items_sorted.filter(i=>i.rec_qty>0);
recSummary.innerHTML=`<div class="rec"><b>${recs.length} products need reorder</b> • Estimated cost <b>${inr(recs.reduce((a,i)=>a+i.rec_cost,0))}</b><br><span class="muted">Critical first. Click “Create Request” to send any item to Approvals.</span></div>`;
recList.innerHTML=(DATA.transfers&&DATA.transfers.length?`<h3 style='margin:14px 0 6px'>🔀 Stock Transfer Recommendations (move stock, don't buy)</h3>`+DATA.transfers.slice(0,10).map(tr=>`<div class='rec good'><b>${tr.sku} — ${tr.product}</b><br>Move <b>${tr.qty} units</b>: <b>${tr.from_loc}</b> (has ${tr.from_stock}) → <b>${tr.to_loc}</b> (only ${tr.to_stock} left, demand ${tr.daily_demand}/day)</div>`).join(''):'')+`<h3 style='margin:16px 0 6px'>🛒 Purchase / Reorder Recommendations</h3>`+recs.map(i=>`<div class="rec ${i.status==='Low Stock'?'low':''}"><b>${i.sku} — ${i.product_name}</b> ${pill(i.status)}<br><span class="muted">${i.machine_model} • ${i.category} • Stock ${i.total_stock} • Demand ${i.daily_demand}/day • Cover ${i.days_cover>900?'∞':i.days_cover+' days'}</span><br>➡️ Order <b>${i.rec_qty} units</b> from <b>${i.best_supplier}</b> @ ${inr(i.price)} = <b>${inr(i.rec_cost)}</b> • Lead ${i.lead} days, MOQ ${i.moq}<br><button class="btn small" style="margin-top:7px" onclick="quickRequest('${i.sku}')">+ Create Request</button></div>`).join('');
// REQUESTS
function renderReq(){let list=requests.filter(r=>(!rFilter.value||r.status===rFilter.value)&&(!rSource.value||r.source===rSource.value)&&(!rQ.value||(r.id+' '+r.sku+' '+r.product+' '+r.supplier).toLowerCase().includes(rQ.value.toLowerCase())));reqBody.innerHTML=list.map(r=>`<tr><td><b>${r.id}</b><br><span class="muted">${r.sku}</span></td><td>${r.product}<br><span class="muted">${r.model} • ${r.category}</span></td><td>${r.supplier}</td><td>${r.qty}</td><td>${inr(r.cost)}</td><td>${r.expected}</td><td>${r.source}<br><span class="muted">${r.po_status}</span></td><td>${rpill(r.status)}</td><td>${r.status==='Pending'?`<button class="btn greenb small" onclick="decide('${r.id}','Approved')">✓ Approve</button> <button class="btn redb small" onclick="decide('${r.id}','Rejected')">✕ Reject</button>`:`<button class="btn ghost small" onclick="decide('${r.id}','Pending')">↩ Reopen</button>`}</td></tr>`).join('')||'<tr><td colspan="9">No requests match.</td></tr>';refreshBadges()}
function decide(id,st){let r=requests.find(x=>x.id===id);if(r){r.status=st;saveReq();renderReq();addChat(`Request ${id} (${r.sku} — ${r.product}) marked as ${st}.`,'ai')}}
function quickRequest(sku){let i=DATA.items.find(x=>x.sku===sku);if(!i)return;let ex=requests.find(r=>r.sku===sku&&r.status==='Pending');if(ex){alert('A pending request already exists: '+ex.id);showPage('requests',document.querySelectorAll('.nav button')[3]);return}requests.unshift({id:'REQ-'+(5000+requests.filter(r=>String(r.id).startsWith('REQ')).length+1),sku,product:i.product_name,category:i.category,model:i.machine_model,supplier:i.best_supplier,qty:i.rec_qty||i.moq,expected:'—',status:'Pending',po_status:'Manual',cost:(i.rec_qty||i.moq)*i.price,source:'Manual'});saveReq();renderReq();showPage('requests',document.querySelectorAll('.nav button')[3])}
function createRequest(){let sku=nrSku.value,i=DATA.items.find(x=>x.sku===sku),qty=parseInt(nrQty.value)||i.rec_qty||i.moq;requests.unshift({id:'REQ-'+(5000+requests.filter(r=>String(r.id).startsWith('REQ')).length+1),sku,product:i.product_name,category:i.category,model:i.machine_model,supplier:i.best_supplier,qty,expected:'—',status:'Pending',po_status:nrNote.value||'Manual',cost:qty*i.price,source:'Manual'});saveReq();renderReq();nrQty.value='';nrNote.value='';alert('Request created and added as Pending ✓')}
renderReq();
// SUPPLIERS
poBody.innerHTML=DATA.pos.map(p=>`<tr><td><b>${p.po}</b></td><td>${p.supplier}</td><td>${p.sku}</td><td>${p.qty}</td><td>${p.expected_date}</td><td>${p.status}</td></tr>`).join('');
supBody.innerHTML=DATA.items.map(i=>`<tr><td><b>${i.sku}</b></td><td>${i.product_name}</td><td>${i.best_supplier}</td><td>${inr(i.price)}</td><td>${i.lead}d</td><td>${i.moq}</td><td>${i.suppliers.length}</td></tr>`).join('');
// AI CHAT
function addChat(t,who='ai'){let d=document.createElement('div');d.className='msg '+who;d.textContent=t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
function askQuick(el){chatIn.value=el.textContent;sendChat()}
function findSKU(text){let m=text.toUpperCase().match(/[A-Z]{3}-\d{4}/);return m?DATA.items.find(i=>i.sku===m[0]):null}
function sendChat(){let text=chatIn.value.trim();if(!text)return;addChat(text,'user');chatIn.value='';let t=text.toLowerCase(),sku=findSKU(text),reply='';
if(sku){reply=`${sku.sku} — ${sku.product_name} (${sku.machine_model}, ${sku.category})\n• Total stock: ${sku.total_stock} units across 8 locations\n• Sold (60d): ${sku.sold_60d} • Demand: ${sku.daily_demand}/day • Cover: ${sku.days_cover>900?'∞':sku.days_cover+' days'} • Status: ${sku.status}\n• Location stock: ${DATA.locations.map(l=>l+': '+sku.stock_by_loc[l]).join(', ')}\n• Best supplier: ${sku.best_supplier} @ ${inr(sku.price)}, lead ${sku.lead} days, MOQ ${sku.moq}`;if(sku.rec_qty)reply+=`\n• 💡 Recommendation: order ${sku.rec_qty} units (${inr(sku.rec_cost)}). Use the Request button in Recommendations.`}
else if(t.includes('out of stock')){let l=DATA.loc_items.filter(i=>i.stock===0);reply=`🔴 ${l.length} SKU-location slots are at ZERO stock:\n`+l.slice(0,15).map(i=>`• ${i.sku} ${i.product} at ${i.location} (local demand ${i.daily_demand}/day)`).join('\n')+`\n\nNo SKU is zero across the whole network — check Transfers in Recommendations to move stock from warehouses/surplus stores first.`}
else if(t.includes('reorder')||t.includes('order first')||t.includes('recommend')){reply=`💡 Reorder first (lowest cover):\n`+recs.slice(0,8).map((i,x)=>`${x+1}. ${i.sku} ${i.product_name} — stock ${i.total_stock}, cover ${i.days_cover}d → order ${i.rec_qty} from ${i.best_supplier} (${inr(i.rec_cost)})`).join('\n')+`\n\nSee the full plan in AI Recommendations →`}
else if(t.includes('low stock')){let cat=cats.find(c=>t.includes(c.toLowerCase().split(' ')[0].toLowerCase()));let l=DATA.items.filter(i=>['Low Stock','Critical','Out of Stock'].includes(i.status)&&(!cat||i.category===cat));reply=`⚠️ ${l.length} low/critical/out items${cat?' in '+cat:''}:\n`+l.slice(0,12).map(i=>`• ${i.sku} ${i.product_name} — stock ${i.total_stock}, cover ${i.days_cover>900?'∞':i.days_cover+'d'} (${i.status})`).join('\n')}
else if(t.includes('cheapest')||t.includes('supplier')){reply=sku?`Cheapest for ${sku.sku}: ${sku.best_supplier} @ ${inr(sku.price)} (lead ${sku.lead}d, MOQ ${sku.moq}). All options: `+sku.suppliers.map(s=>`${s.supplier} ${inr(s.price)}/${s.lead}d`).join(', '):'Tell me a SKU, e.g. “Cheapest supplier for HYD-1042?” — I compare all 205 supplier offers on price + lead time.'}
else if(t.includes('location')||t.includes('warehouse')){reply=`🏬 Stock by location:\n`+DATA.locations.map(l=>`• ${l}: ${fmt(DATA.stock_by_loc[l])} units`).join('\n')+`\nLowest is ${Object.entries(DATA.stock_by_loc).sort((a,b)=>a[1]-b[1])[0][0]} — check location-wise zeros in Inventory → Locations.`}
else if(t.includes('top sell')||t.includes('fast')||t.includes('best sell')){reply=`🔥 Top sellers (60 days):\n`+fast.slice(0,8).map((i,x)=>`${x+1}. ${i.sku} ${i.product_name} — ${i.sold_60d} sold, stock ${i.total_stock}`).join('\n')}
else if(t.includes('pending')||t.includes('approval')||t.includes('request')){let p=requests.filter(r=>r.status==='Pending');reply=`⏳ ${p.length} requests pending approval worth ${inr(p.reduce((a,r)=>a+r.cost,0))}. Go to Requests & Approvals to Approve / Reject each item.`}
else{let cat=cats.find(c=>t.includes(c.toLowerCase()));if(cat){let l=DATA.items.filter(i=>i.category===cat);reply=`${cat}: ${l.length} products, ${fmt(l.reduce((a,i)=>a+i.total_stock,0))} units in stock, ${l.filter(i=>i.status!=='In Stock').length} need attention. Ask “low stock ${cat.toLowerCase()}” for details.`}else reply=`I can help with:\n• Any SKU — type e.g. “stock of BRG-1000”\n• “Which items are out of stock?”\n• “What should I reorder first?”\n• “Cheapest supplier for BLT-1003?”\n• “Top selling products” • “Which location has lowest stock?”\n• Category checks — “low stock filters”`}
setTimeout(()=>addChat(reply,'ai'),250)}
addChat(`👋 Hello! I'm your Spare Parts AI Assistant for Kaveri Spares & Hydraulics.\n\nRight now across 1,008 SKU-location slots: ${K.avail_loc} available, ${K.low_loc} low (1–10 units) and ${K.out_loc} out of stock. Network stock is ${fmt(K.total_units)} units — so most shortages can be fixed by transfers before buying.\n\nAsk me anything — try a SKU, “what should I reorder first?” or tap a quick question above.`,'ai');
// EXPORT
function exportCSV(){let rows=[['sku','product_name','machine_model','category','total_stock','sold_60d','daily_demand','days_cover','status','best_supplier','price_inr','lead_days','moq',...DATA.locations]];DATA.items.forEach(i=>rows.push([i.sku,i.product_name,i.machine_model,i.category,i.total_stock,i.sold_60d,i.daily_demand,i.days_cover>900?'':i.days_cover,i.status,i.best_supplier,i.price,i.lead,i.moq,...DATA.locations.map(l=>i.stock_by_loc[l])]));let csv=rows.map(r=>r.map(x=>`"${String(x).replaceAll('"','""')}"`).join(',')).join('\n');let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='spare-parts-inventory-export.csv';a.click()}
refreshBadges();
</script></body></html>
"""
html=html.replace("__DATA__", json.dumps(DATA))
open(OUT,"w").write(html)
print(f"Wrote {OUT} {len(html)} bytes")
print(DATA["kpi"])
print("recs", len([i for i in items if i['rec_qty']>0]), "requests", len(requests))
