"use strict";

const state = {
  schema: null,
  mode: "block",
  options: {},
  font: "",
  fallbackFont: "",
  source: "",
  sourceName: "input.png",
  result: null,
  view: "render",
  rendering: false,
  pending: false,
  timer: null,
  revision: 0,
};

const elements = {
  status: document.querySelector(".status"),
  statusText: document.querySelector("#status-text"),
  sourceInput: document.querySelector("#source-input"),
  sourceButton: document.querySelector("#source-button"),
  sourceName: document.querySelector("#source-name"),
  sourceSize: document.querySelector("#source-size"),
  sourcePreview: document.querySelector("#source-preview"),
  renderPreview: document.querySelector("#render-preview"),
  textPreview: document.querySelector("#text-preview"),
  emptyState: document.querySelector("#empty-state"),
  renderMask: document.querySelector("#render-mask"),
  dropTarget: document.querySelector("#drop-target"),
  parameters: document.querySelector("#parameter-controls"),
  fonts: document.querySelector("#font-controls"),
  autoRender: document.querySelector("#auto-render"),
  renderButton: document.querySelector("#render-button"),
  resetButton: document.querySelector("#reset-button"),
  dimensions: document.querySelector("#preview-dimensions"),
  palette: document.querySelector("#palette"),
  paletteCount: document.querySelector("#palette-count"),
  metrics: document.querySelector("#metrics"),
  command: document.querySelector("#command-preview"),
  copyCommand: document.querySelector("#copy-command"),
};

function setStatus(text, status = "idle") {
  elements.status.dataset.state = status;
  elements.statusText.textContent = text;
}

function currentSchema() {
  return state.schema.modes[state.mode];
}

function storedOptions() {
  try {
    return JSON.parse(localStorage.getItem("edgeglyph-options-v1") || "{}");
  } catch (_) {
    return {};
  }
}

function saveOptions() {
  const stored = storedOptions();
  stored[state.mode] = state.options;
  localStorage.setItem("edgeglyph-options-v1", JSON.stringify(stored));
}

function resetOptions() {
  state.options = Object.fromEntries(currentSchema().map((item) => [item.key, item.default]));
  state.revision += 1;
  saveOptions();
  buildParameters();
  updateCommand();
  scheduleRender();
}

function loadModeOptions() {
  const saved = storedOptions()[state.mode] || {};
  state.options = Object.fromEntries(
    currentSchema().map((item) => [item.key, saved[item.key] ?? item.default]),
  );
}

function setOption(key, value) {
  state.options[key] = value;
  state.revision += 1;
  saveOptions();
  updateConditionalControls();
  updateCommand();
  scheduleRender();
}

function createNumericControl(parameter) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-control";
  wrapper.dataset.parameter = parameter.key;

  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameter.label;
  label.title = parameter.help;

  const row = document.createElement("div");
  row.className = "range-row";
  const range = document.createElement("input");
  range.type = "range";
  range.min = parameter.minimum;
  range.max = parameter.maximum;
  range.step = parameter.step;
  range.value = state.options[parameter.key];
  range.setAttribute("aria-label", parameter.label);

  const number = document.createElement("input");
  number.type = "number";
  number.className = "parameter-value";
  number.min = parameter.minimum;
  number.max = parameter.maximum;
  number.step = parameter.step;
  number.value = state.options[parameter.key];
  number.setAttribute("aria-label", `${parameter.label} value`);

  const update = (raw) => {
    const value = parameter.kind === "integer" ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
    if (!Number.isFinite(value)) return;
    const bounded = Math.min(parameter.maximum, Math.max(parameter.minimum, value));
    range.value = bounded;
    number.value = bounded;
    setOption(parameter.key, bounded);
  };
  range.addEventListener("input", () => update(range.value));
  number.addEventListener("change", () => update(number.value));

  row.append(range, number);
  wrapper.append(label, row);
  return wrapper;
}

function createChoiceControl(parameter) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-control";
  wrapper.dataset.parameter = parameter.key;
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameter.label;
  label.title = parameter.help;
  const select = document.createElement("select");
  select.setAttribute("aria-label", parameter.label);
  parameter.choices.forEach((choice) => {
    const option = document.createElement("option");
    option.value = choice;
    option.textContent = choice;
    option.selected = choice === state.options[parameter.key];
    select.append(option);
  });
  select.addEventListener("change", () => setOption(parameter.key, select.value));
  wrapper.append(label, select);
  return wrapper;
}

function createColorControl(parameter) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-control";
  wrapper.dataset.parameter = parameter.key;
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameter.label;
  label.title = parameter.help;
  const row = document.createElement("div");
  row.className = "color-row";
  const picker = document.createElement("input");
  picker.type = "color";
  picker.value = state.options[parameter.key];
  const text = document.createElement("input");
  text.type = "text";
  text.value = state.options[parameter.key];
  const update = (value) => {
    if (!/^#[0-9a-f]{6}$/i.test(value)) return;
    picker.value = value;
    text.value = value;
    setOption(parameter.key, value);
  };
  picker.addEventListener("input", () => update(picker.value));
  text.addEventListener("change", () => update(text.value));
  row.append(picker, text);
  wrapper.append(label, row);
  return wrapper;
}

function buildParameters() {
  elements.parameters.replaceChildren();
  currentSchema().forEach((parameter) => {
    let control;
    if (parameter.kind === "choice") control = createChoiceControl(parameter);
    else if (parameter.kind === "color") control = createColorControl(parameter);
    else control = createNumericControl(parameter);
    elements.parameters.append(control);
  });
  buildFontControls();
  updateConditionalControls();
}

function fontSelect(labelText, value, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-control";
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = labelText;
  const select = document.createElement("select");
  state.schema.fonts.forEach((font) => {
    const option = document.createElement("option");
    option.value = font.path;
    option.textContent = font.label;
    option.selected = font.path === value;
    select.append(option);
  });
  select.addEventListener("change", () => onChange(select.value));
  wrapper.append(label, select);
  return wrapper;
}

function buildFontControls() {
  elements.fonts.replaceChildren();
  if (state.mode !== "glyph") return;
  elements.fonts.append(
    fontSelect("Primary font", state.font, (value) => {
      state.font = value;
      state.revision += 1;
      updateCommand();
      scheduleRender();
    }),
    fontSelect("Fallback font", state.fallbackFont, (value) => {
      state.fallbackFont = value;
      state.revision += 1;
      updateCommand();
      scheduleRender();
    }),
  );
}

function updateConditionalControls() {
  const foreground = elements.parameters.querySelector('[data-parameter="foreground"]');
  if (foreground) foreground.classList.toggle("disabled", state.options.colors !== 1);
}

function setMode(mode) {
  if (state.mode === mode) return;
  state.mode = mode;
  state.revision += 1;
  document.querySelectorAll(".mode-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  loadModeOptions();
  buildParameters();
  state.result = null;
  clearResult();
  updateCommand();
  scheduleRender();
}

function quoteShell(value) {
  if (/^[a-zA-Z0-9_./#-]+$/.test(value)) return value;
  return `'${value.replaceAll("'", `'\\''`)}'`;
}

function updateCommand() {
  if (!state.schema) return;
  const parts = ["edgeglyph", state.mode, quoteShell(state.sourceName || "input.png")];
  if (state.mode === "glyph") {
    parts.push("--font", quoteShell(state.font || "/path/to/font.ttf"));
    if (state.fallbackFont) parts.push("--fallback-font", quoteShell(state.fallbackFont));
  }
  currentSchema().forEach((parameter) => {
    parts.push(parameter.flag, quoteShell(String(state.options[parameter.key])));
  });
  parts.push("--preview", "output.png", "--lua-output", "output.lua");
  elements.command.textContent = parts.join(" ");
}

function readSource(file) {
  if (!file || !file.type.startsWith("image/")) {
    setStatus("Unsupported file", "error");
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    state.source = reader.result;
    state.sourceName = file.name;
    state.revision += 1;
    elements.sourceName.textContent = file.name;
    elements.sourceSize.textContent = file.size >= 1024 * 1024
      ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
      : `${(file.size / 1024).toFixed(1)} KB`;
    elements.sourcePreview.src = state.source;
    elements.emptyState.hidden = true;
    setView("source");
    updateCommand();
    scheduleRender(true);
  });
  reader.readAsDataURL(file);
}

function scheduleRender(immediate = false) {
  clearTimeout(state.timer);
  if (!state.source || !elements.autoRender.checked) return;
  state.timer = setTimeout(render, immediate ? 40 : 480);
}

async function render() {
  if (!state.source) {
    elements.sourceInput.click();
    return;
  }
  if (state.rendering) {
    state.pending = true;
    return;
  }
  state.rendering = true;
  state.pending = false;
  const revision = state.revision;
  const mode = state.mode;
  elements.renderButton.disabled = true;
  elements.renderMask.hidden = false;
  setStatus(`Rendering ${state.mode}`, "working");

  try {
    const response = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,
        source: state.source,
        options: state.options,
        font: state.font,
        fallback_font: state.fallbackFont,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    if (revision === state.revision) {
      state.result = payload;
      showResult();
      setStatus(`Rendered in ${payload.metrics.render_seconds.toFixed(3)}s`);
    }
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    state.rendering = false;
    elements.renderButton.disabled = false;
    elements.renderMask.hidden = true;
    if (state.pending) {
      state.pending = false;
      render();
    }
  }
}

function showResult() {
  elements.renderPreview.src = state.result.preview;
  elements.textPreview.textContent = state.result.text;
  elements.dimensions.textContent = `${state.result.metrics.cols} x ${state.result.metrics.rows}`;
  elements.palette.replaceChildren();
  state.result.palette.forEach((color) => {
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.backgroundColor = color;
    swatch.textContent = color.slice(1);
    swatch.title = color;
    elements.palette.append(swatch);
  });
  elements.paletteCount.textContent = state.result.palette.length;
  renderMetrics(state.result.metrics);
  document.querySelectorAll("[data-export]").forEach((button) => { button.disabled = false; });
  setView("render");
}

function formatMetric(key, value) {
  if (key === "render_seconds") return `${value.toFixed(3)} s`;
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(3);
  return String(value);
}

function renderMetrics(metrics) {
  const preferred = ["mode", "render_seconds", "cols", "rows", "colors", "characters"];
  const entries = [];
  preferred.forEach((key) => {
    if (key === "cols") {
      entries.push(["Cells", `${metrics.cols} x ${metrics.rows}`]);
    } else if (key !== "rows" && key in metrics) {
      entries.push([key.replaceAll("_", " "), formatMetric(key, metrics[key])]);
    }
  });
  Object.entries(metrics).forEach(([key, value]) => {
    if (!preferred.includes(key)) entries.push([key.replaceAll("_", " "), formatMetric(key, value)]);
  });
  elements.metrics.replaceChildren();
  entries.forEach(([key, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = key;
    description.textContent = value;
    row.append(term, description);
    elements.metrics.append(row);
  });
}

function clearResult() {
  elements.renderPreview.removeAttribute("src");
  elements.textPreview.textContent = "";
  elements.palette.replaceChildren();
  elements.paletteCount.textContent = "0";
  elements.dimensions.textContent = "-- x --";
  document.querySelectorAll("[data-export]").forEach((button) => { button.disabled = true; });
  if (!state.source) elements.emptyState.hidden = false;
  setView(state.source ? "source" : "render");
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".view-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  const hasResult = Boolean(state.result);
  elements.emptyState.hidden = Boolean(state.source);
  elements.renderPreview.hidden = view !== "render" || !hasResult;
  elements.sourcePreview.hidden = view !== "source" || !state.source;
  elements.textPreview.hidden = view !== "text" || !hasResult;
}

function downloadBlob(content, type, extension) {
  const stem = state.sourceName.replace(/\.[^.]+$/, "") || "edgeglyph";
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = `${stem}-${state.mode}.${extension}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 500);
}

function exportResult(type) {
  if (!state.result) return;
  if (type === "png") {
    const link = document.createElement("a");
    link.href = state.result.preview;
    link.download = `${state.sourceName.replace(/\.[^.]+$/, "")}-${state.mode}.png`;
    link.click();
  } else if (type === "txt") downloadBlob(state.result.text, "text/plain;charset=utf-8", "txt");
  else if (type === "lua") downloadBlob(state.result.lua, "text/plain;charset=utf-8", "lua");
  else downloadBlob(JSON.stringify(state.result.metrics, null, 2) + "\n", "application/json", "json");
}

async function init() {
  try {
    const response = await fetch("/api/schema");
    state.schema = await response.json();
    state.font = state.schema.defaults.font;
    state.fallbackFont = state.schema.defaults.fallback_font;
    loadModeOptions();
    buildParameters();
    updateCommand();
    setStatus("Ready");
  } catch (error) {
    setStatus(`Setup failed: ${error.message}`, "error");
  }
}

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});
document.querySelectorAll(".view-tab").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});
document.querySelectorAll("[data-export]").forEach((button) => {
  button.addEventListener("click", () => exportResult(button.dataset.export));
});
elements.sourceButton.addEventListener("click", () => elements.sourceInput.click());
elements.emptyState.addEventListener("click", () => elements.sourceInput.click());
elements.sourceInput.addEventListener("change", () => readSource(elements.sourceInput.files[0]));
elements.renderButton.addEventListener("click", render);
elements.resetButton.addEventListener("click", resetOptions);
elements.autoRender.addEventListener("change", () => scheduleRender(true));
elements.copyCommand.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(elements.command.textContent);
    setStatus("Command copied");
  } catch (_) {
    setStatus("Clipboard unavailable", "error");
  }
});
["dragenter", "dragover"].forEach((event) => {
  elements.dropTarget.addEventListener(event, (current) => {
    current.preventDefault();
    elements.dropTarget.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((event) => {
  elements.dropTarget.addEventListener(event, (current) => {
    current.preventDefault();
    elements.dropTarget.classList.remove("dragging");
  });
});
elements.dropTarget.addEventListener("drop", (event) => readSource(event.dataTransfer.files[0]));

init();
