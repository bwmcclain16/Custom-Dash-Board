const state = {
  config: null,
  runtime: null,
  selectedWidgetId: null,
  refreshTimer: null,
  dragging: null,
};

const els = {
  canvas: document.getElementById('canvas'),
  widgetList: document.getElementById('widget-list'),
  runtimeStatus: document.getElementById('runtime-status'),
  dashboardName: document.getElementById('dashboard-name'),
  dashboardTitle: document.getElementById('dashboard-title'),
  dashboardWidth: document.getElementById('dashboard-width'),
  dashboardHeight: document.getElementById('dashboard-height'),
  dashboardBg: document.getElementById('dashboard-bg'),
  dashboardBgImage: document.getElementById('dashboard-bg-image'),
  dashboardGrid: document.getElementById('dashboard-grid'),
  toggleGrid: document.getElementById('toggle-grid'),
  refreshRate: document.getElementById('refresh-rate'),
  addWidget: document.getElementById('add-widget'),
  saveConfig: document.getElementById('save-config'),
  duplicateWidget: document.getElementById('duplicate-widget'),
  deleteWidget: document.getElementById('delete-widget'),
  injectFrame: document.getElementById('inject-frame'),
  simCanId: document.getElementById('sim-can-id'),
  simData: document.getElementById('sim-data'),
  widgetForm: document.getElementById('widget-form'),
  emptyState: document.getElementById('empty-state'),
  widgetTemplate: document.getElementById('widget-template'),
};

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function selectedWidget() {
  return state.config?.widgets.find((widget) => widget.id === state.selectedWidgetId) ?? null;
}

function ensureHexColor(value, fallback = '#0f172a') {
  if (!value) return fallback;
  if (value.startsWith('#')) return value;
  const rgba = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!rgba) return fallback;
  return '#' + rgba.slice(1, 4).map((part) => Number(part).toString(16).padStart(2, '0')).join('');
}

function updateDashboardControls() {
  const dashboard = state.config.dashboard;
  els.dashboardName.textContent = dashboard.name;
  els.dashboardTitle.value = dashboard.name;
  els.dashboardWidth.value = dashboard.width;
  els.dashboardHeight.value = dashboard.height;
  els.dashboardBg.value = ensureHexColor(dashboard.backgroundColor, '#08111f');
  els.dashboardBgImage.value = dashboard.backgroundImage || '';
  els.dashboardGrid.value = dashboard.gridSize;
  els.toggleGrid.checked = dashboard.showGrid;
}

function renderWidgetList() {
  els.widgetList.innerHTML = '';
  state.config.widgets.forEach((widget) => {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = `widget-row ${widget.id === state.selectedWidgetId ? 'active' : ''}`;
    row.innerHTML = `<strong>${widget.name}</strong><div class="tiny">${widget.source.canId} · ${widget.kind}</div>`;
    row.addEventListener('click', () => selectWidget(widget.id));
    els.widgetList.appendChild(row);
  });
}

function buildWidgetElement(widget, runtimeInfo) {
  const node = els.widgetTemplate.content.firstElementChild.cloneNode(true);
  node.dataset.widgetId = widget.id;
  node.style.left = `${widget.x}px`;
  node.style.top = `${widget.y}px`;
  node.style.width = `${widget.w}px`;
  node.style.height = `${widget.h}px`;
  node.style.zIndex = widget.z || 1;
  node.style.background = widget.display.backgroundColor;
  node.style.color = widget.display.textColor;
  node.style.border = `${widget.display.borderWidth}px solid ${widget.display.borderColor}`;
  node.style.borderRadius = `${widget.display.borderRadius}px`;
  node.style.backgroundImage = widget.display.backgroundImage ? `url(${widget.display.backgroundImage})` : 'none';
  node.classList.toggle('selected', widget.id === state.selectedWidgetId);

  const title = node.querySelector('.widget-title');
  const value = node.querySelector('.widget-value');
  const meterFill = node.querySelector('.widget-meter-fill');
  const alertNode = node.querySelector('.widget-alert');
  title.textContent = widget.display.showLabel ? (widget.display.label || widget.name) : '';
  value.textContent = widget.display.showValue ? (runtimeInfo?.formatted || '—') : '';
  meterFill.style.color = widget.display.accentColor;

  const min = Number(widget.display.min ?? 0);
  const max = Number(widget.display.max ?? 100);
  const current = Number(runtimeInfo?.value ?? 0);
  const ratio = Math.max(0, Math.min(100, ((current - min) / Math.max(1, max - min)) * 100));
  meterFill.style.width = `${ratio}%`;

  if (runtimeInfo?.alert) {
    alertNode.textContent = runtimeInfo.alert.message || runtimeInfo.alert.name || 'Alert';
    alertNode.style.background = runtimeInfo.alert.color || '#ef4444';
    alertNode.classList.remove('hidden');
  }

  node.addEventListener('pointerdown', (event) => beginDrag(event, widget.id, false));
  node.querySelector('.resize-handle').addEventListener('pointerdown', (event) => beginDrag(event, widget.id, true));
  node.addEventListener('click', () => selectWidget(widget.id));
  return node;
}

function renderCanvas() {
  const dashboard = state.config.dashboard;
  els.canvas.classList.toggle('grid', dashboard.showGrid);
  els.canvas.style.setProperty('--grid-size', `${dashboard.gridSize}px`);
  els.canvas.style.width = `${dashboard.width}px`;
  els.canvas.style.height = `${dashboard.height}px`;
  els.canvas.style.backgroundColor = dashboard.backgroundColor;
  els.canvas.style.backgroundImage = dashboard.backgroundImage ? `url(${dashboard.backgroundImage})` : 'none';
  els.canvas.innerHTML = '';
  const runtimeMap = new Map((state.runtime?.widgets || []).map((entry) => [entry.widgetId, entry]));
  [...state.config.widgets].sort((a, b) => (a.z || 1) - (b.z || 1)).forEach((widget) => {
    els.canvas.appendChild(buildWidgetElement(widget, runtimeMap.get(widget.id)));
  });
}

function selectWidget(widgetId) {
  state.selectedWidgetId = widgetId;
  renderWidgetList();
  renderCanvas();
  populateWidgetForm();
}

function setPath(object, path, value) {
  const keys = path.split('.');
  let current = object;
  keys.forEach((key, index) => {
    const isLast = index === keys.length - 1;
    const nextKey = keys[index + 1];
    if (isLast) {
      current[key] = value;
      return;
    }
    if (!(key in current)) current[key] = /^\d+$/.test(nextKey) ? [] : {};
    current = current[key];
    if (Array.isArray(current) && current.length <= Number(nextKey)) {
      current[Number(nextKey)] = {};
    }
  });
}

function getPath(object, path) {
  return path.split('.').reduce((acc, key) => acc?.[key], object);
}

function populateWidgetForm() {
  const widget = selectedWidget();
  const form = els.widgetForm;
  if (!widget) {
    form.classList.add('hidden');
    els.emptyState.classList.remove('hidden');
    return;
  }
  form.classList.remove('hidden');
  els.emptyState.classList.add('hidden');
  [...form.elements].forEach((field) => {
    if (!field.name) return;
    const value = getPath(widget, field.name);
    if (field.type === 'checkbox') {
      field.checked = Boolean(value);
    } else if (field.type === 'color') {
      field.value = ensureHexColor(value, '#0f172a');
    } else {
      field.value = value ?? '';
    }
  });
}

function addWidget() {
  const nextIndex = state.config.widgets.length + 1;
  const widget = {
    id: `widget-${Date.now()}`,
    name: `Widget ${nextIndex}`,
    kind: 'value',
    x: 100 + nextIndex * 12,
    y: 100 + nextIndex * 12,
    w: 220,
    h: 160,
    z: nextIndex,
    source: {
      canId: '0x102', startByte: 0, byteLength: 1, endian: 'little', signed: false,
      scale: 1, offset: 0, units: '', samplePeriodMs: 100, fallback: 0, valueMap: {},
    },
    display: {
      label: `Widget ${nextIndex}`, decimalPlaces: 0, prefix: '', suffix: '', min: 0, max: 100,
      backgroundColor: '#132033', textColor: '#f8fafc', accentColor: '#38bdf8', borderColor: '#38bdf8',
      borderWidth: 2, borderRadius: 20, backgroundImage: '', showLabel: true, showValue: true,
    },
    alerts: [{ id: `alert-${Date.now()}`, name: 'Warning', operator: '>=', threshold: 90, color: '#ef4444', message: 'WARNING' }],
  };
  state.config.widgets.push(widget);
  selectWidget(widget.id);
}

function duplicateWidget() {
  const widget = selectedWidget();
  if (!widget) return;
  const copy = clone(widget);
  copy.id = `widget-${Date.now()}`;
  copy.name = `${widget.name} Copy`;
  copy.x += 24;
  copy.y += 24;
  copy.z = state.config.widgets.length + 1;
  state.config.widgets.push(copy);
  selectWidget(copy.id);
}

function deleteWidget() {
  if (!state.selectedWidgetId) return;
  state.config.widgets = state.config.widgets.filter((widget) => widget.id !== state.selectedWidgetId);
  state.selectedWidgetId = state.config.widgets[0]?.id ?? null;
  renderWidgetList();
  renderCanvas();
  populateWidgetForm();
}

function beginDrag(event, widgetId, resizing) {
  event.preventDefault();
  event.stopPropagation();
  selectWidget(widgetId);
  const widget = selectedWidget();
  state.dragging = {
    widgetId,
    resizing,
    startX: event.clientX,
    startY: event.clientY,
    origin: { x: widget.x, y: widget.y, w: widget.w, h: widget.h },
  };
}

window.addEventListener('pointermove', (event) => {
  if (!state.dragging) return;
  const widget = selectedWidget();
  if (!widget) return;
  const dx = event.clientX - state.dragging.startX;
  const dy = event.clientY - state.dragging.startY;
  const grid = Number(state.config.dashboard.gridSize || 1);
  const snap = (value) => Math.round(value / grid) * grid;
  if (state.dragging.resizing) {
    widget.w = Math.max(140, snap(state.dragging.origin.w + dx));
    widget.h = Math.max(110, snap(state.dragging.origin.h + dy));
  } else {
    widget.x = Math.max(0, snap(state.dragging.origin.x + dx));
    widget.y = Math.max(0, snap(state.dragging.origin.y + dy));
  }
  renderCanvas();
  populateWidgetForm();
});

window.addEventListener('pointerup', () => { state.dragging = null; });

async function saveConfig() {
  const saved = await request('/api/config', { method: 'PUT', body: JSON.stringify(state.config) });
  state.config = saved;
  renderWidgetList();
  renderCanvas();
}

async function refreshRuntime() {
  state.runtime = await request('/api/runtime');
  els.runtimeStatus.textContent = state.runtime.error ? `${state.runtime.status} · ${state.runtime.error}` : state.runtime.status;
  renderCanvas();
}

function wireForm() {
  els.widgetForm.addEventListener('input', (event) => {
    const field = event.target;
    if (!field.name) return;
    const widget = selectedWidget();
    if (!widget) return;
    let value;
    if (field.type === 'checkbox') value = field.checked;
    else if (field.type === 'number') value = field.value === '' ? 0 : Number(field.value);
    else value = field.value;
    setPath(widget, field.name, value);
    renderWidgetList();
    renderCanvas();
  });

  [
    ['dashboard-title', 'name'],
    ['dashboard-width', 'width', Number],
    ['dashboard-height', 'height', Number],
    ['dashboard-bg', 'backgroundColor'],
    ['dashboard-bg-image', 'backgroundImage'],
    ['dashboard-grid', 'gridSize', Number],
  ].forEach(([id, key, parser]) => {
    document.getElementById(id).addEventListener('input', (event) => {
      state.config.dashboard[key] = parser ? parser(event.target.value) : event.target.value;
      renderCanvas();
      updateDashboardControls();
    });
  });
  els.toggleGrid.addEventListener('change', (event) => {
    state.config.dashboard.showGrid = event.target.checked;
    renderCanvas();
  });
}

function scheduleRefresh() {
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  state.refreshTimer = setInterval(refreshRuntime, Number(els.refreshRate.value || 250));
}

async function injectFrame() {
  const data = els.simData.value.split(',').map((value) => Number(value.trim())).filter((value) => Number.isFinite(value));
  await request('/api/inject', { method: 'POST', body: JSON.stringify({ canId: els.simCanId.value, data }) });
  await refreshRuntime();
}

async function init() {
  state.config = await request('/api/config');
  updateDashboardControls();
  selectWidget(state.config.widgets[0]?.id ?? null);
  renderWidgetList();
  renderCanvas();
  wireForm();
  await refreshRuntime();
  scheduleRefresh();
}

els.addWidget.addEventListener('click', addWidget);
els.saveConfig.addEventListener('click', saveConfig);
els.duplicateWidget.addEventListener('click', duplicateWidget);
els.deleteWidget.addEventListener('click', deleteWidget);
els.injectFrame.addEventListener('click', injectFrame);
els.refreshRate.addEventListener('change', scheduleRefresh);

init().catch((error) => {
  console.error(error);
  els.runtimeStatus.textContent = error.message;
});
