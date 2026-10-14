const $ = (selector) => document.querySelector(selector);
const state = { groups: [], users: [], members: [], expenses: [], payments: [], summary: [], analytics: null, group: null, balance: null, suggestions: [], payment: null, version: 0 };
const money = (minor) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(minor / 100);
// API amounts have exactly two decimal places; keep arithmetic in paise here too.
const paise = (value) => {
  const match = String(value).match(/^(-?)(\d+)(?:\.(\d{0,2}))?$/);
  if (!match) return null;
  return (match[1] ? -1 : 1) * (Number(match[2]) * 100 + Number((match[3] || '').padEnd(2, '0')));
};
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const initials = (name) => name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const dateLabel = (date) => new Date(date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
const avatar = (name) => `<span class="avatar" aria-hidden="true">${escapeHTML(initials(name))}</span>`;
const labelFor = (person) => state.members.filter(member => member.name === person.name).length > 1 ? `${person.name} (#${person.id})` : person.name;
let toastTimer;

async function api(path, data, method = 'POST') {
  let response;
  try {
    response = await fetch(path, data === undefined ? {} : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  } catch {
    throw new Error('Cannot reach the service. Check that it is running, then refresh.');
  }
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(body.error?.details?.map(detail => detail.message).join('. ') || body.error?.message || 'Something went wrong. Please try again.');
  return body;
}

async function allPages(path) {
  const items = [];
  for (let offset = 0; ; offset += 100) {
    const page = await api(`${path}${path.includes('?') ? '&' : '?'}limit=100&offset=${offset}`);
    items.push(...page);
    if (page.length < 100) return items;
  }
}

function notify(message) {
  clearTimeout(toastTimer);
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4500);
}

function showError(error) {
  $('#page-error').textContent = error.message;
  $('#page-error').hidden = false;
}

function renderGroups() {
  $('#group-list').innerHTML = state.groups.map(group => `<button class="group-choice ${group.id === state.group ? 'selected' : ''}" data-group="${group.id}" ${group.id === state.group ? 'aria-current="true"' : ''}><span class="group-initial">${escapeHTML(initials(group.name))}</span><span class="group-name">${escapeHTML(group.name)}</span></button>`).join('') || '<p class="muted">No groups yet.</p>';
}

async function loadWorkspace(preferred) {
  $('#refresh').disabled = true;
  try {
    [state.groups, state.users] = await Promise.all([allPages('/groups'), allPages('/users')]);
    const desired = preferred || state.group || Number(new URLSearchParams(location.search).get('group'));
    await selectGroup(state.groups.some(group => group.id === desired) ? desired : state.groups[0]?.id);
  } catch (error) { showError(error); }
  finally { $('#refresh').disabled = false; }
}

async function selectGroup(id) {
  state.group = id || null;
  const version = ++state.version;
  renderGroups();
  $('#page-error').hidden = true;
  $('#welcome').hidden = !!id;
  $('#group-content').hidden = !id;
  $('#add-expense').disabled = true;
  $('#delete-group').disabled = !id;
  $('#export-csv').disabled = !id;
  if (!id) {
    $('#group-title').textContent = 'Your shared expenses';
    $('#group-description').textContent = 'Create a group to start tracking shared expenses.';
    return;
  }
  $('#group-title').textContent = state.groups.find(group => group.id === id).name;
  $('#group-description').textContent = 'Loading the latest expenses and balances…';
  $('#group-content').classList.add('loading');
  history.replaceState(null, '', `/?group=${id}`);
  try {
    const [members, expenses, balance, plan, payments, summary, analytics] = await Promise.all([
      api(`/groups/${id}/members`), allPages(`/groups/${id}/expenses`), api(`/balances?group_id=${id}`),
      api(`/groups/${id}/settlement-suggestions`), allPages(`/groups/${id}/settlements`),
      api(`/groups/${id}/monthly-summary`), api(`/groups/${id}/analytics`),
    ]);
    if (version !== state.version) return;
    Object.assign(state, { members, expenses, balance, suggestions: plan.suggestions, payments, summary, analytics });
    $('#group-description').textContent = members.length ? 'Track expenses, balances, and repayments for this group.' : 'Add the people who will share expenses.';
    $('#add-expense').disabled = members.length === 0;
    $('#search').value = '';
    $('#category-filter').innerHTML = '<option value="">All categories</option>' + [...new Set(expenses.map(expense => expense.category || 'Other'))].sort().map(category => `<option value="${escapeHTML(category)}">${escapeHTML(category)}</option>`).join('');
    render();
  } catch (error) {
    if (version === state.version) { showError(error); $('#group-content').hidden = true; $('#group-description').textContent = 'Could not load this group. Use Refresh to try again.'; }
  } finally { if (version === state.version) $('#group-content').classList.remove('loading'); }
}

function empty(title, description, icon = '↗') {
  return `<div class="empty"><span class="empty-icon" aria-hidden="true">${icon}</span><strong>${title}</strong>${description}</div>`;
}

function render() {
  const total = state.balance.members.reduce((sum, member) => sum + paise(member.paid), 0);
  const outstanding = state.balance.members.reduce((sum, member) => sum + Math.max(0, paise(member.net_balance)), 0);
  $('#total-spent').textContent = money(total);
  $('#total-owed').textContent = money(outstanding);
  $('#member-count').textContent = state.members.length;
  $('#member-caption').textContent = state.members.length ? state.members.map(member => member.name).join(', ') : 'Add people to this group';
  $('#settle-caption').textContent = outstanding ? `${state.suggestions.length} suggested payment${state.suggestions.length === 1 ? '' : 's'} remaining` : 'No payments needed.';
  $('#expense-count').textContent = state.expenses.length;
  renderInsights();
  renderExpenses();
  $('#suggestions').innerHTML = state.suggestions.map((payment, index) => `<article class="suggestion"><div class="suggestion-top">${avatar(payment.from_name)}<div class="suggestion-names">${escapeHTML(payment.from_name)}<span class="arrow" aria-label="pays">→</span>${escapeHTML(payment.to_name)}</div></div><div class="suggestion-bottom"><strong>${money(paise(payment.amount))}</strong><button class="record-button" data-payment="${index}">Record payment ↗</button></div></article>`).join('') || empty(state.members.length ? 'All settled up' : 'No balances yet', state.members.length ? 'Nobody owes anything right now.' : 'Add members and an expense to get started.', '✓');
  $('#members').innerHTML = state.members.length ? `<table class="member-table"><thead><tr><th>Member</th><th>Paid</th><th>Share</th><th>Balance</th></tr></thead><tbody>${state.balance.members.map(member => {
    const net = paise(member.net_balance);
    return `<tr><td><div class="person-cell">${avatar(member.name)}<span>${escapeHTML(labelFor({ id: member.user_id, name: member.name }))}</span></div></td><td>${money(paise(member.paid))}</td><td>${money(paise(member.share))}</td><td><span class="net-pill ${net > 0 ? 'receives' : net < 0 ? 'owes' : 'settled'}">${net > 0 ? 'Gets back ' + money(net) : net < 0 ? 'Owes ' + money(-net) : 'Settled up'}</span></td></tr>`;
  }).join('')}</tbody></table>` : empty('No members yet', 'Use “Add member” to add people to this group.', '+');
  const names = Object.fromEntries(state.members.map(member => [member.id, member.name]));
  $('#payment-count').textContent = state.payments.length;
  $('#payment-list').innerHTML = state.payments.map(payment => `<div class="payment-row"><div>${escapeHTML(names[payment.from_user_id])} <span class="muted">paid</span> ${escapeHTML(names[payment.to_user_id])}<small>${dateLabel(payment.created_at)}</small></div><strong>${money(paise(payment.amount_minor ?? payment.amount))}</strong></div>`).join('') || '<div class="empty">No payments recorded yet.</div>';
}

function renderInsights() {
  $('#monthly-summary').innerHTML = state.summary.map(item => {
    const label = new Date(`${item.month}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    return `<div class="month-summary-item"><strong>${label}</strong><span>${money(paise(item.total_spent))}</span><small>${item.expense_count} expense${item.expense_count === 1 ? '' : 's'}</small></div>`;
  }).join('') || '<span class="muted">Add an expense to see monthly totals.</span>';
  const total = paise(state.analytics.total_spent);
  const section = (title, rows) => `<div class="analytics-section"><strong>${title}</strong>${rows.map(row => {
    const amount = paise(row.total), percent = total ? Math.round((amount / total) * 100) : 0;
    return `<div class="bar-row"><div><span>${escapeHTML(row.name)}</span><span>${money(amount)} · ${percent}%</span></div><i><b style="width:${percent}%"></b></i></div>`;
  }).join('')}</div>`;
  $('#analytics').innerHTML = state.analytics.expense_count ? categoryChart(state.analytics.by_category, total) + section('Paid by', state.analytics.by_payer) : '<div class="empty">Add an expense to see spending details.</div>';
}

function categoryChart(rows, total) {
  const colors = ['#17684e', '#75a983', '#b8c98f', '#d7b878', '#c58b66', '#8ca8a0'];
  let angle = -90;
  const point = (degrees, radius) => {
    const radians = degrees * Math.PI / 180;
    return [100 + radius * Math.cos(radians), 100 + radius * Math.sin(radians)];
  };
  const slice = (start, end, color, index) => {
    if (end - start >= 359.99) return `<circle class="analytics-slice active" data-analytics-slice="${index}" cx="100" cy="100" r="56" fill="none" style="stroke:${color};stroke-width:34px" tabindex="0" role="button" aria-label="${escapeHTML(rows[index].name)}"></circle>`;
    const [outerStartX, outerStartY] = point(start, 73), [outerEndX, outerEndY] = point(end, 73);
    const [innerEndX, innerEndY] = point(end, 39), [innerStartX, innerStartY] = point(start, 39);
    const large = end - start > 180 ? 1 : 0;
    return `<path class="analytics-slice" data-analytics-slice="${index}" d="M ${outerStartX} ${outerStartY} A 73 73 0 ${large} 1 ${outerEndX} ${outerEndY} L ${innerEndX} ${innerEndY} A 39 39 0 ${large} 0 ${innerStartX} ${innerStartY} Z" fill="${color}" tabindex="0" role="button" aria-label="${escapeHTML(rows[index].name)}"></path>`;
  };
  const slices = rows.map((row, index) => {
    const next = angle + (paise(row.total) / total) * 360;
    const markup = slice(angle, next, colors[index % colors.length], index);
    angle = next;
    return markup;
  }).join('');
  const legend = rows.map((row, index) => {
    const percent = Math.round((paise(row.total) / total) * 100);
    return `<button class="chart-legend ${index === 0 ? 'active' : ''}" data-analytics-slice="${index}"><i style="background:${colors[index % colors.length]}"></i><span>${escapeHTML(row.name)}</span><strong>${money(paise(row.total))}</strong><small>${percent}%</small></button>`;
  }).join('');
  const first = rows[0];
  return `<div class="chart-section"><strong>By category</strong><div class="category-chart"><svg viewBox="0 0 200 200" role="group" aria-label="Spending by category">${slices}</svg><div id="chart-detail" class="chart-detail"><strong>${escapeHTML(first.name)}</strong><span>${money(paise(first.total))} · ${Math.round((paise(first.total) / total) * 100)}%</span></div></div><div class="chart-legend-list">${legend}</div></div>`;
}

function selectAnalyticsSlice(index) {
  const rows = state.analytics?.by_category || [];
  const row = rows[index];
  if (!row) return;
  const total = paise(state.analytics.total_spent);
  document.querySelectorAll('[data-analytics-slice]').forEach(element => element.classList.toggle('active', Number(element.dataset.analyticsSlice) === index));
  $('#chart-detail').innerHTML = `<strong>${escapeHTML(row.name)}</strong><span>${money(paise(row.total))} · ${Math.round((paise(row.total) / total) * 100)}%</span>`;
}

function renderExpenses() {
  const search = $('#search').value.trim().toLowerCase();
  const category = $('#category-filter').value;
  const range = $('#date-range')?.value || 'all';
  const start = new Date();
  if (range === 'month') start.setDate(1);
  if (range === '30') start.setDate(start.getDate() - 29);
  start.setHours(0, 0, 0, 0);
  const visible = state.expenses.filter(expense => expense.description.toLowerCase().includes(search) && (!category || (expense.category || 'Other') === category) && (range === 'all' || new Date(expense.created_at) >= start));
  $('#expense-list').innerHTML = visible.map(expense => {
    const type = (expense.category || 'other').toLowerCase();
    const symbol = ({ food: '♧', travel: '↗', transport: '↗', stay: '⌂', shopping: '◇' })[type] || '▦';
    return `<details class="expense"><summary><span class="expense-icon ${['travel', 'stay', 'other'].includes(type) ? type : ''}" aria-hidden="true">${symbol}</span><span class="expense-info"><span class="expense-name">${escapeHTML(expense.description)}</span><small>Paid by ${escapeHTML(expense.payer_name)} · ${dateLabel(expense.created_at)}</small></span><span class="expense-amount">${money(paise(expense.amount))}</span><span class="view-split">View split</span><span class="chevron" aria-hidden="true">⌄</span></summary><div class="expense-details"><strong>${expense.split_type === 'equal' ? 'Shared equally' : 'Custom shares'} · ${escapeHTML(expense.category || 'Other')}</strong><div class="expense-tools">${expense.receipt_url ? `<a class="receipt-link" href="${expense.receipt_url}" target="_blank" rel="noopener">View receipt ↗</a>` : ''}<button class="delete-expense" data-delete-expense="${expense.id}">Delete expense</button></div>${expense.splits.map(split => `<div class="share-row"><span>${escapeHTML(split.name)}</span><span>${money(paise(split.amount))}</span></div>`).join('')}</div></details>`;
  }).join('') || empty(state.expenses.length ? 'No matching expenses' : 'No expenses yet', state.expenses.length ? 'Try another search or category.' : state.members.length ? 'Click “Add expense” to record the first bill.' : 'Add group members before adding an expense.', '₹');
}

function openDialog(id) {
  const dialog = document.getElementById(id);
  dialog.querySelector('form').reset();
  dialog.querySelector('.form-error').hidden = true;
  if (id === 'member-dialog') {
    const available = state.users.filter(user => !state.members.some(member => member.id === user.id));
    $('#existing-user').innerHTML = available.map(user => `<option value="${user.id}">${escapeHTML(user.name)} (#${user.id})</option>`).join('') || '<option value="">No other people available</option>';
    setMemberMode();
  }
  if (id === 'expense-dialog') {
    $('#payer').innerHTML = state.members.map(member => `<option value="${member.id}">${escapeHTML(labelFor(member))}</option>`).join('');
    $('#custom-splits').innerHTML = state.members.map(member => `<label class="custom-row"><span>${escapeHTML(labelFor(member))}</span><input aria-label="Share for ${escapeHTML(labelFor(member))}" data-share="${member.id}" type="number" min="0" max="1000000000" step="0.01" value="0.00" inputmode="decimal"></label>`).join('');
    previewSplit();
  }
  dialog.showModal();
}

function setMemberMode() {
  const existing = $('#member-mode').value === 'existing';
  $('#new-person-field').hidden = existing;
  $('#existing-person-field').hidden = !existing;
  $('#person-name').disabled = existing;
  $('#existing-user').disabled = !existing;
  $('#existing-user').required = existing;
}

function previewSplit() {
  const custom = $('#split-mode').value === 'unequal';
  $('#custom-splits').hidden = !custom;
  $('#custom-splits').querySelectorAll('input').forEach(input => { input.disabled = !custom; input.required = custom; });
  const amount = paise($('#expense-amount').value);
  if (custom) {
    $('#split-preview').textContent = 'Enter a share for each person. Shares must add up to the total; use 0.00 for anyone not sharing this expense.';
  } else if (amount > 0 && state.members.length) {
    const sorted = [...state.members].sort((a, b) => a.id - b.id);
    const share = Math.floor(amount / sorted.length), remainder = amount % sorted.length;
    $('#split-preview').innerHTML = '<strong>Everyone’s share</strong>' + sorted.map((member, index) => `<div class="share-row"><span>${escapeHTML(labelFor(member))}</span><span>${money(share + (index < remainder ? 1 : 0))}</span></div>`).join('');
  } else $('#split-preview').textContent = `The bill will be shared by all ${state.members.length} current members, including the person who paid.`;
}

async function submit(event, action) {
  event.preventDefault();
  const form = event.target, button = form.querySelector('[type="submit"]'), errorBox = form.querySelector('.form-error');
  if (button.disabled) return;
  button.disabled = true;
  errorBox.hidden = true;
  // Keep this operation bound to the group that was selected when submitted.
  const group = state.group;
  try {
    const message = await action(new FormData(form), group);
    form.closest('dialog').close();
    notify(message);
    await loadWorkspace(state.group);
  } catch (error) { errorBox.textContent = error.message; errorBox.hidden = false; }
  finally { button.disabled = false; }
}

document.addEventListener('click', event => {
  const open = event.target.closest('[data-open]');
  if (open) openDialog(open.dataset.open);
  const close = event.target.closest('[data-close]');
  if (close) close.closest('dialog').close();
  const group = event.target.closest('[data-group]');
  if (group) selectGroup(Number(group.dataset.group));
  const payment = event.target.closest('[data-payment]');
  if (payment) {
    state.payment = state.suggestions[Number(payment.dataset.payment)];
    openDialog('payment-dialog');
    $('#payment-description').textContent = `${state.payment.from_name} pays ${state.payment.to_name}. Suggested amount: ${money(paise(state.payment.amount))}.`;
    $('#payment-amount').value = state.payment.amount;
    $('#payment-amount').max = state.payment.amount;
  }
  const analyticsSlice = event.target.closest('[data-analytics-slice]');
  if (analyticsSlice) selectAnalyticsSlice(Number(analyticsSlice.dataset.analyticsSlice));
  const deleteExpense = event.target.closest('[data-delete-expense]');
  if (deleteExpense && confirm('Delete this expense? This cannot be undone.')) {
    api(`/expenses/${deleteExpense.dataset.deleteExpense}`, {}, 'DELETE').then(() => loadWorkspace(state.group)).catch(showError);
  }
});
document.addEventListener('pointerover', event => {
  const analyticsSlice = event.target.closest('[data-analytics-slice]');
  if (analyticsSlice) selectAnalyticsSlice(Number(analyticsSlice.dataset.analyticsSlice));
});
document.addEventListener('focusin', event => {
  const analyticsSlice = event.target.closest('[data-analytics-slice]');
  if (analyticsSlice) selectAnalyticsSlice(Number(analyticsSlice.dataset.analyticsSlice));
});
$('#refresh').addEventListener('click', () => loadWorkspace());
$('#export-csv').addEventListener('click', () => {
  if (state.group) window.location.assign(`/groups/${state.group}/expenses/export.xlsx`);
});
$('#add-member').addEventListener('click', () => openDialog('member-dialog'));
$('#add-expense').addEventListener('click', () => openDialog('expense-dialog'));
$('#delete-group').addEventListener('click', async () => {
  if (!state.group || !confirm('Delete this group and all its expenses, receipts, and payments? This cannot be undone.')) return;
  try { await api(`/groups/${state.group}`, {}, 'DELETE'); notify('Group deleted.'); state.group = null; await loadWorkspace(); } catch (error) { showError(error); }
});
$('#member-mode').addEventListener('change', setMemberMode);
$('#expense-amount').addEventListener('input', previewSplit);
$('#split-mode').addEventListener('change', previewSplit);
$('#search').addEventListener('input', renderExpenses);
$('#category-filter').addEventListener('change', renderExpenses);
$('#date-range').addEventListener('change', renderExpenses);
$('#load-demo').addEventListener('click', async () => {
  try { const group = await api('/demo-data', {}); notify('Demo group created.'); await loadWorkspace(group.id); } catch (error) { showError(error); }
});

$('#group-form').addEventListener('submit', event => submit(event, async data => {
  const name = data.get('name').trim();
  if (!name) throw new Error('Give your group a name.');
  const group = await api('/groups', { name });
  state.group = group.id;
  return 'Group created. Add members next.';
}));
$('#member-form').addEventListener('submit', event => submit(event, async (data, group) => {
  let user;
  if (data.get('mode') === 'new') {
    const name = data.get('name').trim();
    if (!name) throw new Error('Enter the person’s name.');
    user = await api('/users', { name });
    state.users.push(user);
    // If adding membership fails, retry the existing user instead of creating a duplicate.
    $('#existing-user').insertAdjacentHTML('beforeend', `<option value="${user.id}">${escapeHTML(user.name)} (#${user.id})</option>`);
    $('#existing-user').value = String(user.id);
    $('#member-mode').value = 'existing';
    setMemberMode();
  } else {
    user = state.users.find(person => person.id === Number(data.get('user_id')));
    if (!user) throw new Error('Choose a person, or create someone new.');
  }
  await api(`/groups/${group}/members`, { user_id: user.id });
  return `Added ${user.name} to the group.`;
}));
$('#expense-form').addEventListener('submit', event => submit(event, async (data, group) => {
  const body = { group_id: group, paid_by: Number(data.get('paid_by')), amount: data.get('amount'), description: data.get('description').trim(), category: data.get('category') };
  if (!body.description) throw new Error('Add a short description for this expense.');
  if (data.get('split') === 'unequal') {
    body.splits = [...$('#custom-splits').querySelectorAll('input')].map(input => ({ user_id: Number(input.dataset.share), amount: input.value }));
    const values = body.splits.map(split => paise(split.amount));
    if (values.some(value => value === null || value < 0) || values.reduce((sum, value) => sum + value, 0) !== paise(body.amount)) throw new Error('Each share must be a valid amount, and all shares must add up to the expense total.');
  }
  const expense = await api('/expenses', body);
  const receipt = $('#receipt').files[0];
  if (receipt) await uploadReceipt(expense.id, receipt);
  return receipt ? 'Expense and receipt saved.' : 'Expense saved. Balances updated.';
}));

async function uploadReceipt(expenseId, file) {
  if (!['image/jpeg', 'image/png', 'application/pdf'].includes(file.type)) throw new Error('Choose a JPG, PNG, or PDF receipt.');
  if (file.size > 5_000_000) throw new Error('Receipt must be 5 MB or smaller.');
  const dataUrl = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
  await api(`/expenses/${expenseId}/receipt`, { filename: file.name, content_type: file.type, data_base64: dataUrl.split(',')[1] }, 'PUT');
}
$('#payment-form').addEventListener('submit', event => submit(event, async (data, group) => {
  await api(`/groups/${group}/settlements`, { from_user_id: state.payment.from_user_id, to_user_id: state.payment.to_user_id, amount: data.get('amount') });
  return 'Payment recorded.';
}));

loadWorkspace();
