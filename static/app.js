const state = {
  config: null,
  runtime: null,
  selectedWidgetId: null,
  refreshTimer: null,
  dragging: null,
  dirty: { dashboard: false, widget: false },
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
  saveWidget: document.getElementById('save-widget'),
  importConfigButton: document.getElementById('import-config-button'),
  importConfigInput: document.getElementById('import-config-input'),
  duplicateWidget: document.getElementById('duplicate-widget'),
  deleteWidget: document.getElementById('delete-widget'),
  injectFrame: document.getElementById('inject-frame'),
  simCanId: document.getElementById('sim-can-id'),
  simData: document.getElementById('sim-data'),
  widgetForm: document.getElementById('widget-form'),
  emptyState: document.getElementById('empty-state'),
  widgetTemplate: document.getElementById('widget-template'),
  fullscreenToggle: document.getElementById('fullscreen-toggle'),
  dashboardSaveStatus: document.getElementById('dashboard-save-status'),
  widgetSaveStatus: document.getElementById('widget-save-status'),
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

function updateStatusText() {
  els.dashboardSaveStatus.textContent = state.dirty.dashboard
    ? 'Dashboard changes are live in the editor. Click “Save dashboard” to write them to disk.'
    : 'Dashboard changes are saved.';
  const hasWidget = Boolean(selectedWidget());
  els.widgetSaveStatus.classList.toggle('hidden', !hasWidget);
  if (hasWidget) {
    els.widgetSaveStatus.textContent = state.dirty.widget
      ? 'Widget changes are live in the preview. Click “Save widget” to write them to disk.'
      : 'Widget changes are saved.';
  }
}

function markDirty(scope, dirty = true) {
  state.dirty[scope] = dirty;
  updateStatusText();
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
  updateStatusText();
}

function setPath(object, path, value) {
  const keys = path.split('.');
  let current = object;
  keys.forEach((key, index) => {
    const isLast = index === keys.length - 1;
    const nextKey = keys[index + 1];
    const normalizedKey = Array.isArray(current) ? Number(key) : key;
    if (isLast) {
      current[normalizedKey] = value;
      return;
    }
    if (current[normalizedKey] === undefined) current[normalizedKey] = /^\d+$/.test(nextKey) ? [] : {};
    current = current[normalizedKey];
  });
}

function getPath(object, path) {
  return path.split('.').reduce((acc, key) => {
    if (acc === undefined || acc === null) return undefined;
    return Array.isArray(acc) ? acc[Number(key)] : acc[key];
  }, object);
}

function coerceFieldValue(field, currentValue) {
  if (field.type === 'checkbox') return field.checked;
  if (field.type === 'number') {
    if (field.value === '' || Number.isNaN(field.valueAsNumber)) return currentValue ?? 0;
    return field.valueAsNumber;
  }
  return field.value;
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
    if (field.type === 'checkbox') field.checked = Boolean(value);
    else if (field.type === 'color') field.value = ensureHexColor(value, '#0f172a');
    else field.value = value ?? '';
  });
}

function createDefaultWidget() {
  const nextIndex = state.config.widgets.length + 1;
  return {
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
    alerts: [{ id: `alert-${Date.now()}`, name: 'Warning', operator: 'greater_or_equal', threshold: 90, color: '#ef4444', message: 'WARNING' }],
  };
}

function addWidget() {
  const widget = createDefaultWidget();
  state.config.widgets.push(widget);
  markDirty('widget', true);
  markDirty('dashboard', true);
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
  markDirty('widget', true);
  markDirty('dashboard', true);
  selectWidget(copy.id);
}

function deleteWidget() {
  if (!state.selectedWidgetId) return;
  state.config.widgets = state.config.widgets.filter((widget) => widget.id !== state.selectedWidgetId);
  state.selectedWidgetId = state.config.widgets[0]?.id ?? null;
  markDirty('widget', true);
  markDirty('dashboard', true);
  renderWidgetList();
  renderCanvas();
  populateWidgetForm();
}

function beginDrag(event, widgetId, resizing) {
  if (event.target.closest('input, select, button')) return;
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
  markDirty('widget', true);
  markDirty('dashboard', true);
  renderCanvas();
  populateWidgetForm();
});

window.addEventListener('pointerup', () => { state.dragging = null; });

async function persistConfig(successMessage = 'Dashboard saved.') {
  const saved = await request('/api/config', { method: 'PUT', body: JSON.stringify(state.config) });
  state.config = saved;
  markDirty('dashboard', false);
  markDirty('widget', false);
  renderWidgetList();
  renderCanvas();
  populateWidgetForm();
  els.runtimeStatus.textContent = successMessage;
  return saved;
}

async function saveConfig() {
  await persistConfig('Dashboard saved to disk.');
}

async function saveSelectedWidget() {
  if (!selectedWidget()) return;
  await persistConfig(`Saved widget: ${selectedWidget().name}`);
}

async function refreshRuntime() {
  state.runtime = await request('/api/runtime');
  if (!state.runtime.error || !String(els.runtimeStatus.textContent).includes('saved')) {
    els.runtimeStatus.textContent = state.runtime.error ? `${state.runtime.status} · ${state.runtime.error}` : state.runtime.status;
  }
  renderCanvas();
}

function wireForm() {
  const updateWidgetFromField = (field) => {
    if (!field.name) return;
    const widget = selectedWidget();
    if (!widget) return;
    const currentValue = getPath(widget, field.name);
    const value = coerceFieldValue(field, currentValue);
    setPath(widget, field.name, value);
    if (field.name === 'name') widget.display.label ||= value;
    markDirty('widget', true);
    renderWidgetList();
    renderCanvas();
  };

  els.widgetForm.addEventListener('input', (event) => updateWidgetFromField(event.target));
  els.widgetForm.addEventListener('change', (event) => updateWidgetFromField(event.target));

  [
    ['dashboard-title', 'name'],
    ['dashboard-width', 'width', (value, current) => Number.isNaN(Number(value)) ? current : Number(value)],
    ['dashboard-height', 'height', (value, current) => Number.isNaN(Number(value)) ? current : Number(value)],
    ['dashboard-bg', 'backgroundColor'],
    ['dashboard-bg-image', 'backgroundImage'],
    ['dashboard-grid', 'gridSize', (value, current) => Number.isNaN(Number(value)) ? current : Number(value)],
  ].forEach(([id, key, parser]) => {
    document.getElementById(id).addEventListener('input', (event) => {
      const current = state.config.dashboard[key];
      state.config.dashboard[key] = parser ? parser(event.target.value, current) : event.target.value;
      markDirty('dashboard', true);
      updateDashboardControls();
      renderCanvas();
    });
  });
  els.toggleGrid.addEventListener('change', (event) => {
    state.config.dashboard.showGrid = event.target.checked;
    markDirty('dashboard', true);
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

async function importConfigFromFile(file) {
  if (!file) return;
  const text = await file.text();
  const imported = JSON.parse(text);
  state.config = await request('/api/config', { method: 'PUT', body: JSON.stringify(imported) });
  state.selectedWidgetId = state.config.widgets[0]?.id ?? null;
  markDirty('dashboard', false);
  markDirty('widget', false);
  updateDashboardControls();
  renderWidgetList();
  renderCanvas();
  populateWidgetForm();
  els.runtimeStatus.textContent = `Imported configuration: ${file.name}`;
  await refreshRuntime();
}

async function toggleFullscreen() {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen();
    els.fullscreenToggle.textContent = 'Exit fullscreen';
  } else {
    await document.exitFullscreen();
    els.fullscreenToggle.textContent = 'Fullscreen';
  }
}

document.addEventListener('fullscreenchange', () => {
  els.fullscreenToggle.textContent = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen';
});

async function init() {
  state.config = await request('/api/config');
  updateDashboardControls();
  selectWidget(state.config.widgets[0]?.id ?? null);
  renderWidgetList();
  renderCanvas();
  wireForm();
  updateStatusText();
  await refreshRuntime();
  scheduleRefresh();
}

els.addWidget.addEventListener('click', addWidget);
els.saveConfig.addEventListener('click', saveConfig);
els.saveWidget.addEventListener('click', saveSelectedWidget);
els.importConfigButton.addEventListener('click', () => els.importConfigInput.click());
els.importConfigInput.addEventListener('change', async (event) => {
  try {
    await importConfigFromFile(event.target.files[0]);
  } catch (error) {
    console.error(error);
    els.runtimeStatus.textContent = `Import failed: ${error.message}`;
  } finally {
    event.target.value = '';
  }
});
els.duplicateWidget.addEventListener('click', duplicateWidget);
els.deleteWidget.addEventListener('click', deleteWidget);
els.injectFrame.addEventListener('click', injectFrame);
els.refreshRate.addEventListener('change', scheduleRefresh);
els.fullscreenToggle.addEventListener('click', toggleFullscreen);

init().catch((error) => {
  console.error(error);
  els.runtimeStatus.textContent = error.message;
});
