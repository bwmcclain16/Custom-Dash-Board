const state = {
  config: null,
  selectedWidgetId: null,
  liveValues: new Map(),
  drag: null,
  refreshTimer: null,
};

const els = {
  canvas: document.querySelector('#dashboard-canvas'),
  previewTitle: document.querySelector('#preview-title'),
  widgetList: document.querySelector('#widget-list'),
  widgetCount: document.querySelector('#widget-count'),
  widgetEditor: document.querySelector('#widget-editor'),
  widgetEmptyState: document.querySelector('#widget-empty-state'),
};

const dashboardFields = {
  dashboardName: document.querySelector('#dashboard-name'),
  refreshMs: document.querySelector('#refresh-ms'),
  themeBg: document.querySelector('#theme-bg'),
  themeAccent: document.querySelector('#theme-accent'),
  themeCard: document.querySelector('#theme-card'),
  themeText: document.querySelector('#theme-text'),
  themeImage: document.querySelector('#theme-image'),
  gridSize: document.querySelector('#grid-size'),
  showGrid: document.querySelector('#show-grid'),
  canMode: document.querySelector('#can-mode'),
  canChannel: document.querySelector('#can-channel'),
  canBustype: document.querySelector('#can-bustype'),
  canBitrate: document.querySelector('#can-bitrate'),
};

const widgetFields = {
  title: document.querySelector('#widget-title'),
  type: document.querySelector('#widget-type'),
  unit: document.querySelector('#widget-unit'),
  precision: document.querySelector('#widget-precision'),
  min: document.querySelector('#widget-min'),
  max: document.querySelector('#widget-max'),
  canId: document.querySelector('#widget-can-id'),
  startByte: document.querySelector('#widget-start-byte'),
  length: document.querySelector('#widget-length'),
  endianness: document.querySelector('#widget-endianness'),
  signed: document.querySelector('#widget-signed'),
  scale: document.querySelector('#widget-scale'),
  offset: document.querySelector('#widget-offset'),
  demoMin: document.querySelector('#widget-demo-min'),
  demoMax: document.querySelector('#widget-demo-max'),
  backgroundColor: document.querySelector('#widget-bg'),
  textColor: document.querySelector('#widget-text'),
  valueColor: document.querySelector('#widget-value-color'),
  borderColor: document.querySelector('#widget-border'),
  borderWidth: document.querySelector('#widget-border-width'),
  borderRadius: document.querySelector('#widget-radius'),
  backgroundImage: document.querySelector('#widget-bg-image'),
  alertsList: document.querySelector('#alerts-list'),
};

const widgetListTemplate = document.querySelector('#widget-list-item-template');
const alertTemplate = document.querySelector('#alert-template');

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function rgbaToHex(value) {
  if (!value) return '#000000';
  if (value.startsWith('#')) return value;
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!match) return '#000000';
  const [, r, g, b] = match.map(Number);
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

function hexToRgb(hex, alpha = 1) {
  const clean = hex.replace('#', '');
  const num = parseInt(clean, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return alpha === 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function getSelectedWidget() {
  return state.config?.widgets.find((widget) => widget.id === state.selectedWidgetId) ?? null;
}

function selectWidget(id) {
  state.selectedWidgetId = id;
  renderWidgetList();
  renderEditor();
  renderCanvas();
}

function buildWidget() {
  const index = state.config.widgets.length + 1;
  return {
    id: `widget-${Date.now()}`,
    type: 'numeric',
    title: `New Widget ${index}`,
    unit: '',
    position: { x: 60 + index * 20, y: 60 + index * 20, w: 220, h: 140 },
    style: {
      backgroundColor: 'rgba(15,23,42,0.92)',
      textColor: '#f8fafc',
      valueColor: state.config.settings.theme.accentColor,
      borderColor: state.config.settings.theme.accentColor,
      borderWidth: 2,
      borderRadius: 18,
      backgroundImage: '',
      fontFamily: 'Inter, sans-serif',
    },
    data: {
      canId: '0x100',
      startByte: 0,
      length: 2,
      endianness: 'big',
      signed: false,
      scale: 1,
      offset: 0,
      precision: 0,
      min: 0,
      max: 100,
      demoMin: 10,
      demoMax: 90,
    },
    alerts: [],
  };
}

function applyDashboardForm() {
  const settings = state.config.settings;
  settings.dashboardName = dashboardFields.dashboardName.value;
  settings.refreshMs = Number(dashboardFields.refreshMs.value) || 120;
  settings.gridSize = Number(dashboardFields.gridSize.value) || 20;
  settings.snapToGrid = true;
  settings.theme.backgroundColor = dashboardFields.themeBg.value;
  settings.theme.accentColor = dashboardFields.themeAccent.value;
  settings.theme.cardColor = dashboardFields.themeCard.value;
  settings.theme.textColor = dashboardFields.themeText.value;
  settings.theme.backgroundImage = dashboardFields.themeImage.value.trim();
  settings.theme.showGrid = dashboardFields.showGrid.value === 'true';
  settings.can.mode = dashboardFields.canMode.value;
  settings.can.channel = dashboardFields.canChannel.value.trim() || 'can0';
  settings.can.bustype = dashboardFields.canBustype.value.trim() || 'socketcan';
  settings.can.bitrate = Number(dashboardFields.canBitrate.value) || 500000;
  renderCanvas();
  scheduleRefresh();
}

function applyWidgetForm() {
  const widget = getSelectedWidget();
  if (!widget) return;
  widget.title = widgetFields.title.value;
  widget.type = widgetFields.type.value;
  widget.unit = widgetFields.unit.value;
  widget.data.precision = Number(widgetFields.precision.value) || 0;
  widget.data.min = Number(widgetFields.min.value) || 0;
  widget.data.max = Number(widgetFields.max.value) || 100;
  widget.data.canId = widgetFields.canId.value.trim() || '0x100';
  widget.data.startByte = Number(widgetFields.startByte.value) || 0;
  widget.data.length = Number(widgetFields.length.value) || 1;
  widget.data.endianness = widgetFields.endianness.value;
  widget.data.signed = widgetFields.signed.value === 'true';
  widget.data.scale = Number(widgetFields.scale.value) || 1;
  widget.data.offset = Number(widgetFields.offset.value) || 0;
  widget.data.demoMin = Number(widgetFields.demoMin.value) || 0;
  widget.data.demoMax = Number(widgetFields.demoMax.value) || 100;
  widget.style.backgroundColor = hexToRgb(widgetFields.backgroundColor.value, 0.92);
  widget.style.textColor = widgetFields.textColor.value;
  widget.style.valueColor = widgetFields.valueColor.value;
  widget.style.borderColor = widgetFields.borderColor.value;
  widget.style.borderWidth = Number(widgetFields.borderWidth.value) || 0;
  widget.style.borderRadius = Number(widgetFields.borderRadius.value) || 0;
  widget.style.backgroundImage = widgetFields.backgroundImage.value.trim();
  widget.alerts = Array.from(widgetFields.alertsList.querySelectorAll('.alert-row')).map((row, index) => ({
    id: `${widget.id}-alert-${index}`,
    label: row.querySelector('[data-field="label"]').value || `Alert ${index + 1}`,
    operator: row.querySelector('[data-field="operator"]').value,
    value: Number(row.querySelector('[data-field="value"]').value) || 0,
    severity: row.querySelector('[data-field="severity"]').value,
    message: row.querySelector('[data-field="message"]').value || '',
    color: row.querySelector('[data-field="color"]').value || '#f59e0b',
  }));
  renderWidgetList();
  renderCanvas();
}

function populateDashboardForm() {
  const { settings } = state.config;
  dashboardFields.dashboardName.value = settings.dashboardName;
  dashboardFields.refreshMs.value = settings.refreshMs;
  dashboardFields.themeBg.value = rgbaToHex(settings.theme.backgroundColor);
  dashboardFields.themeAccent.value = rgbaToHex(settings.theme.accentColor);
  dashboardFields.themeCard.value = rgbaToHex(settings.theme.cardColor);
  dashboardFields.themeText.value = rgbaToHex(settings.theme.textColor);
  dashboardFields.themeImage.value = settings.theme.backgroundImage || '';
  dashboardFields.gridSize.value = settings.gridSize;
  dashboardFields.showGrid.value = String(settings.theme.showGrid);
  dashboardFields.canMode.value = settings.can.mode;
  dashboardFields.canChannel.value = settings.can.channel;
  dashboardFields.canBustype.value = settings.can.bustype;
  dashboardFields.canBitrate.value = settings.can.bitrate;
}

function populateWidgetForm(widget) {
  widgetFields.title.value = widget.title;
  widgetFields.type.value = widget.type;
  widgetFields.unit.value = widget.unit;
  widgetFields.precision.value = widget.data.precision;
  widgetFields.min.value = widget.data.min;
  widgetFields.max.value = widget.data.max;
  widgetFields.canId.value = widget.data.canId;
  widgetFields.startByte.value = widget.data.startByte;
  widgetFields.length.value = widget.data.length;
  widgetFields.endianness.value = widget.data.endianness;
  widgetFields.signed.value = String(widget.data.signed);
  widgetFields.scale.value = widget.data.scale;
  widgetFields.offset.value = widget.data.offset;
  widgetFields.demoMin.value = widget.data.demoMin;
  widgetFields.demoMax.value = widget.data.demoMax;
  widgetFields.backgroundColor.value = rgbaToHex(widget.style.backgroundColor);
  widgetFields.textColor.value = rgbaToHex(widget.style.textColor);
  widgetFields.valueColor.value = rgbaToHex(widget.style.valueColor);
  widgetFields.borderColor.value = rgbaToHex(widget.style.borderColor);
  widgetFields.borderWidth.value = widget.style.borderWidth;
  widgetFields.borderRadius.value = widget.style.borderRadius;
  widgetFields.backgroundImage.value = widget.style.backgroundImage || '';
  renderAlerts(widget.alerts);
}

function renderAlerts(alerts) {
  widgetFields.alertsList.innerHTML = '';
  alerts.forEach((alert) => {
    const node = alertTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector('[data-field="label"]').value = alert.label || '';
    node.querySelector('[data-field="operator"]').value = alert.operator || '>=';
    node.querySelector('[data-field="value"]').value = alert.value ?? 0;
    node.querySelector('[data-field="severity"]').value = alert.severity || 'warning';
    node.querySelector('[data-field="message"]').value = alert.message || '';
    node.querySelector('[data-field="color"]').value = alert.color || '#f59e0b';
    node.querySelector('[data-action="remove-alert"]').addEventListener('click', () => {
      node.remove();
      applyWidgetForm();
    });
    node.querySelectorAll('input, select').forEach((field) => field.addEventListener('input', applyWidgetForm));
    widgetFields.alertsList.appendChild(node);
  });
}

function renderWidgetList() {
  els.widgetList.innerHTML = '';
  els.widgetCount.textContent = `${state.config.widgets.length} total`;
  state.config.widgets.forEach((widget) => {
    const node = widgetListTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector('.widget-list-title').textContent = widget.title;
    node.querySelector('.widget-list-meta').textContent = `${widget.type} · ${widget.data.canId}`;
    node.classList.toggle('active', widget.id === state.selectedWidgetId);
    node.addEventListener('click', () => selectWidget(widget.id));
    els.widgetList.appendChild(node);
  });
}

function renderEditor() {
  const widget = getSelectedWidget();
  const visible = Boolean(widget);
  els.widgetEditor.classList.toggle('hidden', !visible);
  els.widgetEmptyState.classList.toggle('hidden', visible);
  if (widget) populateWidgetForm(widget);
}

function formatValue(widget, value) {
  if (value == null) return '--';
  const precision = Number(widget.data.precision || 0);
  return Number(value).toFixed(precision);
}

function renderCanvas() {
  const { settings, widgets } = state.config;
  els.previewTitle.textContent = settings.dashboardName || 'Dashboard Preview';
  els.canvas.innerHTML = '';
  els.canvas.classList.toggle('grid', Boolean(settings.theme.showGrid));
  els.canvas.style.backgroundColor = settings.theme.backgroundColor;
  els.canvas.style.backgroundImage = settings.theme.backgroundImage
    ? `${settings.theme.showGrid ? 'linear-gradient(to right, rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.06) 1px, transparent 1px), ' : ''}url("${settings.theme.backgroundImage}")`
    : '';
  if (settings.theme.showGrid) {
    els.canvas.style.backgroundSize = `${settings.gridSize}px ${settings.gridSize}px, ${settings.gridSize}px ${settings.gridSize}px, cover`;
  } else {
    els.canvas.style.backgroundSize = 'cover';
  }

  widgets.forEach((widget) => {
    const live = state.liveValues.get(widget.id) || {};
    const alert = live.alert;
    const node = document.createElement('div');
    node.className = `dashboard-widget ${widget.id === state.selectedWidgetId ? 'selected' : ''} ${alert?.severity || ''}`.trim();
    node.dataset.widgetId = widget.id;
    node.style.left = `${widget.position.x}px`;
    node.style.top = `${widget.position.y}px`;
    node.style.width = `${widget.position.w}px`;
    node.style.height = `${widget.position.h}px`;
    node.style.background = widget.style.backgroundImage
      ? `${widget.style.backgroundColor} url("${widget.style.backgroundImage}") center / cover no-repeat`
      : widget.style.backgroundColor;
    node.style.color = widget.style.textColor;
    node.style.border = `${widget.style.borderWidth}px solid ${widget.style.borderColor}`;
    node.style.borderRadius = `${widget.style.borderRadius}px`;
    node.style.fontFamily = widget.style.fontFamily || 'Inter, sans-serif';

    const value = formatValue(widget, live.value);
    const range = Math.max(1, Number(widget.data.max) - Number(widget.data.min));
    const percentage = live.value == null ? 0 : Math.min(100, Math.max(0, ((live.value - widget.data.min) / range) * 100));

    node.innerHTML = `
      <div class="widget-header">
        <div class="widget-title">${widget.title}</div>
        <div>${widget.data.canId}</div>
      </div>
      <div class="widget-value" style="color:${widget.style.valueColor}">${value}<small>${widget.unit ? ` ${widget.unit}` : ''}</small></div>
      ${widget.type === 'gauge' ? `<div class="widget-gauge-bar"><div class="widget-gauge-fill" style="width:${percentage}%; background:${widget.style.valueColor}"></div></div>` : ''}
      <div class="widget-footer">
        <span>${live.stale ? 'Awaiting data' : 'Live data'}</span>
        ${alert ? `<span class="widget-alert" style="background:${alert.color || '#f59e0b'}">${alert.message || alert.label}</span>` : '<span></span>'}
      </div>
      <div class="widget-resizer"></div>
    `;

    node.addEventListener('pointerdown', onPointerDown);
    node.addEventListener('click', () => selectWidget(widget.id));
    els.canvas.appendChild(node);
  });
}

function onPointerDown(event) {
  const widgetId = event.currentTarget.dataset.widgetId;
  const widget = state.config.widgets.find((item) => item.id === widgetId);
  if (!widget) return;

  selectWidget(widgetId);

  const rect = event.currentTarget.getBoundingClientRect();
  const canvasRect = els.canvas.getBoundingClientRect();
  const resizing = event.target.classList.contains('widget-resizer');

  state.drag = {
    widgetId,
    resizing,
    startX: event.clientX,
    startY: event.clientY,
    origin: { ...widget.position },
    canvasRect,
  };

  event.currentTarget.setPointerCapture(event.pointerId);
}

function snap(value) {
  const gridSize = Number(state.config.settings.gridSize) || 20;
  return Math.round(value / gridSize) * gridSize;
}

function onPointerMove(event) {
  if (!state.drag) return;
  const widget = state.config.widgets.find((item) => item.id === state.drag.widgetId);
  if (!widget) return;

  const deltaX = event.clientX - state.drag.startX;
  const deltaY = event.clientY - state.drag.startY;

  if (state.drag.resizing) {
    widget.position.w = Math.max(120, snap(state.drag.origin.w + deltaX));
    widget.position.h = Math.max(90, snap(state.drag.origin.h + deltaY));
  } else {
    widget.position.x = Math.max(0, snap(state.drag.origin.x + deltaX));
    widget.position.y = Math.max(0, snap(state.drag.origin.y + deltaY));
  }
  renderCanvas();
}

function onPointerUp() {
  state.drag = null;
}

async function saveConfig() {
  applyDashboardForm();
  applyWidgetForm();
  state.config = await request('/api/config', {
    method: 'POST',
    body: JSON.stringify(state.config),
  });
  renderWidgetList();
  renderCanvas();
}

async function loadConfig() {
  state.config = await request('/api/config');
  if (!state.selectedWidgetId && state.config.widgets.length) {
    state.selectedWidgetId = state.config.widgets[0].id;
  }
  populateDashboardForm();
  renderWidgetList();
  renderEditor();
  renderCanvas();
}

async function refreshValues() {
  if (!state.config) return;
  const liveState = await request('/api/state');
  liveState.widgets.forEach((widgetState) => {
    state.liveValues.set(widgetState.id, widgetState);
  });
  renderCanvas();
}

function bindEvents() {
  document.querySelector('#add-widget-btn').addEventListener('click', () => {
    const widget = buildWidget();
    state.config.widgets.push(widget);
    selectWidget(widget.id);
  });
  document.querySelector('#delete-widget-btn').addEventListener('click', () => {
    if (!state.selectedWidgetId) return;
    state.config.widgets = state.config.widgets.filter((widget) => widget.id !== state.selectedWidgetId);
    state.selectedWidgetId = state.config.widgets[0]?.id ?? null;
    renderWidgetList();
    renderEditor();
    renderCanvas();
  });
  document.querySelector('#save-btn').addEventListener('click', saveConfig);
  document.querySelector('#reset-btn').addEventListener('click', async () => {
    state.config = await request('/api/demo-reset', { method: 'POST', body: '{}' });
    state.selectedWidgetId = state.config.widgets[0]?.id ?? null;
    populateDashboardForm();
    renderWidgetList();
    renderEditor();
    renderCanvas();
  });
  document.querySelector('#add-alert-btn').addEventListener('click', () => {
    const widget = getSelectedWidget();
    if (!widget) return;
    widget.alerts.push({
      id: `${widget.id}-alert-${widget.alerts.length}`,
      label: `Alert ${widget.alerts.length + 1}`,
      operator: '>=',
      value: widget.data.max,
      severity: 'warning',
      message: '',
      color: '#f59e0b',
    });
    renderAlerts(widget.alerts);
    applyWidgetForm();
  });

  Object.values(dashboardFields).forEach((field) => field.addEventListener('input', applyDashboardForm));
  Object.values(widgetFields)
    .filter((field) => field instanceof HTMLElement && field !== widgetFields.alertsList)
    .forEach((field) => field.addEventListener('input', applyWidgetForm));

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
}

function scheduleRefresh() {
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  const interval = Math.max(50, Number(state.config?.settings?.refreshMs) || 250);
  state.refreshTimer = setInterval(refreshValues, interval);
}

async function init() {
  bindEvents();
  await loadConfig();
  await refreshValues();
  scheduleRefresh();
}

init().catch((error) => {
  console.error(error);
  alert(`Failed to load dashboard: ${error.message}`);
});
