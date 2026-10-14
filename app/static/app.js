const $ = (selector) => document.querySelector(selector);
const state = { groups: [], users: [], members: [], expenses: [], payments: [], group: null, balance: null, suggestions: [], payment: null, version: 0 };
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

async function api(path, data) {
  let response;
  try {
    response = await fetch(path, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  } catch {
    throw new Error('Cannot reach the service. Check that it is running, then refresh.');
  }
  const body = await response.json();
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
  if (!id) {
    $('#group-title').textContent = 'Your shared expenses';
    $('#group-description').textContent = 'A home for every bill and every shared plan.';
    return;
  }
  $('#group-title').textContent = state.groups.find(group => group.id === id).name;
  $('#group-description').textContent = 'Loading the latest expenses and balances…';
  $('#group-content').classList.add('loading');
  history.replaceState(null, '', `/?group=${id}`);
  try {
    const [members, expenses, balance, plan, payments] = await Promise.all([
      api(`/groups/${id}/members`), allPages(`/groups/${id}/expenses`), api(`/balances?group_id=${id}`),
      api(`/groups/${id}/settlement-suggestions`), allPages(`/groups/${id}/settlements`),
    ]);
    if (version !== state.version) return;
    Object.assign(state, { members, expenses, balance, suggestions: plan.suggestions, payments });
    $('#group-description').textContent = members.length ? 'Shared moments. Clear balances. Everything in one place.' : 'Start by adding the people who will share expenses.';
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
  $('#member-caption').textContent = state.members.length ? 'Everyone has a place at the table' : 'Add the people in your group';
  $('#settle-caption').textContent = outstanding ? `${state.suggestions.length} suggested payment${state.suggestions.length === 1 ? '' : 's'} to settle up` : 'All square. No payments needed.';
  $('#expense-count').textContent = state.expenses.length;
  renderExpenses();
  $('#suggestions').innerHTML = state.suggestions.map((payment, index) => `<article class="suggestion"><div class="suggestion-top">${avatar(payment.from_name)}<div class="suggestion-names">${escapeHTML(payment.from_name)}<span class="arrow" aria-label="pays">→</span>${escapeHTML(payment.to_name)}</div></div><div class="suggestion-bottom"><strong>${money(paise(payment.amount))}</strong><button class="record-button" data-payment="${index}">Record payment ↗</button></div></article>`).join('') || empty(state.members.length ? 'All settled up' : 'No balances yet', state.members.length ? 'Nobody owes anything right now.' : 'Add members and an expense to get started.', '✓');
  $('#members').innerHTML = state.members.length ? `<table class="member-table"><thead><tr><th>Member</th><th>Paid for group</th><th>Their share</th><th>Balance</th></tr></thead><tbody>${state.balance.members.map(member => {
    const net = paise(member.net_balance);
    return `<tr><td><div class="person-cell">${avatar(member.name)}<span>${escapeHTML(labelFor({ id: member.user_id, name: member.name }))}</span></div></td><td>${money(paise(member.paid))}</td><td>${money(paise(member.share))}</td><td><span class="net-pill ${net > 0 ? 'receives' : net < 0 ? 'owes' : 'settled'}">${net > 0 ? 'Gets back ' + money(net) : net < 0 ? 'Owes ' + money(-net) : 'Settled up'}</span></td></tr>`;
  }).join('')}</tbody></table>` : empty('Who’s joining?', 'Use “Add member” to bring your group together.', '+');
  const names = Object.fromEntries(state.members.map(member => [member.id, member.name]));
  $('#payment-count').textContent = state.payments.length;
  $('#payment-list').innerHTML = state.payments.map(payment => `<div class="payment-row"><div>${escapeHTML(names[payment.from_user_id])} <span class="muted">paid</span> ${escapeHTML(names[payment.to_user_id])}<small>${dateLabel(payment.created_at)}</small></div><strong>${money(paise(payment.amount_minor ?? payment.amount))}</strong></div>`).join('') || '<div class="empty">No payments recorded yet. Completed payments will appear here.</div>';
}

function renderExpenses() {
  const search = $('#search').value.trim().toLowerCase();
  const category = $('#category-filter').value;
  const visible = state.expenses.filter(expense => expense.description.toLowerCase().includes(search) && (!category || (expense.category || 'Other') === category));
  $('#expense-list').innerHTML = visible.map(expense => {
    const type = (expense.category || 'other').toLowerCase();
    const symbol = ({ food: '♧', travel: '↗', transport: '↗', stay: '⌂', shopping: '◇' })[type] || '▦';
    return `<details class="expense"><summary><span class="expense-icon ${['travel', 'stay', 'other'].includes(type) ? type : ''}" aria-hidden="true">${symbol}</span><span class="expense-info"><span class="expense-name">${escapeHTML(expense.description)}</span><small>Paid by ${escapeHTML(expense.payer_name)} · ${dateLabel(expense.created_at)}</small></span><span class="expense-amount">${money(paise(expense.amount))}</span><span class="chevron" aria-hidden="true">⌄</span></summary><div class="expense-details"><strong>${expense.split_type === 'equal' ? 'Shared equally' : 'Custom shares'} · ${escapeHTML(expense.category || 'Other')}</strong>${expense.splits.map(split => `<div class="share-row"><span>${escapeHTML(split.name)}</span><span>${money(paise(split.amount))}</span></div>`).join('')}</div></details>`;
  }).join('') || empty(state.expenses.length ? 'No matching expenses' : 'Your first shared moment awaits', state.expenses.length ? 'Try another search or category.' : state.members.length ? 'Tap “Add expense” when someone picks up the bill.' : 'Add group members first, then your first expense.', '₹');
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
});
$('#refresh').addEventListener('click', () => loadWorkspace());
$('#add-member').addEventListener('click', () => openDialog('member-dialog'));
$('#add-expense').addEventListener('click', () => openDialog('expense-dialog'));
$('#member-mode').addEventListener('change', setMemberMode);
$('#expense-amount').addEventListener('input', previewSplit);
$('#split-mode').addEventListener('change', previewSplit);
$('#search').addEventListener('input', renderExpenses);
$('#category-filter').addEventListener('change', renderExpenses);

$('#group-form').addEventListener('submit', event => submit(event, async data => {
  const name = data.get('name').trim();
  if (!name) throw new Error('Give your group a name.');
  const group = await api('/groups', { name });
  state.group = group.id;
  return 'Group created. Add your members next.';
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
  await api('/expenses', body);
  return 'Expense saved. Everyone’s balance is updated.';
}));
$('#payment-form').addEventListener('submit', event => submit(event, async (data, group) => {
  await api(`/groups/${group}/settlements`, { from_user_id: state.payment.from_user_id, to_user_id: state.payment.to_user_id, amount: data.get('amount') });
  return 'Payment recorded. You’re one step closer to settled.';
}));

loadWorkspace();
