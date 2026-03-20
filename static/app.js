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
  dashboardBgUploadButton: document.getElementById('dashboard-bg-upload-button'),
  dashboardBgUpload: document.getElementById('dashboard-bg-upload'),
  dashboardBgStatus: document.getElementById('dashboard-bg-status'),
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
  widgetBgUploadButton: document.getElementById('widget-bg-upload-button'),
  widgetBgUpload: document.getElementById('widget-bg-upload'),
  widgetBgStatus: document.getElementById('widget-bg-status'),
  dashboardFullscreenToggle: document.getElementById('dashboard-fullscreen-toggle'),
  dashboardSaveStatus: document.getElementById('dashboard-save-status'),
  widgetSaveStatus: document.getElementById('widget-save-status'),
  screenAlertOverlay: document.getElementById('screen-alert-overlay'),
  screenAlertMessage: document.getElementById('screen-alert-message'),
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

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('Unable to read image file'));
    reader.readAsDataURL(file);
  });
}

function hexToRgb(hex) {
  const normalized = ensureHexColor(hex, '#000000').replace('#', '');
  return {
    r: parseInt(normalized.slice(0, 2), 16),
    g: parseInt(normalized.slice(2, 4), 16),
    b: parseInt(normalized.slice(4, 6), 16),
  };
}

function rgbToHex({ r, g, b }) {
  return '#' + [r, g, b].map((value) => Math.round(value).toString(16).padStart(2, '0')).join('');
}

function mixColor(start, end, ratio) {
  const a = hexToRgb(start);
  const b = hexToRgb(end);
  return rgbToHex({
    r: a.r + (b.r - a.r) * ratio,
    g: a.g + (b.g - a.g) * ratio,
    b: a.b + (b.b - a.b) * ratio,
  });
}

function gaugeColor(display, ratio) {
  const gauge = display.gauge || {};
  if (!gauge.useGradient) return display.accentColor;
  const start = gauge.gradientStartColor || '#22c55e';
  const mid = gauge.gradientMidColor || '#facc15';
  const end = gauge.gradientEndColor || '#ef4444';
  return ratio < 50 ? mixColor(start, mid, ratio / 50) : mixColor(mid, end, (ratio - 50) / 50);
}

function isCanvasFullscreen() {
  return document.fullscreenElement === els.canvas;
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
  els.dashboardBgStatus.textContent = dashboard.backgroundImage ? 'Dashboard background uploaded.' : 'No background image uploaded.';
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

function getWidgetLayout(widget) {
  const layout = widget.display.layout || {};
  return {
    labelX: Number(layout.labelX ?? 16),
    labelY: Number(layout.labelY ?? 16),
    valueX: Number(layout.valueX ?? 16),
    valueY: Number(layout.valueY ?? 52),
    labelAlign: layout.labelAlign || 'left',
    valueAlign: layout.valueAlign || 'left',
  };
}

function getGaugeSettings(widget) {
  const gauge = widget.display.gauge || {};
  return {
    useGradient: Boolean(gauge.useGradient),
    gradientStartColor: gauge.gradientStartColor || '#22c55e',
    gradientMidColor: gauge.gradientMidColor || '#facc15',
    gradientEndColor: gauge.gradientEndColor || '#ef4444',
    tickCount: Math.max(3, Number(gauge.tickCount ?? 11)),
    majorTickEvery: Math.max(1, Number(gauge.majorTickEvery ?? 2)),
    startAngle: Number(gauge.startAngle ?? -120),
    endAngle: Number(gauge.endAngle ?? 120),
  };
}

function applyMovableLayout(element, x, y, align) {
  element.style.left = `${x}px`;
  element.style.top = `${y}px`;
  element.style.textAlign = align;
  element.style.transform = align === 'center' ? 'translateX(-50%)' : align === 'right' ? 'translateX(-100%)' : 'none';
}

function alignAnchor(align) {
  if (align === 'center') return 0.5;
  if (align === 'right') return 1;
  return 0;
}

function renderGaugeMarks(container, settings) {
  container.innerHTML = '';
  const span = settings.endAngle - settings.startAngle;
  for (let index = 0; index < settings.tickCount; index += 1) {
    const mark = document.createElement('div');
    const ratio = settings.tickCount === 1 ? 0 : index / (settings.tickCount - 1);
    const angle = settings.startAngle + span * ratio;
    mark.className = `widget-gauge-mark ${index % settings.majorTickEvery === 0 ? 'major' : ''}`;
    mark.style.transform = `translate(-50%, -100%) rotate(${angle}deg) translateY(-120%)`;
    container.appendChild(mark);
  }
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
  const meter = node.querySelector('.widget-meter');
  const meterFill = node.querySelector('.widget-meter-fill');
  const gauge = node.querySelector('.widget-gauge');
  const gaugeRing = node.querySelector('.widget-gauge-ring');
  const gaugeNeedle = node.querySelector('.widget-gauge-needle');
  const gaugeMarks = node.querySelector('.widget-gauge-marks');
  const statusDot = node.querySelector('.widget-status-dot');
  const alertNode = node.querySelector('.widget-alert');

  const layout = getWidgetLayout(widget);
  title.textContent = widget.display.showLabel ? (widget.display.label || widget.name) : '';
  value.textContent = widget.display.showValue ? (runtimeInfo?.formatted || '—') : '';
  title.classList.toggle('hidden', !widget.display.showLabel);
  value.classList.toggle('hidden', !widget.display.showValue);
  applyMovableLayout(title, layout.labelX, layout.labelY, layout.labelAlign);
  applyMovableLayout(value, layout.valueX, layout.valueY, layout.valueAlign);

  const min = Number(widget.display.min ?? 0);
  const max = Number(widget.display.max ?? 100);
  const current = Number(runtimeInfo?.value ?? 0);
  const ratio = clamp(((current - min) / Math.max(1, max - min)) * 100, 0, 100);
  const color = gaugeColor(widget.display, ratio);
  meterFill.style.color = color;
  statusDot.style.color = color;
  gaugeRing.style.color = color;
  gaugeNeedle.style.color = color;
  meterFill.style.width = `${ratio}%`;

  const gaugeSettings = getGaugeSettings(widget);
  const span = gaugeSettings.endAngle - gaugeSettings.startAngle;
  const needleAngle = gaugeSettings.startAngle + span * (ratio / 100);
  gaugeRing.style.background = `conic-gradient(from ${gaugeSettings.startAngle}deg, ${color} 0deg ${Math.max(0, span * (ratio / 100))}deg, rgba(255,255,255,0.08) ${Math.max(0, span * (ratio / 100))}deg ${Math.max(0, span)}deg, transparent ${Math.max(0, span)}deg 360deg)`;
  gaugeNeedle.style.transform = `rotate(${needleAngle}deg)`;
  renderGaugeMarks(gaugeMarks, gaugeSettings);
  statusDot.style.opacity = `${0.35 + ratio / 150}`;

  meter.classList.toggle('hidden', (widget.kind === 'gauge') || widget.kind === 'status');
  gauge.classList.toggle('hidden', !(widget.kind === 'gauge' || widget.kind === 'gauge_value'));
  statusDot.classList.toggle('hidden', widget.kind !== 'status');
  meter.style.height = widget.kind === 'bar' ? '22px' : '14px';

  if (runtimeInfo?.alert) {
    alertNode.textContent = runtimeInfo.alert.message || runtimeInfo.alert.name || 'Alert';
    alertNode.style.background = runtimeInfo.alert.color || '#ef4444';
    alertNode.classList.remove('hidden');
    if (runtimeInfo.alert.effect === 'widget_only') {
      node.style.boxShadow = `0 0 0 3px ${runtimeInfo.alert.color || '#ef4444'}, 0 0 30px ${runtimeInfo.alert.color || '#ef4444'}`;
    }
  } else {
    node.style.boxShadow = 'none';
  }

  node.addEventListener('pointerdown', (event) => beginWidgetDrag(event, widget.id, 'move'));
  node.querySelector('.resize-handle').addEventListener('pointerdown', (event) => beginWidgetDrag(event, widget.id, 'resize'));
  node.querySelectorAll('.movable-part').forEach((partNode) => {
    partNode.addEventListener('pointerdown', (event) => beginPartDrag(event, widget.id, partNode.dataset.part));
  });
  node.addEventListener('click', () => selectWidget(widget.id));
  return node;
}

function ensureCanvasAlertLayer() {
  let layer = els.canvas.querySelector('.canvas-alert-layer');
  if (!layer) {
    layer = document.createElement('div');
    layer.className = 'canvas-alert-layer hidden';
    els.canvas.appendChild(layer);
  }
  return layer;
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
  const canvasAlertLayer = ensureCanvasAlertLayer();
  const runtimeMap = new Map((state.runtime?.widgets || []).map((entry) => [entry.widgetId, entry]));
  [...state.config.widgets].sort((a, b) => (a.z || 1) - (b.z || 1)).forEach((widget) => {
    els.canvas.appendChild(buildWidgetElement(widget, runtimeMap.get(widget.id)));
  });
  applyDashboardAlertLayer(canvasAlertLayer);
  applyScreenAlertOverlay();
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
  els.widgetBgStatus.textContent = widget.display.backgroundImage ? 'Widget background uploaded.' : 'No widget background uploaded.';
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
      layout: { labelX: 16, labelY: 16, valueX: 16, valueY: 52, labelAlign: 'left', valueAlign: 'left' },
      gauge: { useGradient: false, gradientStartColor: '#22c55e', gradientMidColor: '#facc15', gradientEndColor: '#ef4444', tickCount: 11, majorTickEvery: 2, startAngle: -120, endAngle: 120 },
    },
    alerts: [{ id: `alert-${Date.now()}`, name: 'Warning', operator: 'greater_or_equal', threshold: 90, color: '#ef4444', message: 'WARNING', effect: 'widget_only' }],
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

function beginWidgetDrag(event, widgetId, mode) {
  if (isCanvasFullscreen() || event.target.closest('input, select, button') || event.target.closest('.movable-part')) return;
  event.preventDefault();
  event.stopPropagation();
  selectWidget(widgetId);
  const widget = selectedWidget();
  state.dragging = {
    type: mode,
    widgetId,
    startX: event.clientX,
    startY: event.clientY,
    origin: { x: widget.x, y: widget.y, w: widget.w, h: widget.h },
  };
}

function beginPartDrag(event, widgetId, part) {
  if (isCanvasFullscreen()) return;
  event.preventDefault();
  event.stopPropagation();
  selectWidget(widgetId);
  const widget = selectedWidget();
  const layout = getWidgetLayout(widget);
  const keyX = part === 'label' ? 'labelX' : 'valueX';
  const keyY = part === 'label' ? 'labelY' : 'valueY';
  state.dragging = {
    type: 'part',
    widgetId,
    part,
    startX: event.clientX,
    startY: event.clientY,
    origin: { x: Number(layout[keyX]), y: Number(layout[keyY]) },
  };
}

window.addEventListener('pointermove', (event) => {
  if (!state.dragging || isCanvasFullscreen()) return;
  const widget = selectedWidget();
  if (!widget) return;
  const dx = event.clientX - state.dragging.startX;
  const dy = event.clientY - state.dragging.startY;
  const grid = Number(state.config.dashboard.gridSize || 1);
  const snap = (value) => Math.round(value / grid) * grid;

  if (state.dragging.type === 'resize') {
    widget.w = Math.max(140, snap(state.dragging.origin.w + dx));
    widget.h = Math.max(110, snap(state.dragging.origin.h + dy));
  } else if (state.dragging.type === 'move') {
    widget.x = Math.max(0, snap(state.dragging.origin.x + dx));
    widget.y = Math.max(0, snap(state.dragging.origin.y + dy));
  } else if (state.dragging.type === 'part') {
    const layout = widget.display.layout ||= {};
    const partPrefix = state.dragging.part === 'label' ? 'label' : 'value';
    const align = layout[`${partPrefix}Align`] || 'left';
    const anchor = alignAnchor(align);
    const maxX = widget.w - 16;
    const newX = clamp(snap(state.dragging.origin.x + dx), 12 + (anchor * 60), maxX);
    const newY = clamp(snap(state.dragging.origin.y + dy), 8, widget.h - 36);
    layout[`${partPrefix}X`] = newX;
    layout[`${partPrefix}Y`] = newY;
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

function applyDashboardAlertLayer(layer) {
  const backgroundAlert = (state.runtime?.widgets || [])
    .map((entry) => entry.alert)
    .find((alert) => alert && alert.effect === 'background_flash');
  if (!backgroundAlert) {
    layer.className = 'canvas-alert-layer hidden';
    layer.style.background = 'transparent';
    return;
  }
  layer.className = 'canvas-alert-layer flash';
  layer.style.background = backgroundAlert.color || '#ef4444';
}

function applyScreenAlertOverlay() {
  const activeAlert = (state.runtime?.widgets || [])
    .map((entry) => entry.alert)
    .find((alert) => alert && (alert.effect === 'screen_flash' || alert.effect === 'screen_solid'));

  if (!activeAlert) {
    els.screenAlertOverlay.className = 'screen-alert-overlay hidden';
    els.screenAlertOverlay.style.background = 'transparent';
    els.screenAlertMessage.textContent = '';
    return;
  }

  els.screenAlertOverlay.className = `screen-alert-overlay ${activeAlert.effect === 'screen_flash' ? 'flash' : ''}`.trim();
  els.screenAlertOverlay.style.background = activeAlert.color || '#ef4444';
  els.screenAlertMessage.textContent = activeAlert.message || activeAlert.name || 'ALERT';
}

async function refreshRuntime() {
  state.runtime = await request('/api/runtime');
  if (!state.runtime.error || !String(els.runtimeStatus.textContent).includes('Saved')) {
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
    if (field.name === 'name' && !widget.display.label) widget.display.label = value;
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

  els.dashboardBgUploadButton.addEventListener('click', () => els.dashboardBgUpload.click());
  els.dashboardBgUpload.addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    state.config.dashboard.backgroundImage = await readFileAsDataUrl(file);
    els.dashboardBgStatus.textContent = `Dashboard background: ${file.name}`;
    markDirty('dashboard', true);
    renderCanvas();
    event.target.value = '';
  });

  els.widgetBgUploadButton.addEventListener('click', () => els.widgetBgUpload.click());
  els.widgetBgUpload.addEventListener('change', async (event) => {
    const file = event.target.files[0];
    const widget = selectedWidget();
    if (!file || !widget) return;
    widget.display.backgroundImage = await readFileAsDataUrl(file);
    els.widgetBgStatus.textContent = `Widget background: ${file.name}`;
    markDirty('widget', true);
    renderCanvas();
    event.target.value = '';
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

async function toggleDashboardFullscreen() {
  if (document.fullscreenElement === els.canvas) {
    await document.exitFullscreen();
    return;
  }
  await els.canvas.requestFullscreen();
}

document.addEventListener('fullscreenchange', () => {
  els.dashboardFullscreenToggle.textContent = document.fullscreenElement === els.canvas
    ? 'Exit dashboard fullscreen'
    : 'Dashboard fullscreen';
  renderCanvas();
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
els.dashboardFullscreenToggle.addEventListener('click', toggleDashboardFullscreen);

init().catch((error) => {
  console.error(error);
  els.runtimeStatus.textContent = error.message;
});
