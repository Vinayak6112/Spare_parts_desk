# Spare Parts Desk — Kaveri Spares & Hydraulics

Professional Spare Parts website built with **basic technologies only** — no frameworks, nothing to install.

| Layer | Technology |
|---|---|
| Backend / API | **Python 3** — standard library only (`http.server`), zero dependencies |
| Frontend | **HTML5 + CSS3 + JavaScript** (separate files) |
| Data | CSV files in `data/` — your exact provided datasets |
| Fonts | **Inter** everywhere (like the reference UI) via Google Fonts, with system-font fallback |

## Run (1 command)
```bash
cd spare-parts-website
python3 app.py
```
Open **http://localhost:8000**

## Structure
```
spare-parts-website/
├── app.py                  ← Python REST API + web server (run this)
├── README.md
├── data/
│   ├── inventory.csv  products.csv  sales.csv  suppliers.csv  purchase_orders.csv
│   └── requests.json       ← created automatically; Approve/Reject decisions are saved here
└── static/
    ├── index.html
    ├── css/style.css       ← professional design system
    └── js/app.js           ← all pages call the API with fetch()
```

## REST API (try in browser)
| Method | Endpoint | Use |
|---|---|---|
| GET | `/api/dashboard` | KPIs, pie-chart + location + category data |
| GET | `/api/inventory?search=&category=&status=&sort=` | Inventory (filter/search/sort) |
| GET | `/api/inventory/<SKU>` | One product, e.g. `/api/inventory/BLT-1003` |
| GET | `/api/recommendations` | AI transfer + reorder recommendations |
| GET/POST | `/api/requests` | List requests / create new request |
| PUT | `/api/requests/<id>` `{"status":"Approved"}` | **Approve / Reject** |
| POST | `/api/chat` `{"message":"..."}` | AI Assistant |
| GET | `/api/suppliers`, `/api/purchase-orders`, `/api/health` | Suppliers, POs, health check |

## Pages
Layout matches the reference screenshot: dark-navy sidebar, **SP** logo, and at the bottom
*"Your name (used for requests & approvals)"* — type your name once; it is recorded as
Requested-by / Decided-by on every action. **There is no sign-in / login anywhere** — every
page, including Recommendations, opens directly (URLs are hash routes like `#/recommendations`).

1. **Dashboard** (`#/dashboard`) — Available (586), Low (368), Out (54) stock, pie/donut charts, location bars, top sellers, urgent list
2. **Inventory** (`#/inventory`) — all 126 products with per-location stock, demand, cover, supplier
3. **Recommendations** (`#/recommendations`) — stock-transfer & reorder plan (separate page)
4. **AI Assistant** (`#/ai`) — chat answers from your live data (separate page)
5. **Requests** (`#/requests`) — Approve / Reject required items (permanently saved server-side) + 43 purchase orders & best-supplier table

## Business logic
- Stock health per SKU×Location (1,008 slots): Available >10, Low 1–10, Out = 0
- Demand = 60-day sales ÷ 60; Days cover = stock ÷ daily demand
- Reorder qty = covers lead time + 14 safety days, rounded up to supplier MOQ
- Transfers are suggested before buying: surplus warehouse/store → empty store
