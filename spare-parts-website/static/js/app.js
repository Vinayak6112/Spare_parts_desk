/* Spare Parts Desk — Frontend (JavaScript) | Talks ONLY to the Python REST API */
const $ = id => document.getElementById(id);
const fmt = n => Number(n).toLocaleString('en-IN');
const inr = n => '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
let ITEMS = [], REQUESTS = [];
const TITLES = { dashboard: 'Dashboard', inventory: 'Inventory', recommendations: 'Recommendations', ai: 'AI Assistant', requests: 'Requests' };
const SUBS = { dashboard: 'Available, low & out-of-stock visibility across 6 stores + 2 warehouses', inventory: 'Complete product details — stock at every store & warehouse', recommendations: 'Smart transfer & reorder suggestions from your data — no sign-in needed, just open and use', ai: 'Ask anything about stock, suppliers, demand and reorders', requests: 'Approve or reject required items — your name is recorded with every decision' };
const myName = () => ($('userName').value || '').trim();

async function api(path, options = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'API error');
  return r.json();
}
function toast(msg) { $('toast').textContent = msg; $('toast').classList.add('show'); setTimeout(() => $('toast').classList.remove('show'), 2600); }
function pill(s) { return s === 'In Stock' ? '<span class="pill p-in">● In Stock</span>' : s === 'Low Stock' ? '<span class="pill p-low">● Low Stock</span>' : s === 'Critical' ? '<span class="pill p-crit">● Critical</span>' : '<span class="pill p-out">● Out of Stock</span>'; }
function rPill(s) { return s === 'Pending' ? '<span class="pill p-pend">⏳ Pending</span>' : s === 'Approved' ? '<span class="pill p-app">✅ Approved</span>' : '<span class="pill p-rej">❌ Rejected</span>'; }

/* ---------- Navigation ---------- */
function showPage(name, push = true) {
  if (!TITLES[name]) name = 'dashboard';
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  $('page-' + name).classList.add('active');
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('active', b.dataset.page === name));
  $('pageTitle').textContent = TITLES[name]; $('pageSub').textContent = SUBS[name];
  if (push && location.hash !== '#/' + name) location.hash = '/' + name;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.addEventListener('hashchange', () => showPage(location.hash.replace('#/', '').replace('ai-assistant', 'ai') || 'dashboard', false));
document.querySelectorAll('#nav button').forEach(b => b.onclick = () => showPage(b.dataset.page));
document.querySelector('[data-goto]').onclick = () => showPage('requests');

/* ---------- Pie / Donut chart on Canvas (no libraries) ---------- */
function drawDonut(canvas, legendEl, data, colors) {
  const c = canvas.getContext('2d'), total = data.reduce((a, d) => a + d.value, 0);
  c.clearRect(0, 0, 250, 250); let a = -Math.PI / 2;
  data.forEach((d, i) => { const s = total ? d.value / total * Math.PI * 2 : 0; c.beginPath(); c.moveTo(125, 125); c.arc(125, 125, 104, a, a + s); c.closePath(); c.fillStyle = colors[i]; c.fill(); a += s; });
  c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.arc(125, 125, 57, 0, Math.PI * 2); c.fill();
  c.globalCompositeOperation = 'source-over'; c.fillStyle = '#17233b'; c.font = '800 21px Sora, Inter, sans-serif'; c.textAlign = 'center'; c.fillText(fmt(total), 125, 122);
  c.fillStyle = '#68779a'; c.font = '500 11px Inter, sans-serif'; c.fillText('TOTAL', 125, 142);
  legendEl.innerHTML = data.map((d, i) => `<span><i style="background:${colors[i]}"></i>${d.label}: <b>${fmt(d.value)}</b> (${total ? (d.value / total * 100).toFixed(1) : 0}%)</span>`).join('');
}

/* ---------- Your name (sidebar, like reference) — optional, NEVER a sign-in gate ---------- */
$('userName').value = localStorage.getItem('spd_name') || '';
$('userName').addEventListener('input', () => localStorage.setItem('spd_name', myName()));

/* ---------- Dashboard  (GET /api/dashboard) ---------- */
async function loadDashboard() {
  const d = await api('/api/dashboard'), K = d.kpi;
  const pend = d.pending_requests;
  $('kpiGrid').innerHTML = `
    <div class="kpi"><small>TOTAL PRODUCTS (SKUs)</small><b>${K.total_sku}</b><p>8 categories • 8 machine models</p></div>
    <div class="kpi green"><small>✅ AVAILABLE STOCK</small><b class="green">${fmt(K.avail_loc)} slots</b><p>${fmt(K.total_units)} total units in stock</p></div>
    <div class="kpi orange"><small>⚠️ LOW STOCK (1–10 units)</small><b class="orange">${fmt(K.low_loc)} slots</b><p>SKU-location slots at risk</p></div>
    <div class="kpi red"><small>🔴 OUT OF STOCK (0 units)</small><b class="red">${fmt(K.out_loc)} slots</b><p>Fix by transfer before buying</p></div>
    <div class="kpi"><small>💰 INVENTORY VALUE</small><b class="blue">${inr(K.inventory_value)}</b><p>At cheapest supplier price</p></div>
    <div class="kpi"><small>🧾 OPEN PURCHASE ORDERS</small><b>${K.open_po}</b><p>Open + Confirmed orders</p></div>
    <div class="kpi orange"><small>⏳ PENDING APPROVALS</small><b class="orange">${pend}</b><p>Waiting for your decision</p></div>
    <div class="kpi green"><small>🏬 LOCATIONS TRACKED</small><b>8</b><p>6 stores + 2 warehouses</p></div>`;
  drawDonut($('healthChart'), $('healthLegend'),
    [{ label: 'Available (>10)', value: K.avail_loc }, { label: 'Low Stock (1–10)', value: K.low_loc }, { label: 'Out of Stock (0)', value: K.out_loc }],
    ['#0a9d62', '#f5a623', '#dd2c2c']);
  const cats = Object.entries(d.cat_stock).sort((a, b) => b[1] - a[1]).map(([label, value]) => ({ label, value }));
  drawDonut($('catChart'), $('catLegend'), cats, ['#2563eb', '#0a9d62', '#f5a623', '#dd2c2c', '#7c3aed', '#0891b2', '#db2777', '#65a30d']);
  const max = Math.max(...Object.values(d.stock_by_loc));
  $('locBars').innerHTML = d.locations.map(l => `<div class="barrow"><span>${l}</span><b>${fmt(d.stock_by_loc[l] || 0)} units</b></div><div class="track"><div class="fill" style="width:${(d.stock_by_loc[l] || 0) / max * 100}%"></div></div>`).join('');
  $('fastBody').innerHTML = d.fast.map(i => `<tr><td><b>${i.sku}</b></td><td>${i.product_name}</td><td>${i.sold_60d}</td><td>${i.total_stock}</td><td>${pill(i.status)}</td></tr>`).join('');
  $('urgentBody').innerHTML = d.urgent.map(l => `<tr><td><b>${l.sku}</b></td><td>${l.product}<br><small style="color:var(--muted)">${l.model}</small></td><td>${l.location}</td><td><b>${l.stock}</b></td><td>${l.daily_demand}/day</td><td>${pill(l.status)}</td><td><button class="btn btn-primary btn-sm" onclick="quickRequest('${l.sku}')">Request</button></td></tr>`).join('');
  $('navLow').textContent = K.low_loc + K.out_loc;
}

/* ---------- Inventory  (GET /api/inventory?...) ---------- */
async function loadInventory() {
  const qs = new URLSearchParams({ search: $('fSearch').value, category: $('fCategory').value, model: $('fModel').value, status: $('fStatus').value, sort: $('fSort').value });
  const d = await api('/api/inventory?' + qs); ITEMS = d.items;
  if (!$('fCategory').dataset.done) { $('fCategory').innerHTML += d.categories.map(c => `<option>${c}</option>`).join(''); $('fModel').innerHTML += d.models.map(m => `<option>${m}</option>`).join(''); $('fCategory').dataset.done = 1; $('nrSku').innerHTML = (await api('/api/inventory?sort=name')).items.map(i => `<option value="${i.sku}">${i.sku} — ${i.product_name} (${i.machine_model}) • Stock ${i.total_stock}</option>`).join(''); }
  $('invCount').textContent = `Showing ${d.count} of 126 products`;
  $('invBody').innerHTML = ITEMS.map((i, x) => `<tr>
    <td><b>${i.sku}</b></td><td>${i.product_name}</td><td>${i.machine_model}</td><td>${i.category}</td>
    <td><b>${i.total_stock}</b><br><small style="color:var(--muted)">${i.loc_out} loc out • ${i.loc_low} low</small></td>
    <td>${i.sold_60d}</td><td>${i.daily_demand}/d</td><td>${i.days_cover > 900 ? '∞' : i.days_cover + 'd'}</td><td>${pill(i.status)}</td>
    <td>${i.best_supplier}<br><small style="color:var(--muted)">${inr(i.price)} • ${i.lead}d • MOQ ${i.moq}</small></td>
    <td><button class="btn btn-light btn-sm" onclick="toggleLoc(${x})">Locations ▾</button></td></tr>
    <tr id="loc-${x}" style="display:none"><td colspan="11" style="background:#f7f9ff">🏬 ${i.stock_by_loc.map(m => `${m.location}: <b>${m.stock}</b>`).join(' &nbsp;|&nbsp; ')}<br><small style="color:var(--muted)">Suppliers: ${i.suppliers.map(s => `${s.supplier} — ${inr(s.price)}, ${s.lead}d, MOQ ${s.moq}`).join(' | ')}</small></td></tr>`).join('') || '<tr><td colspan="11">No products match your filters.</td></tr>';
}
function toggleLoc(x) { const r = $('loc-' + x); r.style.display = r.style.display === 'none' ? '' : 'none'; }
['fSearch', 'fCategory', 'fModel', 'fStatus', 'fSort'].forEach(id => $(id).addEventListener('input', loadInventory));

/* ---------- Recommendations + AI chat ---------- */
async function loadRecommendations() {
  let d; try { d = await api('/api/recommendations'); } catch { $('recList').innerHTML = '<div class="rec low">Recommendations could not load right now. Please check that the Python API is running, then refresh.</div>'; return; }
  const cost = d.reorders.reduce((a, i) => a + i.rec_cost, 0);
  $('recSummary').innerHTML = `<div class="rec transfer"><b>${d.transfers.length} transfers</b> can fix shortages without spending &nbsp;•&nbsp; <b>${d.reorders.length} reorders</b> worth <b>${inr(cost)}</b></div>`;
  $('recList').innerHTML =
    `<h4 style="margin:12px 0 4px">🔀 Stock Transfer Recommendations — move stock, don't buy</h4>` +
    d.transfers.slice(0, 10).map(t => `<div class="rec transfer"><h5>${t.sku} — ${t.product}</h5><span class="meta">Move <b style="color:var(--ink)">${t.qty} units</b>: <b style="color:var(--ink)">${t.from_loc}</b> (has ${t.from_stock}) → <b style="color:var(--ink)">${t.to_loc}</b> (only ${t.to_stock} left, demand ${t.daily_demand}/day)</span></div>`).join('') +
    `<h4 style="margin:16px 0 4px">🛒 Purchase / Reorder Recommendations</h4>` +
    d.reorders.map(i => `<div class="rec ${i.status === 'Low Stock' ? 'low' : ''}"><h5>${i.sku} — ${i.product_name} ${pill(i.status)}</h5><span class="meta">${i.machine_model} • Stock ${i.total_stock} • Demand ${i.daily_demand}/day • Cover ${i.days_cover}d<br>Order <b style="color:var(--ink)">${i.rec_qty} units</b> from <b style="color:var(--ink)">${i.best_supplier}</b> @ ${inr(i.price)} = <b style="color:var(--ink)">${inr(i.rec_cost)}</b> • Lead ${i.lead}d, MOQ ${i.moq}</span><br><button class="btn btn-primary btn-sm" onclick="quickRequest('${i.sku}')">+ Create Request</button></div>`).join('');
}
function addMsg(text, who) { const d = document.createElement('div'); d.className = 'msg ' + who; d.textContent = text; $('chat').appendChild(d); $('chat').scrollTop = $('chat').scrollHeight; }
const QUICK = ['Which items are out of stock?', 'What should I reorder first?', 'Show transfers', 'Show low stock', 'Cheapest supplier for BLT-1003?', 'Top selling products', 'Which location has lowest stock?'];
$('chips').innerHTML = QUICK.map(q => `<span class="chip">${q}</span>`).join('');
document.querySelectorAll('.chip').forEach(c => c.onclick = () => { $('chatInput').value = c.textContent; $('chatForm').requestSubmit(); });
$('chatForm').onsubmit = async e => { e.preventDefault(); const m = $('chatInput').value.trim(); if (!m) return; addMsg(m, 'user'); $('chatInput').value = ''; try { addMsg((await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: m }) })).reply, 'ai'); } catch { addMsg('⚠ API is not reachable. Please check the Python server.', 'ai'); } };

/* ---------- Requests: approve / reject  (PUT /api/requests/<id>) ---------- */
async function loadRequests() { REQUESTS = (await api('/api/requests')).requests; renderRequests(); }
function renderRequests() {
  const list = REQUESTS.filter(r => (!$('rStatus').value || r.status === $('rStatus').value) && (!$('rSource').value || r.source === $('rSource').value) && (!$('rSearch').value || `${r.id} ${r.sku} ${r.product} ${r.supplier}`.toLowerCase().includes($('rSearch').value.toLowerCase())));
  const p = REQUESTS.filter(r => r.status === 'Pending');
  $('reqKpis').innerHTML = `
    <div class="kpi orange"><small>⏳ PENDING</small><b class="orange">${p.length}</b><p>Awaiting decision</p></div>
    <div class="kpi green"><small>✅ APPROVED</small><b class="green">${REQUESTS.filter(r => r.status === 'Approved').length}</b><p>Approved to purchase</p></div>
    <div class="kpi red"><small>❌ REJECTED</small><b class="red">${REQUESTS.filter(r => r.status === 'Rejected').length}</b><p>Rejected requests</p></div>
    <div class="kpi"><small>💰 PENDING VALUE</small><b class="blue">${inr(p.reduce((a, r) => a + r.cost, 0))}</b><p>Value awaiting approval</p></div>`;
  $('navReq').textContent = p.length || '';
  $('reqBody').innerHTML = list.map(r => `<tr><td><b>${r.id}</b><br><small style="color:var(--muted)">${r.sku}</small></td>
    <td>${r.product}<br><small style="color:var(--muted)">${r.model} • ${r.category}</small></td><td>${r.supplier}</td><td>${r.qty}</td><td>${inr(r.cost)}</td>
    <td>${r.expected}</td><td>${r.source}<br><small style="color:var(--muted)">${r.note}${r.requested_by ? ' • by ' + r.requested_by : ''}${r.decided_by ? '<br>Decided by ' + r.decided_by : ''}</small></td><td>${rPill(r.status)}</td>
    <td>${r.status === 'Pending' ? `<button class="btn btn-approve btn-sm" onclick="decide('${r.id}','Approved')">✓ Approve</button> <button class="btn btn-reject btn-sm" onclick="decide('${r.id}','Rejected')">✕ Reject</button>` : `<button class="btn btn-light btn-sm" onclick="decide('${r.id}','Pending')">↩ Reopen</button>`}</td></tr>`).join('') || '<tr><td colspan="9">No requests match.</td></tr>';
}
['rStatus', 'rSource', 'rSearch'].forEach(id => $(id).addEventListener('input', renderRequests));
async function decide(id, status) { await api('/api/requests/' + encodeURIComponent(id), { method: 'PUT', body: JSON.stringify({ status, name: myName() }) }); await loadRequests(); await loadDashboard(); toast(`Request ${id} → ${status} ✓`); }
async function quickRequest(sku) {
  const r = await api('/api/requests', { method: 'POST', body: JSON.stringify({ sku, name: myName() }) });
  await loadRequests(); await loadDashboard(); showPage('requests'); toast(`Request ${r.id} created for ${sku} — now Pending ⏳`);
}
$('newReqForm').onsubmit = async e => {
  e.preventDefault();
  const r = await api('/api/requests', { method: 'POST', body: JSON.stringify({ sku: $('nrSku').value, qty: $('nrQty').value, note: $('nrNote').value, name: myName() }) });
  $('nrQty').value = ''; $('nrNote').value = ''; $('formMsg').textContent = `✓ ${r.id} created for ${r.sku} (${r.qty} units, ${inr(r.cost)}) — status: Pending`;
  await loadRequests(); await loadDashboard(); toast('New request created ✓');
};

/* ---------- Suppliers & Orders ---------- */
async function loadSuppliers() {
  const [po, sup] = await Promise.all([api('/api/purchase-orders'), api('/api/suppliers')]);
  $('poBody').innerHTML = po.orders.map(o => `<tr><td><b>${o.po}</b></td><td>${o.supplier}</td><td>${o.sku}</td><td>${o.qty}</td><td>${o.expected_date}</td><td>${o.status}</td></tr>`).join('');
  $('supBody').innerHTML = sup.items.map(i => `<tr><td><b>${i.sku}</b></td><td>${i.product_name}</td><td>${i.best_supplier}</td><td>${inr(i.price)}</td><td>${i.lead}d</td><td>${i.moq}</td></tr>`).join('');
}

/* ---------- Export CSV ---------- */
$('exportBtn').onclick = async () => {
  const d = await api('/api/inventory?sort=name');
  const rows = [['sku', 'product_name', 'machine_model', 'category', 'total_stock', 'sold_60d', 'daily_demand', 'days_cover', 'status', 'best_supplier', 'price_inr', 'lead_days', 'moq']];
  d.items.forEach(i => rows.push([i.sku, i.product_name, i.machine_model, i.category, i.total_stock, i.sold_60d, i.daily_demand, i.days_cover, i.status, i.best_supplier, i.price, i.lead, i.moq]));
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([rows.map(r => r.join(',')).join('\n')], { type: 'text/csv' })); a.download = 'spare-parts-inventory.csv'; a.click(); toast('Inventory CSV downloaded ⬇');
};

/* ---------- Start ---------- */
(async function init() {
  try {
    await api('/api/health'); $('apiStatus').textContent = '● Python API Connected';
    await Promise.all([loadDashboard(), loadInventory(), loadRecommendations(), loadRequests(), loadSuppliers()]);
    showPage(location.hash.replace('#/', '').replace('ai-assistant', 'ai') || 'dashboard', false);
    addMsg('👋 Hello! I am your Spare Parts AI Assistant.\n\nRight now: 586 slots available, 368 low and 54 out of stock (network stock: 21,436 units — most shortages are fixable by transfer).\n\nAsk me any SKU, or tap a quick question above.', 'ai');
  } catch (e) { $('apiStatus').textContent = '● API Offline — run: python3 app.py'; toast('⚠ Could not connect to Python API'); }
})();
