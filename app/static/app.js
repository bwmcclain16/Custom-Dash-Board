const state = {
  config: null,
  values: {},
  alerts: {},
  selectedWidgetId: null,
  drag: null,
};

const $ = (selector) => document.querySelector(selector);
const canvas = $('#dashboard-canvas');
const alertTemplate = $('#alert-template');

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  return response.json();
}

function uid(prefix = 'item') {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function clone(obj) {
  return structuredClone(obj);
}

function selectedWidget() {
  return state.config.widgets.find((widget) => widget.id === state.selectedWidgetId);
}

function bindInputs() {
  $('#dash-name').addEventListener('input', (e) => { state.config.name = e.target.value; render(); });
  $('#dash-width').addEventListener('input', (e) => { state.config.width = Number(e.target.value); render(); });
  $('#dash-height').addEventListener('input', (e) => { state.config.height = Number(e.target.value); render(); });
  $('#theme-background').addEventListener('input', (e) => { state.config.theme.background_color = e.target.value; render(); });
  $('#theme-grid').addEventListener('input', (e) => { state.config.theme.grid_color = hexToRgba(e.target.value, 0.18); render(); });
  $('#theme-image').addEventListener('input', (e) => { state.config.theme.background_image = e.target.value; render(); });

  $('#widget-picker').addEventListener('change', (e) => {
    state.selectedWidgetId = e.target.value;
    render();
  });

  const widgetMappings = {
    '#widget-title': ['title', String],
    '#widget-kind': ['kind', String],
    '#widget-unit': ['unit', String],
    '#widget-description': ['description', String],
    '#widget-precision': ['precision', Number],
    '#widget-min': ['min_value', Number],
    '#widget-max': ['max_value', Number],
    '#widget-warning': ['warning_text', String],
  };
  Object.entries(widgetMappings).forEach(([selector, [field, caster]]) => {
    $(selector).addEventListener('input', (e) => {
      const widget = selectedWidget();
      if (!widget) return;
      widget[field] = caster(e.target.value);
      render();
    });
  });

  const sourceMappings = {
    '#source-can-id': ['can_id', String],
    '#source-type': ['data_type', String],
    '#source-start': ['start_byte', Number],
    '#source-length': ['length', Number],
    '#source-bit': ['bit_index', (v) => (v === '' ? null : Number(v))],
    '#source-scale': ['scale', Number],
    '#source-offset': ['offset', Number],
    '#source-signed': ['signed', (v) => v === 'true'],
    '#source-endian': ['endianness', String],
  };
  Object.entries(sourceMappings).forEach(([selector, [field, caster]]) => {
    $(selector).addEventListener('input', (e) => {
      const widget = selectedWidget();
      if (!widget) return;
      widget.source[field] = caster(e.target.value);
      render();
    });
  });

  const styleMappings = {
    '#style-bg': ['background_color', String],
    '#style-text': ['text_color', String],
    '#style-accent': ['accent_color', String],
    '#style-border': ['border_color', String],
    '#style-border-width': ['border_width', Number],
    '#style-radius': ['border_radius', Number],
    '#style-font': ['font_size', Number],
    '#style-value-font': ['value_font_size', Number],
    '#style-image': ['background_image', String],
    '#style-show-border': ['show_border', (v) => v === 'true'],
  };
  Object.entries(styleMappings).forEach(([selector, [field, caster]]) => {
    $(selector).addEventListener('input', (e) => {
      const widget = selectedWidget();
      if (!widget) return;
      widget.style[field] = caster(e.target.value);
      render();
    });
  });

  $('#add-widget').addEventListener('click', () => {
    const widget = {
      id: uid('widget'),
      title: 'New Widget',
      kind: 'value',
      unit: '',
      description: '',
      source: { can_id: '0x100', start_byte: 0, length: 2, endianness: 'little', signed: false, scale: 1, offset: 0, data_type: 'int', bit_index: null },
      style: { background_color: '#111827', text_color: '#f3f4f6', accent_color: '#38bdf8', border_color: '#334155', border_width: 2, border_radius: 14, background_image: '', font_family: 'Inter, sans-serif', font_size: 18, value_font_size: 34, show_border: true },
      layout: { x: 40, y: 40, width: 240, height: 160, z_index: 1 },
      precision: 1,
      min_value: 0,
      max_value: 100,
      warning_text: '',
      alerts: [],
    };
    state.config.widgets.push(widget);
    state.selectedWidgetId = widget.id;
    render();
  });

  $('#duplicate-widget').addEventListener('click', () => {
    const widget = selectedWidget();
    if (!widget) return;
    const duplicated = clone(widget);
    duplicated.id = uid('widget');
    duplicated.title = `${widget.title} Copy`;
    duplicated.layout.x += 28;
    duplicated.layout.y += 28;
    duplicated.alerts = duplicated.alerts.map((alert) => ({ ...alert, id: uid('alert') }));
    state.config.widgets.push(duplicated);
    state.selectedWidgetId = duplicated.id;
    render();
  });

  $('#delete-widget').addEventListener('click', () => {
    const index = state.config.widgets.findIndex((widget) => widget.id === state.selectedWidgetId);
    if (index < 0) return;
    state.config.widgets.splice(index, 1);
    state.selectedWidgetId = state.config.widgets[0]?.id ?? null;
    render();
  });

  $('#add-alert').addEventListener('click', () => {
    const widget = selectedWidget();
    if (!widget) return;
    widget.alerts.push({
      id: uid('alert'),
      label: 'Custom alert',
      comparator: 'gt',
      threshold: 0,
      secondary_threshold: null,
      color: '#ff4d4f',
      background_color: 'rgba(255,77,79,0.2)',
      message: 'Threshold reached',
    });
    render();
  });

  $('#save-config').addEventListener('click', async () => {
    state.config = await fetchJson('/api/config', { method: 'POST', body: JSON.stringify(state.config) });
    render();
  });

  $('#apply-bus').addEventListener('click', async () => {
    const payload = {
      interface: $('#bus-interface').value,
      channel: $('#bus-channel').value,
      bitrate: Number($('#bus-bitrate').value),
    };
    await fetchJson('/api/bus', { method: 'POST', body: JSON.stringify(payload) });
    pollState();
  });
}

function renderForm() {
  $('#dash-name').value = state.config.name;
  $('#dash-width').value = state.config.width;
  $('#dash-height').value = state.config.height;
  $('#theme-background').value = state.config.theme.background_color;
  $('#theme-grid').value = rgbaToHex(state.config.theme.grid_color);
  $('#theme-image').value = state.config.theme.background_image || '';

  const picker = $('#widget-picker');
  picker.innerHTML = state.config.widgets.map((widget) => `<option value="${widget.id}">${widget.title}</option>`).join('');
  if (!state.selectedWidgetId && state.config.widgets.length) {
    state.selectedWidgetId = state.config.widgets[0].id;
  }
  picker.value = state.selectedWidgetId || '';

  const widget = selectedWidget();
  if (!widget) return;
  $('#widget-title').value = widget.title;
  $('#widget-kind').value = widget.kind;
  $('#widget-unit').value = widget.unit;
  $('#widget-description').value = widget.description;
  $('#widget-precision').value = widget.precision;
  $('#widget-min').value = widget.min_value;
  $('#widget-max').value = widget.max_value;
  $('#widget-warning').value = widget.warning_text || '';

  $('#source-can-id').value = widget.source.can_id;
  $('#source-type').value = widget.source.data_type;
  $('#source-start').value = widget.source.start_byte;
  $('#source-length').value = widget.source.length;
  $('#source-bit').value = widget.source.bit_index ?? '';
  $('#source-scale').value = widget.source.scale;
  $('#source-offset').value = widget.source.offset;
  $('#source-signed').value = String(widget.source.signed);
  $('#source-endian').value = widget.source.endianness;

  $('#style-bg').value = widget.style.background_color;
  $('#style-text').value = widget.style.text_color;
  $('#style-accent').value = widget.style.accent_color;
  $('#style-border').value = widget.style.border_color;
  $('#style-border-width').value = widget.style.border_width;
  $('#style-radius').value = widget.style.border_radius;
  $('#style-font').value = widget.style.font_size;
  $('#style-value-font').value = widget.style.value_font_size;
  $('#style-image').value = widget.style.background_image || '';
  $('#style-show-border').value = String(widget.style.show_border);

  renderAlerts(widget);
}

function renderAlerts(widget) {
  const container = $('#alerts-list');
  container.innerHTML = '';
  widget.alerts.forEach((alert) => {
    const fragment = alertTemplate.content.cloneNode(true);
    const card = fragment.querySelector('.alert-card');
    card.querySelectorAll('[data-field]').forEach((input) => {
      const field = input.dataset.field;
      const rawValue = alert[field] ?? '';
      input.value = field.includes('color') ? normalizeColor(rawValue) : rawValue;
      input.addEventListener('input', (event) => {
        alert[field] = input.type === 'number' ? Number(event.target.value) : event.target.value;
      });
    });
    card.querySelector('[data-action="remove-alert"]').addEventListener('click', () => {
      widget.alerts = widget.alerts.filter((item) => item.id !== alert.id);
      render();
    });
    container.appendChild(fragment);
  });
}

function renderCanvas() {
  canvas.style.width = `${state.config.width}px`;
  canvas.style.height = `${state.config.height}px`;
  canvas.style.backgroundColor = state.config.theme.background_color;
  canvas.style.backgroundImage = state.config.theme.background_image ? `url(${state.config.theme.background_image})` : 'none';
  canvas.style.setProperty('--grid-color', state.config.theme.grid_color);

  canvas.innerHTML = '';
  state.config.widgets.forEach((widget) => {
    const node = document.createElement('article');
    node.className = `widget ${widget.id === state.selectedWidgetId ? 'selected' : ''}`;
    node.style.left = `${widget.layout.x}px`;
    node.style.top = `${widget.layout.y}px`;
    node.style.width = `${widget.layout.width}px`;
    node.style.height = `${widget.layout.height}px`;
    node.style.zIndex = widget.layout.z_index;
    node.style.backgroundColor = widget.style.background_color;
    node.style.color = widget.style.text_color;
    node.style.backgroundImage = widget.style.background_image ? `linear-gradient(rgba(2,6,23,0.15), rgba(2,6,23,0.3)), url(${widget.style.background_image})` : 'none';
    node.style.borderRadius = `${widget.style.border_radius}px`;
    node.style.border = widget.style.show_border ? `${widget.style.border_width}px solid ${widget.style.border_color}` : 'none';
    node.style.fontFamily = widget.style.font_family;

    const value = state.values[widget.id];
    const activeAlerts = state.alerts[widget.id] || [];
    const percent = typeof value === 'number' ? Math.min(100, Math.max(0, ((value - widget.min_value) / (widget.max_value - widget.min_value || 1)) * 100)) : 0;

    node.innerHTML = `
      <div>
        <div class="widget-title" style="font-size:${widget.style.font_size}px">${widget.title}</div>
        <div class="widget-subtitle">${widget.description || widget.source.can_id}</div>
      </div>
      <div>
        <div class="widget-value" style="font-size:${widget.style.value_font_size}px">${formatValue(widget, value)}</div>
        ${renderVisualization(widget, percent, value)}
      </div>
      <div class="widget-alerts">
        ${activeAlerts.map((message) => `<span class="widget-alert" style="background:${widget.style.accent_color}; color:#fff;">${message}</span>`).join('')}
      </div>
    `;

    node.addEventListener('pointerdown', (event) => startDrag(event, widget));
    node.addEventListener('click', () => {
      state.selectedWidgetId = widget.id;
      render();
    });
    canvas.appendChild(node);
  });
}

function renderVisualization(widget, percent, value) {
  if (widget.kind === 'status') {
    const active = Boolean(value);
    return `<div class="status-pill" style="background:${active ? widget.style.accent_color : 'rgba(148,163,184,0.2)'}; color:${active ? '#fff' : widget.style.text_color}">${active ? 'ACTIVE' : 'OK'}</div>`;
  }
  if (widget.kind === 'gauge') {
    return `<div class="gauge-track"><div class="gauge-fill" style="width:${percent}%; background:${widget.style.accent_color}"></div></div>`;
  }
  if (widget.kind === 'bar') {
    return `<div class="bar-track"><div class="bar-fill" style="width:${percent}%; background:${widget.style.accent_color}"></div></div>`;
  }
  return `<div class="widget-subtitle">Range ${widget.min_value} – ${widget.max_value} ${widget.unit || ''}</div>`;
}

function startDrag(event, widget) {
  state.drag = {
    id: widget.id,
    offsetX: event.clientX - widget.layout.x,
    offsetY: event.clientY - widget.layout.y,
  };
  window.addEventListener('pointermove', onDrag);
  window.addEventListener('pointerup', stopDrag, { once: true });
}

function onDrag(event) {
  if (!state.drag) return;
  const widget = state.config.widgets.find((item) => item.id === state.drag.id);
  if (!widget) return;
  widget.layout.x = Math.max(0, Math.min(state.config.width - widget.layout.width, event.clientX - state.drag.offsetX));
  widget.layout.y = Math.max(0, Math.min(state.config.height - widget.layout.height, event.clientY - state.drag.offsetY));
  renderCanvas();
}

function stopDrag() {
  state.drag = null;
  window.removeEventListener('pointermove', onDrag);
  render();
}

function formatValue(widget, value) {
  if (value === undefined || value === null) return '--';
  if (typeof value === 'boolean') return value ? 'ON' : 'OFF';
  return `${value}${widget.unit ? ` ${widget.unit}` : ''}`;
}

function render() {
  renderForm();
  renderCanvas();
}

async function pollState() {
  const payload = await fetchJson('/api/state');
  state.values = payload.values;
  state.alerts = payload.alerts;
  state.config = payload.config;
  $('#bus-status').textContent = `Source: ${payload.source_status}`;
  render();
}

function normalizeColor(value) {
  if (!value) return '#ff4d4f';
  if (value.startsWith('#')) return value;
  return rgbaToHex(value);
}

function rgbaToHex(value) {
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!match) return value || '#94a3b8';
  return `#${match.slice(1, 4).map((part) => Number(part).toString(16).padStart(2, '0')).join('')}`;
}

function hexToRgba(hex, alpha) {
  const cleaned = hex.replace('#', '');
  const expanded = cleaned.length === 3 ? cleaned.split('').map((ch) => ch + ch).join('') : cleaned;
  const num = parseInt(expanded, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function init() {
  state.config = await fetchJson('/api/config');
  bindInputs();
  await pollState();
  setInterval(pollState, 400);
}

init();
