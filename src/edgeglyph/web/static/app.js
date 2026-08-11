"use strict";

const translations = {
  en: {
    "document.title": "EdgeGlyph Workbench",
    "language.target": "中文",
    "language.switch": "Switch to Chinese",
    "brand.workbench": "WORKBENCH",
    "aria.rendererMode": "Renderer mode",
    "aria.renderControls": "Render controls",
    "aria.preview": "Preview",
    "aria.previewFormat": "Preview format",
    "aria.renderResult": "Render result",
    "aria.parameterValue": "{label} value",
    "mode.block": "Block",
    "mode.bead": "Bead",
    "mode.glyph": "Glyph",
    "section.source": "Source",
    "section.parameters": "Parameters",
    "section.palette": "Palette",
    "section.metrics": "Metrics",
    "section.export": "Export",
    "source.noFile": "No file",
    "source.choose": "Choose image",
    "source.browse": "Browse",
    "source.drop": "Drop an image",
    "action.reset": "Reset",
    "action.render": "Render",
    "action.copy": "Copy",
    "render.auto": "Auto render",
    "view.render": "Render",
    "view.source": "Source",
    "view.text": "Text",
    "alt.rendered": "Rendered terminal artwork",
    "alt.rendered.bead": "Rendered fuse-bead preview",
    "alt.source": "Source image",
    "font.primary": "Primary font",
    "font.fallback": "Fallback font",
    "status.ready": "Ready",
    "status.unsupported": "Unsupported file",
    "status.rendering": "Rendering {mode}",
    "status.rendered": "Rendered in {seconds}s",
    "status.setupFailed": "Setup failed: {message}",
    "status.commandCopied": "Command copied",
    "status.clipboardUnavailable": "Clipboard unavailable",
    "metrics.mode": "Mode",
    "metrics.render_seconds": "Render",
    "metrics.cells": "Cells",
    "metrics.colors": "Colors",
    "metrics.characters": "Characters",
    "metrics.bead_count": "Beads",
    "metrics.empty_cells": "Empty cells",
    "metrics.occupancy_ratio": "Grid occupancy",
    "metrics.preview_bead_size": "Preview bead size",
    "metrics.effective_oversample": "Effective sampling",
    "palette.beadCount": "{count} beads",
    "metrics.silhouette_coverage": "Silhouette coverage",
    "metrics.carved_detail_ratio": "Carved detail",
    "metrics.foreground_ratio": "Foreground ratio",
    "metrics.recall": "Recall",
    "metrics.precision": "Precision",
    "metrics.f1": "F1 score",
    "metrics.chamfer": "Chamfer distance",
    "metrics.tone_rmse": "Tone RMSE",
    "metrics.multiscale_error": "Multi-scale error",
    "metrics.profile": "Glyph profile",
    "metrics.color_mode": "Color mode",
    "metrics.fill_mode": "Resolved fill",
    "metrics.character_preset": "Character preset",
    "metrics.available_glyphs": "Available glyphs",
    "metrics.excluded_glyphs": "Excluded glyphs",
    "parameters.bead.cols.help": "Beads across the pattern, up to 2048.",
    "parameters.bead.rows.help": "Beads down the pattern, up to 2048.",
    "parameters.bead.colors.help": "Maximum bead palette size, up to 128 colors.",
    "choices.glyph.fill_mode.auto": "Follow profile (auto)",
  },
  zh: {
    "document.title": "EdgeGlyph 本地工作台",
    "language.target": "EN",
    "language.switch": "切换到英文",
    "brand.workbench": "工作台",
    "aria.rendererMode": "渲染模式",
    "aria.renderControls": "渲染控制",
    "aria.preview": "预览",
    "aria.previewFormat": "预览格式",
    "aria.renderResult": "渲染结果",
    "aria.parameterValue": "{label}数值",
    "mode.block": "色块",
    "mode.bead": "拼豆",
    "mode.glyph": "字符",
    "section.source": "源图",
    "section.parameters": "参数",
    "section.palette": "调色板",
    "section.metrics": "指标",
    "section.export": "导出",
    "source.noFile": "未选择文件",
    "source.choose": "选择图像",
    "source.browse": "浏览",
    "source.drop": "拖入一张图像",
    "action.reset": "重置",
    "action.render": "渲染",
    "action.copy": "复制",
    "render.auto": "自动渲染",
    "view.render": "渲染图",
    "view.source": "源图",
    "view.text": "文本",
    "alt.rendered": "终端艺术渲染结果",
    "alt.rendered.bead": "拼豆预览渲染结果",
    "alt.source": "源图像",
    "font.primary": "主字体",
    "font.fallback": "后备字体",
    "status.ready": "就绪",
    "status.unsupported": "不支持的文件格式",
    "status.rendering": "正在渲染{mode}模式",
    "status.rendered": "渲染完成，用时 {seconds} 秒",
    "status.setupFailed": "初始化失败：{message}",
    "status.commandCopied": "命令已复制",
    "status.clipboardUnavailable": "剪贴板不可用",
    "metrics.mode": "模式",
    "metrics.render_seconds": "渲染耗时",
    "metrics.cells": "单元格",
    "metrics.colors": "颜色数",
    "metrics.characters": "字符数",
    "metrics.bead_count": "拼豆数量",
    "metrics.empty_cells": "空白格数",
    "metrics.occupancy_ratio": "网格占用率",
    "metrics.preview_bead_size": "实际预览豆尺寸",
    "metrics.effective_oversample": "实际采样倍率",
    "palette.beadCount": "{count} 颗",
    "metrics.silhouette_coverage": "轮廓覆盖率",
    "metrics.carved_detail_ratio": "细节镂空率",
    "metrics.foreground_ratio": "前景占比",
    "metrics.recall": "召回率",
    "metrics.precision": "精确率",
    "metrics.f1": "F1 分数",
    "metrics.chamfer": "Chamfer 距离",
    "metrics.tone_rmse": "色调 RMSE",
    "metrics.multiscale_error": "多尺度误差",
    "metrics.profile": "字符配置",
    "metrics.color_mode": "颜色模式",
    "metrics.fill_mode": "实际填充",
    "metrics.character_preset": "字符预设",
    "metrics.available_glyphs": "可用字符",
    "metrics.excluded_glyphs": "排除字符",
    "parameters.cols.label": "列数",
    "parameters.cols.help": "终端单元格列数。",
    "parameters.rows.label": "行数",
    "parameters.rows.help": "终端单元格行数。",
    "parameters.colors.label": "调色板大小",
    "parameters.colors.help": "自适应调色板的最大颜色数。",
    "parameters.foreground.label": "单色前景",
    "parameters.foreground.help": "调色板大小为一时使用的固定前景色。",
    "parameters.subject_threshold.label": "主体阈值",
    "parameters.subject_threshold.help": "保留为主体区域所需的最小聚合覆盖率。",
    "parameters.ink_threshold.label": "线稿阈值",
    "parameters.ink_threshold.help": "镂空内部细节所需的最小强度。",
    "parameters.detail.label": "细节增益",
    "parameters.detail.help": "局部对比度对镂空细节的贡献。",
    "parameters.oversample.label": "过采样",
    "parameters.oversample.help": "每个终端像素轴向使用的采样数。",
    "parameters.fit.label": "画面适配",
    "parameters.fit.help": "裁剪铺满画面或完整容纳源图。",
    "parameters.focus_y.label": "垂直焦点",
    "parameters.focus_y.help": "从顶部到底部的垂直裁剪锚点。",
    "parameters.zoom.label": "主体缩放",
    "parameters.zoom.help": "主体在终端画面中的缩放比例。",
    "parameters.top_k.label": "候选字符数",
    "parameters.top_k.help": "网格优化前每个单元格保留的候选字符数。",
    "parameters.color_mode.label": "颜色模式",
    "parameters.color_mode.help": "使用源图自适应颜色，或使用单一终端前景色。",
    "parameters.monochrome_color.label": "单色前景",
    "parameters.monochrome_color.help": "单色 PNG 与 Lua 输出使用的前景色。",
    "parameters.profile.label": "渲染配置",
    "parameters.profile.help": "选择轮廓优先、多特征融合或稠密色调字符画。",
    "parameters.character_preset.label": "字符预设",
    "parameters.character_preset.help": "用于字形匹配的终端安全字符集合。",
    "parameters.symbols.label": "结构字符",
    "parameters.symbols.help": "直接输入自定义结构字符；留空时使用当前预设。",
    "parameters.fill_symbols.label": "填充字符",
    "parameters.fill_symbols.help": "直接输入自定义色调与纹理字符；留空时使用当前预设。",
    "parameters.minimum_luminance.label": "最低亮度",
    "parameters.minimum_luminance.help": "渐变调色板允许的最低亮度。",
    "parameters.fill_mode.label": "填充策略",
    "parameters.fill_mode.help": "跟随渲染配置，或显式选择结构、显著区域和完整色调填充。",
    "parameters.continuity.label": "线条连续性",
    "parameters.continuity.help": "相邻单元格笔画连续性的权重。",
    "parameters.diversity.label": "字符多样性",
    "parameters.diversity.help": "重复使用相似字符时施加的惩罚。",
    "parameters.shape_weight.label": "结构权重",
    "parameters.shape_weight.help": "边缘、骨架和笔画方向对匹配结果的影响。",
    "parameters.tone_weight.label": "色调权重",
    "parameters.tone_weight.help": "字符密度与区域明暗分布对匹配结果的影响。",
    "parameters.color_weight.label": "颜色权重",
    "parameters.color_weight.help": "前景色与背景色联合拟合对匹配结果的影响。",
    "parameters.texture_weight.label": "纹理权重",
    "parameters.texture_weight.help": "局部对比度和梯度分布对匹配结果的影响。",
    "parameters.global_weight.label": "全局权重",
    "parameters.global_weight.help": "多尺度轮廓和密度一致性对网格优化的影响。",
    "parameters.line_renderer.label": "线条渲染器",
    "parameters.line_renderer.help": "使用终端精灵或后备字体绘制线框字符。",
    "parameters.bead.cols.label": "横向拼豆数",
    "parameters.bead.cols.help": "图案横向包含的拼豆数量，最高 2048。",
    "parameters.bead.rows.label": "纵向拼豆数",
    "parameters.bead.rows.help": "图案纵向包含的拼豆数量，最高 2048。",
    "parameters.bead.colors.help": "拼豆图案允许使用的最大颜色数，最高 128 色。",
    "parameters.bead.subject_threshold.help": "单元格放置拼豆所需的最小主体覆盖率。",
    "parameters.bead.oversample.label": "采样质量",
    "parameters.bead.oversample.help": "每个拼豆单元轴向使用的源图采样数。",
    "parameters.bead.fit.help": "裁剪铺满拼豆画面或完整容纳源图。",
    "parameters.bead.focus_y.help": "拼豆画面从顶部到底部的垂直裁剪锚点。",
    "parameters.bead.zoom.help": "主体在拼豆画面中的缩放比例。",
    "parameters.background.label": "背景处理",
    "parameters.background.help": "自动移除连通的白色或透明背景，或保留完整画面。",
    "parameters.board_style.label": "底板样式",
    "parameters.board_style.help": "选择浅色、深色或透明的预览底板。",
    "parameters.finish.label": "拼豆质感",
    "parameters.finish.help": "使用带物理高光的亮面质感或克制的哑光质感。",
    "parameters.bead_size.label": "预览拼豆尺寸",
    "parameters.bead_size.help": "PNG 预览中每颗拼豆的目标像素尺寸；超大网格会自动缩小显示尺寸。",
    "choices.cover": "裁剪铺满（cover）",
    "choices.contain": "完整容纳（contain）",
    "choices.none": "无填充（none）",
    "choices.salient": "显著区域（salient）",
    "choices.tone": "完整色调（tone）",
    "choices.glyph.fill_mode.auto": "跟随配置（auto）",
    "choices.outline": "轮廓优先（outline）",
    "choices.hybrid": "多特征融合（hybrid）",
    "choices.portrait": "人物插画（portrait）",
    "choices.ascii": "纯 ASCII（ascii）",
    "choices.line": "线条字符（line）",
    "choices.unicode": "Unicode 扩展（unicode）",
    "choices.color": "彩色（color）",
    "choices.mono": "黑白（mono）",
    "choices.sprite": "终端精灵（sprite）",
    "choices.font": "字体绘制（font）",
    "choices.auto": "自动移除（auto）",
    "choices.keep": "保留背景（keep）",
    "choices.light": "浅色底板（light）",
    "choices.dark": "深色底板（dark）",
    "choices.transparent": "透明背景（transparent）",
    "choices.glossy": "亮面（glossy）",
    "choices.matte": "哑光（matte）",
  },
};

function initialLocale() {
  try {
    const stored = localStorage.getItem("edgeglyph-locale-v1");
    if (stored === "en" || stored === "zh") return stored;
  } catch (_) {
    // Local storage may be disabled; browser language remains a useful default.
  }
  return navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

const state = {
  locale: initialLocale(),
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
  status: { key: "status.ready", variables: {}, raw: false },
};

const elements = {
  status: document.querySelector(".status"),
  statusText: document.querySelector("#status-text"),
  languageToggle: document.querySelector("#language-toggle"),
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

function t(key, variables = {}, fallback = key) {
  const value = translations[state.locale][key] ?? translations.en[key] ?? fallback;
  return Object.entries(variables).reduce(
    (text, [name, replacement]) => text.replaceAll(`{${name}}`, replacement),
    value,
  );
}

function updateStatusText() {
  const variables = state.status.key === "status.rendering"
    ? { mode: t(`mode.${state.mode}`) }
    : state.status.variables;
  elements.statusText.textContent = state.status.raw
    ? state.status.message
    : t(state.status.key, variables);
}

function setStatus(key, status = "idle", variables = {}) {
  elements.status.dataset.state = status;
  state.status = { key, variables, raw: false };
  updateStatusText();
}

function setErrorStatus(message) {
  elements.status.dataset.state = "error";
  state.status = { message, raw: true };
  updateStatusText();
}

function applyTranslations() {
  document.documentElement.lang = state.locale === "zh" ? "zh-CN" : "en";
  document.title = t("document.title");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    if (state.source && (element === elements.sourceName || element === elements.sourceSize)) return;
    element.textContent = t(element.dataset.i18n, {}, element.textContent);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-i18n-alt]").forEach((element) => {
    element.alt = t(element.dataset.i18nAlt);
  });
  elements.languageToggle.textContent = t("language.target");
  elements.languageToggle.setAttribute("aria-label", t("language.switch"));
  elements.languageToggle.title = t("language.switch");
  updateStatusText();
}

function setLocale(locale) {
  state.locale = locale;
  try {
    localStorage.setItem("edgeglyph-locale-v1", locale);
  } catch (_) {
    // The language still applies for the current session.
  }
  applyTranslations();
  if (state.schema) buildParameters();
  if (state.result) renderMetrics(state.result.metrics);
  else renderEmptyMetrics();
}

function parameterText(parameter, field) {
  const generic = t(`parameters.${parameter.key}.${field}`, {}, parameter[field]);
  return t(`parameters.${state.mode}.${parameter.key}.${field}`, {}, generic);
}

function choiceText(parameter, choice) {
  return t(
    `choices.${state.mode}.${parameter.key}.${choice}`,
    {},
    t(`choices.${choice}`, {}, choice),
  );
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
  const controlId = `parameter-${state.mode}-${parameter.key}`;

  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameterText(parameter, "label");
  label.title = parameterText(parameter, "help");
  label.htmlFor = `${controlId}-range`;

  const row = document.createElement("div");
  row.className = "range-row";
  const range = document.createElement("input");
  range.type = "range";
  range.id = `${controlId}-range`;
  range.name = parameter.key;
  range.min = parameter.minimum;
  range.max = parameter.maximum;
  range.step = parameter.step;
  range.value = state.options[parameter.key];
  range.setAttribute("aria-label", parameterText(parameter, "label"));

  const number = document.createElement("input");
  number.type = "number";
  number.className = "parameter-value";
  number.id = `${controlId}-value`;
  number.name = `${parameter.key}_value`;
  number.min = parameter.minimum;
  number.max = parameter.maximum;
  number.step = parameter.step;
  number.value = state.options[parameter.key];
  number.setAttribute(
    "aria-label",
    t("aria.parameterValue", { label: parameterText(parameter, "label") }),
  );

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
  const controlId = `parameter-${state.mode}-${parameter.key}`;
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameterText(parameter, "label");
  label.title = parameterText(parameter, "help");
  label.htmlFor = controlId;
  const select = document.createElement("select");
  select.id = controlId;
  select.name = parameter.key;
  select.setAttribute("aria-label", parameterText(parameter, "label"));
  parameter.choices.forEach((choice) => {
    const option = document.createElement("option");
    option.value = choice;
    option.textContent = choiceText(parameter, choice);
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
  const controlId = `parameter-${state.mode}-${parameter.key}`;
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameterText(parameter, "label");
  label.title = parameterText(parameter, "help");
  label.htmlFor = `${controlId}-picker`;
  const row = document.createElement("div");
  row.className = "color-row";
  const picker = document.createElement("input");
  picker.type = "color";
  picker.id = `${controlId}-picker`;
  picker.name = parameter.key;
  picker.value = state.options[parameter.key];
  const text = document.createElement("input");
  text.type = "text";
  text.id = `${controlId}-text`;
  text.name = `${parameter.key}_text`;
  text.setAttribute("aria-label", `${parameterText(parameter, "label")} HEX`);
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

function createTextControl(parameter) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-control";
  wrapper.dataset.parameter = parameter.key;
  const controlId = `parameter-${state.mode}-${parameter.key}`;
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = parameterText(parameter, "label");
  label.title = parameterText(parameter, "help");
  label.htmlFor = controlId;
  const input = document.createElement("input");
  input.type = "text";
  input.id = controlId;
  input.name = parameter.key;
  input.value = state.options[parameter.key];
  input.placeholder = parameterText(parameter, "help");
  input.spellcheck = false;
  input.addEventListener("change", () => setOption(parameter.key, input.value));
  wrapper.append(label, input);
  return wrapper;
}

function buildParameters() {
  elements.parameters.replaceChildren();
  currentSchema().forEach((parameter) => {
    let control;
    if (parameter.kind === "choice") control = createChoiceControl(parameter);
    else if (parameter.kind === "color") control = createColorControl(parameter);
    else if (parameter.kind === "string") control = createTextControl(parameter);
    else control = createNumericControl(parameter);
    elements.parameters.append(control);
  });
  buildFontControls();
  updateConditionalControls();
}

function fontSelect(key, labelText, value, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-control";
  const label = document.createElement("label");
  label.className = "parameter-label";
  label.textContent = labelText;
  label.htmlFor = `font-${key}`;
  const select = document.createElement("select");
  select.id = `font-${key}`;
  select.name = key;
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
    fontSelect("primary", t("font.primary"), state.font, (value) => {
      state.font = value;
      state.revision += 1;
      updateCommand();
      scheduleRender();
    }),
    fontSelect("fallback", t("font.fallback"), state.fallbackFont, (value) => {
      state.fallbackFont = value;
      state.revision += 1;
      updateCommand();
      scheduleRender();
    }),
  );
}

function updateConditionalControls() {
  const setDisabled = (control, disabled) => {
    if (!control) return;
    control.classList.toggle("disabled", disabled);
    control.setAttribute("aria-disabled", String(disabled));
    control.querySelectorAll("input, select, button").forEach((element) => {
      element.disabled = disabled;
    });
  };
  const foreground = elements.parameters.querySelector('[data-parameter="foreground"]');
  setDisabled(foreground, state.options.colors !== 1);
  if (state.mode !== "glyph") return;
  const monochrome = state.options.color_mode === "mono";
  ["colors", "minimum_luminance", "color_weight"].forEach((key) => {
    const control = elements.parameters.querySelector(`[data-parameter="${key}"]`);
    setDisabled(control, monochrome);
  });
  const ink = elements.parameters.querySelector('[data-parameter="monochrome_color"]');
  setDisabled(ink, !monochrome);
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
    setStatus("status.unsupported", "error");
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
  setStatus("status.rendering", "working");

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
      setStatus("status.rendered", "idle", {
        seconds: payload.metrics.render_seconds.toFixed(3),
      });
    }
  } catch (error) {
    setErrorStatus(error.message);
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
  elements.renderPreview.alt = t(`alt.rendered.${state.mode}`, {}, t("alt.rendered"));
  elements.textPreview.textContent = state.result.text;
  elements.dimensions.textContent = `${state.result.metrics.cols} x ${state.result.metrics.rows}`;
  elements.palette.replaceChildren();
  state.result.palette.forEach((color, index) => {
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.backgroundColor = color;
    const label = document.createElement("strong");
    label.textContent = color.slice(1);
    swatch.append(label);
    const count = state.result.metrics.palette_counts?.[index];
    if (count !== undefined) {
      const amount = document.createElement("small");
      amount.textContent = count;
      swatch.append(amount);
      swatch.title = `${color} · ${t("palette.beadCount", { count })}`;
    } else {
      swatch.title = color;
    }
    elements.palette.append(swatch);
  });
  elements.paletteCount.textContent = state.result.palette.length;
  renderMetrics(state.result.metrics);
  document.querySelectorAll("[data-export]").forEach((button) => { button.disabled = false; });
  setView("render");
}

function formatMetric(key, value) {
  if (key === "mode") return t(`mode.${value}`, {}, String(value));
  if (key === "render_seconds") return `${value.toFixed(3)} s`;
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(3);
  return String(value);
}

function renderMetrics(metrics) {
  const preferred = ["mode", "render_seconds", "cols", "rows", "colors", "characters"];
  const entries = [];
  preferred.forEach((key) => {
    if (key === "cols") {
      entries.push([t("metrics.cells"), `${metrics.cols} x ${metrics.rows}`]);
    } else if (key !== "rows" && key in metrics) {
      entries.push([
        t(`metrics.${key}`, {}, key.replaceAll("_", " ")),
        formatMetric(key, metrics[key]),
      ]);
    }
  });
  Object.entries(metrics).forEach(([key, value]) => {
    if (!preferred.includes(key) && !["palette", "palette_counts"].includes(key)) {
      entries.push([
        t(`metrics.${key}`, {}, key.replaceAll("_", " ")),
        formatMetric(key, value),
      ]);
    }
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

function renderEmptyMetrics() {
  elements.metrics.replaceChildren();
  const keys = state.mode === "bead"
    ? ["mode", "render_seconds", "cells", "bead_count"]
    : ["mode", "render_seconds", "cells", "characters"];
  keys.forEach((key) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = t(`metrics.${key}`);
    description.textContent = "--";
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
  renderEmptyMetrics();
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
    setStatus("status.ready");
  } catch (error) {
    setStatus("status.setupFailed", "error", { message: error.message });
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
    setStatus("status.commandCopied");
  } catch (_) {
    setStatus("status.clipboardUnavailable", "error");
  }
});
elements.languageToggle.addEventListener("click", () => {
  setLocale(state.locale === "en" ? "zh" : "en");
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

applyTranslations();
renderEmptyMetrics();
init();
