const role = document.body.dataset.role;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function toast(msg, bad) {
  const t = document.createElement('div');
  t.className = 'toast' + (bad ? ' bad' : ''); t.textContent = msg;
  document.body.append(t); setTimeout(() => t.remove(), 2600);
}
async function api(url, body) {  // body given = POST (use {} for no data), otherwise GET
  const r = await fetch(url, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
  const d = await r.json();
  if (!r.ok) { toast(d.error || 'Something went wrong.', true); throw new Error(d.error); }
  return d;
}

const left = t => { const ms = new Date(t.replace(' ', 'T')) - Date.now(); if (ms <= 0) return 'expired';
  return Math.floor(ms / 36e5) + 'h ' + Math.floor(ms % 36e5 / 6e4) + 'm left'; };
const money = n => '₹' + Number(n).toFixed(2);
const cls = s => ['Paid', 'Left for delivery', 'Delivered'].includes(s) ? 'ok' : ['Cancelled', 'Returned'].includes(s) ? 'bad' : 'warn';
const stars = r => r == null ? '<span class="muted">No ratings yet</span>' : '<span class="stars">' + '★'.repeat(Math.round(r)) + '☆'.repeat(5 - Math.round(r)) + '</span> ' + r.toFixed(1);
const expText = d => d ? 'Expected ' + esc(d) : 'Date to be announced';
const TINTS = ['#f6e3d4', '#e2ebdc', '#efe6d2', '#dde9ee', '#f2dfdc', '#f5ecc9'];
const thumb = (p, big) => `<div class="thumb ${big ? 'big' : ''}" style="background:${TINTS[[...String(p.Category || '')].reduce((s, c) => s + c.charCodeAt(0), 0) % TINTS.length]}"><span>${esc(p.Item_name.charAt(0))}</span>${p.Image ? `<img src="${esc(p.Image)}" alt="" loading="lazy" onerror="this.remove()">` : ''}</div>`;
const NEXT = {'Paid': 'Left for delivery', 'Left for delivery': 'Delivered'};
const STEPS = ['Paid', 'Left for delivery', 'Delivered'];

// ---------- order pieces (customer and admin share these) ----------

function orderCard(o) {
  const exp = o.Items[0] ? o.Items[0].Expected_Date : '';
  const note = o.Status === 'Reserved' ? 'Pay within ' + left(o.Reserved_Until) : o.Status === 'Waiting for stock' ? expText(exp) : '';
  return `<div class="card tap" onclick="go('order',${o.Order_ID})">
    <div class="between"><b>Order #${o.Order_ID}</b><span class="badge ${cls(o.Status)}">${o.Status}</span></div>
    <p>${o.Items.map(i => esc(i.Item_name) + ' × ' + i.Quantity).join(', ')}</p>
    ${role === 'admin' ? `<p class="muted">${esc(o.Customer)}</p>` : ''}
    <div class="between"><span class="price">${money(o.Amount)}</span><span class="muted small">${note}</span></div>
    ${role === 'customer' && o.Status === 'Reserved' ? `<button onclick="event.stopPropagation();pay(${o.Order_ID})">Pay now</button>` : ''}</div>`;
}

function orderDetail(o) {
  const exp = o.Items[0] ? o.Items[0].Expected_Date : '';
  const acts = [];
  if (role === 'customer' && o.Status === 'Reserved') acts.push(`<button onclick="pay(${o.Order_ID})">Pay now</button>`);
  if (role === 'admin' && NEXT[o.Status]) acts.push(`<button onclick="advance(${o.Order_ID})">Mark as ${NEXT[o.Status].toLowerCase()}</button>`);
  if (role === 'admin' && o.Status === 'Return requested')
    acts.push(`<button onclick="decide(${o.Order_ID},true)">Approve return and refund</button><button class="alt" onclick="decide(${o.Order_ID},false)">Reject</button>`);
  if (role === 'customer' && o.Status === 'Delivered') acts.push(`<button class="alt" onclick="returnOrder(${o.Order_ID})">Return this order</button>`);
  if (['Reserved', 'Waiting for stock'].includes(o.Status)) acts.push(`<button class="alt" onclick="cancelOrder(${o.Order_ID})">Cancel order</button>`);
  const idx = STEPS.indexOf(o.Status);
  return `<button class="link" onclick="go('${role === 'admin' ? 'home' : 'orders'}')">← Back</button>
    <div class="panel"><div class="between"><h2 class="first">Order #${o.Order_ID}</h2><span class="badge ${cls(o.Status)}">${o.Status}</span></div>
    <p class="muted">Placed ${esc(o.Created_At)}${role === 'admin' ? ' by ' + esc(o.Customer) : ''}</p>
    ${idx >= 0 ? `<div class="steps">${STEPS.map((s, i) => `<div class="step ${i <= idx ? 'on' : ''}">${s}</div>`).join('')}</div>` : ''}
    ${o.Status === 'Reserved' ? `<p class="warn">Pay within ${left(o.Reserved_Until)} or it goes back on sale.</p>` : ''}
    ${o.Status === 'Waiting for stock' ? `<p class="warn">In the queue. ${expText(exp)}.</p>` : ''}
    ${o.Return_Reason ? `<p><b>Return reason:</b> ${esc(o.Return_Reason)}</p>` : ''}
    ${o.Items.map(i => `<div class="line"><span>${esc(i.Item_name)} × ${i.Quantity}</span><span>${money(i.Price * i.Quantity)}</span></div>`).join('')}
    <div class="line"><b>Total</b><b>${money(o.Amount)}</b></div>
    <div class="row">${acts.join('')}</div></div>`;
}

// ---------- views ----------

let catFilter = 'All', catNames = ['All'], cart = [], profileKeys = [];

const customerViews = {
  async shop() {
    const ps = await api('/api/products');
    catNames = ['All', ...new Set(ps.map(p => p.Category).filter(Boolean))];
    const shown = ps.filter(p => catFilter === 'All' || p.Category === catFilter);
    $('#main').innerHTML = `<h2 class="first">Shop</h2><div class="chips">` +
      catNames.map((n, i) => `<button class="chip ${n === catFilter ? 'on' : ''}" onclick="setCat(${i})">${esc(n)}</button>`).join('') +
      `</div><div class="grid products">` + (shown.map(p => `<div class="card tap" onclick="go('product',${p.Item_code})">
        ${thumb(p)}<span class="tag">${esc(p.Category || 'Uncategorised')}</span><h3>${esc(p.Item_name)}</h3>
        <p class="muted clamp">${esc(p.Details)}</p>
        <div class="between"><span class="price">${money(p.Price)}</span>${p.Buyable > 0 ? `<span class="badge ok">${p.Buyable} in stock</span>` : '<span class="badge warn">Out of stock</span>'}</div>
        <p class="muted small">${stars(p.Rating)}${p.Reviews ? ' (' + p.Reviews + ')' : ''}</p></div>`).join('') || '<p class="muted">Nothing here yet.</p>') + '</div>';
  },

  async product(id) {
    const d = await api('/api/product/' + id), p = d.product, ok = p.Buyable > 0, m = d.mine;
    $('#main').innerHTML = `<button class="link" onclick="go('shop')">← Back to shop</button>
      <div class="panel pd">${thumb(p, true)}<div><span class="tag">${esc(p.Category || 'Uncategorised')}</span>
      <h2 class="first">${esc(p.Item_name)}</h2>
      <p class="muted">Sold by ${esc(p.Supplier)} · ${stars(p.Rating)}${p.Reviews ? ' (' + p.Reviews + ')' : ''}</p>
      <p>${esc(p.Details) || '<span class="muted">No description.</span>'}</p>
      <p class="price big">${money(p.Price)}</p>
      <p>${ok ? `<span class="badge ok">${p.Buyable} in stock</span>` : `<span class="badge warn">Out of stock</span> <span class="muted">${p.Waiting ? p.Waiting + ' waiting in the queue. ' : ''}${expText(p.Expected_Date)}</span>`}</p>
      <div class="row"><input type="number" min="1" value="1" id="qty" aria-label="Quantity">
        ${ok ? `<button onclick="buyNow(${id})">Buy now</button><button class="cart" onclick="addCart(${id})">Add to cart</button>` : `<button onclick="preorder(${id})">Pre-order</button>`}</div>
      <p class="muted small">${ok ? 'Buy now pays straight away. No timer.' : "Pre-orders keep your place in the queue. When it's back, we hold it for you for 12 hours to pay."}</p></div></div>
      <h2>Reviews</h2>` +
      (d.can_review ? `<div class="panel stack"><h3>${m ? 'Edit your review' : 'Write a review'}</h3>
        <label>Rating<select id="rt">${[5, 4, 3, 2, 1].map(n => `<option value="${n}" ${m && m.Rating === n ? 'selected' : ''}>${n} star${n > 1 ? 's' : ''}</option>`).join('')}</select></label>
        <label>Comment<textarea id="rc" maxlength="500">${esc(m ? m.Comment : '')}</textarea></label>
        <button onclick="saveReview(${id})">Save review</button></div>` : '<p class="muted small">You can review a product once it has been delivered to you.</p>') +
      `<div class="panel">` + (d.reviews.length ? d.reviews.map(r => `<div class="review"><b>${esc(r.Name)}</b> <span class="muted">${stars(r.Rating)}</span><p>${esc(r.Comment)}</p></div>`).join('') : '<p class="muted">No reviews yet.</p>') + '</div>';
  },

  async cart() {
    if (!cart.length) { $('#main').innerHTML = `<h2 class="first">Cart</h2><p class="muted">Your cart is empty.</p><button onclick="go('shop')">Browse products</button>`; return; }
    const total = cart.reduce((s, c) => s + c.Price * c.Quantity, 0), bad = cart.some(c => !c.Ok);
    $('#main').innerHTML = `<h2 class="first">Cart</h2><div class="panel">` + cart.map(c => `<div class="line">
      <div><b>${esc(c.Item_name)}</b><br><span class="muted">${money(c.Price)} each</span>
        ${c.Ok ? '' : '<br><span class="bad small">Not enough stock right now. Lower the quantity or remove it.</span>'}</div>
      <div class="row"><input type="number" min="1" value="${c.Quantity}" onchange="setQty(${c.Item_code},this.value)" aria-label="Quantity">
        <button class="alt" onclick="setQty(${c.Item_code},0)">Remove</button></div></div>`).join('') +
      `<div class="line"><b>Total</b><b>${money(total)}</b></div>
      <button onclick="checkout(${total})" ${bad ? 'disabled' : ''}>Pay ${money(total)}</button></div>`;
  },

  async orders() {
    const os = await api('/api/orders');
    $('#main').innerHTML = `<h2 class="first">My orders</h2>` + (os.length ? `<div class="grid">${os.map(orderCard).join('')}</div>` : '<p class="muted">No orders yet.</p>');
  },
  async order(id) { $('#main').innerHTML = orderDetail(await api('/api/order/' + id)); },
  profile: profileView,
};

const sellerViews = {
  async products() {
    const [ps, cs] = await Promise.all([api('/api/products'), api('/api/categories')]);
    $('#main').innerHTML = `<h2 class="first">Add a product</h2><div class="add">
      <label>Name<input id="n"></label><label>Price<input id="pr" type="number" min="0" step="0.01" inputmode="decimal"></label>
      <label>Stock<input id="st" type="number" min="0" value="0"></label><label>Expected date<input id="ex" type="date"></label>
      <label>Category<select id="ct">${cs.map(c => `<option>${esc(c)}</option>`).join('')}</select></label>
      <label class="wide">Description<textarea id="ds" maxlength="255"></textarea></label>
      <label class="wide">Image link (optional)<input id="im" placeholder="https://..."></label>
      <button class="wide" onclick="addProduct()">Add product</button></div>
      <h2>Your products</h2><div class="tw"><table><tr><th>Product</th><th>Category</th><th>In stock</th><th>Waiting orders</th><th>Add stock</th><th>Expected date</th><th></th></tr>` +
      ps.map(p => `<tr><td>${esc(p.Item_name)}${p.Banned ? '<br><span class="badge bad">Banned by admin</span>' : ''}</td><td>${esc(p.Category)}</td><td>${p.Stock}</td><td>${p.Waiting}</td>
        <td><input type="number" min="0" value="0" id="rq${p.Item_code}"></td><td><input type="date" id="rd${p.Item_code}" value="${esc(p.Expected_Date)}"></td>
        <td><button onclick="restock(${p.Item_code})">Update</button></td></tr>`).join('') + '</table></div>';
  },
  profile: profileView,
};

const adminViews = {
  async home() {
    const os = await api('/api/orders'), n = s => os.filter(o => o.Status === s).length;
    const todo = os.filter(o => ['Paid', 'Return requested'].includes(o.Status));
    $('#main').innerHTML = `<h2 class="first">Find an order</h2>
      <form class="inline" onsubmit="lookup(event)"><input id="ono" type="number" min="1" inputmode="numeric" placeholder="Order number" required><button>Open</button></form>
      <h2>Overview</h2><div class="stats">` +
      [[os.length, 'Total orders'], [n('Paid'), 'To dispatch'], [n('Left for delivery'), 'On the way'], [n('Return requested'), 'Return requests'], [n('Waiting for stock'), 'Waiting for stock']]
        .map(([v, l]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join('') +
      `</div><h2>Needs action</h2>` + (todo.length ? `<div class="grid">${todo.map(orderCard).join('')}</div>` : '<p class="muted">Nothing needs action.</p>');
  },
  async order(id) { $('#main').innerHTML = orderDetail(await api('/api/order/' + id)); },
  async products() {
    const [ps, cs] = await Promise.all([api('/api/products'), api('/api/categories')]);
    $('#main').innerHTML = `<h2 class="first">Products</h2><div class="tw"><table><tr><th>Product</th><th>Seller</th><th>Category</th><th>Price</th><th>In stock</th><th>Waiting</th><th>Status</th><th></th></tr>` +
      ps.map(p => `<tr><td>${esc(p.Item_name)}</td><td>${esc(p.Supplier)}</td>
        <td><select onchange="setCategory(${p.Item_code},this.value)">${cs.map(c => `<option ${c === p.Category ? 'selected' : ''}>${esc(c)}</option>`).join('')}</select></td>
        <td>${money(p.Price)}</td><td>${p.Stock}</td><td>${p.Waiting}</td>
        <td><span class="badge ${p.Banned ? 'bad' : 'ok'}">${p.Banned ? 'Banned' : 'Live'}</span></td>
        <td><button class="${p.Banned ? '' : 'danger'}" onclick="banProduct(${p.Item_code},${p.Banned ? 0 : 1})">${p.Banned ? 'Unban' : 'Ban'}</button></td></tr>`).join('') + '</table></div>';
  },
  profile: profileView,
};

const LABEL = {Name: 'Name', Phone_no: 'Phone', Email: 'Email', Address: 'Address'};
async function profileView() {
  const p = await api('/api/profile');
  profileKeys = Object.keys(p.fields);
  $('#main').innerHTML = `<h2 class="first">Profile</h2><div class="panel stack"><label>Username<input value="${esc(p.username)}" disabled></label>` +
    profileKeys.map(k => `<label>${LABEL[k]}<input id="pf_${k}" value="${esc(p.fields[k])}"${k === 'Phone_no' ? ' inputmode="tel"' : ''}></label>`).join('') +
    `<button onclick="saveProfile()">Save</button></div>`;
}

// ---------- navigation ----------

const TABS = {
  customer: [['shop', 'Shop'], ['cart', 'Cart'], ['orders', 'Orders'], ['profile', 'Profile']],
  seller: [['products', 'Products'], ['profile', 'Profile']],
  admin: [['home', 'Dashboard'], ['products', 'Products'], ['profile', 'Profile']],
}[role];
const V = {customer: customerViews, seller: sellerViews, admin: adminViews}[role];
const PARENT = {product: 'shop', order: role === 'admin' ? 'home' : 'orders'};
let cur = TABS[0][0], arg = null;

function go(view, a) { cur = view; arg = a ?? null; scrollTo(0, 0); load(); }
async function load() {
  if (role === 'customer') cart = await api('/api/cart');
  const count = cart.reduce((s, c) => s + c.Quantity, 0);
  $('#nav').innerHTML = TABS.map(([k, t]) => `<button class="tab ${(PARENT[cur] || cur) === k ? 'on' : ''}" onclick="go('${k}')">${t}${k === 'cart' && count ? `<span class="count">${count}</span>` : ''}</button>`).join('');
  await V[cur](arg);
}
const done = fn => async (...a) => { await fn(...a); load(); };

// ---------- actions ----------

const setCat = i => { catFilter = catNames[i]; load(); };
const lookup = async e => { e.preventDefault(); const n = $('#ono').value; await api('/api/order/' + n); go('order', n); };

const buyNow = async id => {
  if (!confirm('Place this order and pay now?')) return;
  const r = await api('/api/buy', {item_code: id, qty: $('#qty').value});
  toast('Order placed.'); go('order', r.order_id);
};
const preorder = async id => {
  const r = await api('/api/preorder', {item_code: id, qty: $('#qty').value});
  toast("You're in the queue. We'll hold it for you when it's back."); go('order', r.order_id);
};
const addCart = done(id => api('/api/cart/add', {item_code: id, qty: $('#qty').value}).then(() => toast('Added to cart.')));
const setQty = done((id, qty) => api('/api/cart/set', {item_code: id, qty}));
const checkout = async total => {
  if (!confirm('Pay ' + money(total) + ' now?')) return;
  const r = await api('/api/checkout', {});
  toast('Order placed.'); go('order', r.order_id);
};
const saveReview = done(id => api('/api/review', {item_code: id, rating: $('#rt').value, comment: $('#rc').value}).then(() => toast('Review saved.')));

const pay = done(id => api('/api/pay/' + id, {}).then(() => toast('Payment received.')));
const cancelOrder = done(id => confirm('Cancel this order?') ? api('/api/cancel/' + id, {}) : null);
const returnOrder = done(id => { const reason = prompt('Why are you returning this order?'); return reason && reason.trim() ? api('/api/return/' + id, {reason}) : null; });
const advance = done(id => api('/api/order/' + id + '/advance', {}));
const decide = done((id, approve) => api('/api/return/' + id + '/decide', {approve}));

const addProduct = done(() => api('/api/product', {name: $('#n').value, price: $('#pr').value, stock: $('#st').value, expected: $('#ex').value, category: $('#ct').value, details: $('#ds').value, image: $('#im').value}));
const restock = done(id => api('/api/restock', {item_code: id, qty: $('#rq' + id).value, expected: $('#rd' + id).value}));
const banProduct = done((id, banned) => confirm(banned ? 'Ban this product? Customers will no longer see it.' : 'Unban this product?') ? api('/api/ban', {item_code: id, banned}) : null);
const setCategory = (id, category) => api('/api/category', {item_code: id, category}).then(() => toast('Category updated.'));

async function saveProfile() {
  const body = {}; profileKeys.forEach(k => body[k] = $('#pf_' + k).value);
  const r = await api('/api/profile', body);
  $('#who').textContent = r.name + ' (' + role + ')'; toast('Profile saved.');
}

load();