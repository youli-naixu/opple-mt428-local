"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const dom = Object.fromEntries([
    "connectionBadge", "connectionText", "refreshButton", "lampStage", "previewMode",
    "actualStateLabel", "lampStateValue", "stateCaption", "actualBrightness", "actualColorTemp",
    "actualPower", "lastUpdated", "powerButton", "powerText", "powerHint", "brightnessRange",
    "brightnessOutput", "colorTempRange", "colorTempOutput", "draftIndicator", "draftStatus",
    "applyButton", "applyButtonText", "feedback", "feedbackIcon", "liveStatus", "sceneList",
    "timerForm", "customTimerRow", "customMinutes", "timerLabel", "timerCountdown", "timerEndTime",
    "setTimerButton", "cancelTimerButton", "restoreButton", "initialStateSummary", "capabilityList",
    "capabilityCount", "deviceDetails", "activityList", "multicastDiagram", "multicastDemoButton",
    "multicastFeedback", "modeBanner", "modeBannerTitle", "modeBannerNote", "capabilityModeNote",
    "sideLightPanel", "sideLightChannels", "sideLightMode", "sideLightOnButton", "sideLightOffButton",
    "sideLightBrightnessRange", "sideLightBrightnessOutput", "sideLightApplyButton", "sideLightFeedback"
  ].map((id) => [id, $(id)]));

  let snapshot = null;
  let requestPending = false;
  let operationPending = false;
  let connection = "loading";
  let pollHandle = null;
  let timerReceivedAt = 0;
  let pollDue = 0;
  let draftDirty = false;
  let draftEditing = false;
  let hasDraftBaseline = false;
  let draft = { brightness: 60, colorTemp: 4000 };
  let currentScenes = [];
  let currentCapabilities = [];
  let statusHasFailed = false;
  let sideDraftDirty = false;
  let sideBrightnessDraft = 10;
  const POLL_INTERVAL = 5000;
  const REQUEST_TIMEOUT = 16000;
  const MODEL = "MT428-D0.5×36+0.2×21-WTT";

  const clamp = (number, min, max) => Math.min(max, Math.max(min, number));
  const validNumber = (value) => typeof value === "number" && Number.isFinite(value);
  const stateExists = (state) => state && typeof state === "object" && typeof state.power === "boolean";
  const dateValue = (value) => {
    if (typeof value !== "string" || !value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  };
  const formatTime = (value, seconds = true) => {
    const date = dateValue(value);
    return date ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", ...(seconds ? { second: "2-digit" } : {}) }) : "未知";
  };
  const formatDateTime = (value) => {
    const date = dateValue(value);
    return date ? date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "尚无读数";
  };
  const displayValue = (value) => value === null || value === undefined || value === "" ? "未提供" : String(value);
  const percentOf = (state) => validNumber(state?.brightness_pct) ? clamp(Math.round(state.brightness_pct), 0, 100) : validNumber(state?.brightness) ? clamp(Math.round(state.brightness * 100 / 255), 0, 100) : null;
  const tempOf = (state) => validNumber(state?.color_temp) ? Math.round(state.color_temp) : null;
  const currentState = () => stateExists(snapshot?.state) ? snapshot.state : null;
  const isOnline = () => connection === "online";
  const isSimulated = () => snapshot?.simulated === true;
  const isReadOnly = () => snapshot?.read_only === true;
  const hasControls = () => isOnline() && currentState() !== null && !requestPending && !snapshot?.read_only;
  const isDraftFocused = () => [dom.brightnessRange, dom.colorTempRange].includes(document.activeElement);
  const sideChannels = () => currentState()?.experimental_channels;
  const hasSideField = (field) => {
    const channels = sideChannels();
    return channels !== null && typeof channels === "object" && Object.prototype.hasOwnProperty.call(channels, field) && Number.isInteger(channels[field]);
  };
  const hasSideControls = (field) => snapshot?.experimental_side_light === true && hasControls() && hasSideField(field);
  const isSideCapability = (capability) => /side.light|arm.light|侧灯|副灯/.test(`${capability.id || ""} ${capability.title || ""}`.toLowerCase());
  const modeText = (text) => isSimulated() ? String(text).replace(/已由设备读回确认|设备状态读回确认|设备读回确认|设备验证确认|(?:实机|真机)(?:已验证|验证通过|验证成功)/g, "模拟回读").replace(/设备实际状态|实际状态/g, "模拟状态") : String(text);

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = modeText(text);
    return node;
  }

  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("icon");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#icon-${name}`);
    svg.append(use);
    return svg;
  }

  function setFeedback(type, message) {
    dom.feedback.className = `feedback is-${type}`;
    dom.feedbackIcon.setAttribute("href", type === "success" ? "#icon-check" : "#icon-info");
    dom.liveStatus.textContent = `${isSimulated() ? "模拟模式 · " : ""}${modeText(message)}`;
  }

  function setSideFeedback(type, message) {
    dom.sideLightFeedback.className = `side-light-feedback is-${type}`;
    dom.sideLightFeedback.textContent = `${isSimulated() ? "模拟 / Simulation · " : ""}${modeText(message)}`;
    setFeedback(type, message);
  }

  function renderMode() {
    const simulated = isSimulated();
    const readOnly = isReadOnly();
    const mode = simulated ? "simulated" : readOnly ? "read-only" : snapshot?.read_only === false && snapshot?.simulated === false ? "live" : "loading";
    const titles = {
      simulated: "模拟模式 · 不连接真实台灯 / Simulation · no hardware",
      "read-only": "只读模式 · 不会改变灯光 / Read-only · no light changes",
      live: "实物控制模式 / Live control",
      loading: "正在确认运行模式 / Checking mode"
    };
    dom.modeBanner.className = `mode-banner is-${mode}`;
    dom.modeBannerTitle.textContent = titles[mode];
    const notes = {
      simulated: readOnly ? "只读模式 · 不会改变灯光 / Read-only · no light changes. 模拟写入也已禁用。" : "回读与操作记录均为模拟数据；点击控制只更新模拟状态 / Readbacks and controls use simulated data only.",
      "read-only": "仅查询状态；可取消已保存的本地定时 / Status queries only; saved local timers may be cancelled.",
      live: "点击控制会向台灯写入；实验侧灯仍待目视验证 / Controls write to hardware; experimental side light still needs visual verification.",
      loading: "确认前仅查询状态 / Status queries only until the mode is known."
    };
    dom.modeBannerNote.textContent = notes[mode];
    dom.capabilityModeNote.textContent = simulated ? "模拟回读 · 不代表实物验证" : readOnly ? "只读查询" : mode === "live" ? "以设备读回为准" : "等待模式查询";
  }

  function setConnection(value) {
    connection = value;
    const labels = isSimulated() ? { loading: "连接中", online: "模拟服务在线", offline: "模拟服务离线", unknown: "模拟连接待确认" } : { loading: "连接中", online: "设备在线", offline: "设备离线", unknown: "连接待确认" };
    dom.connectionBadge.className = `connection-badge is-${value}${isSimulated() ? " is-simulated" : ""}`;
    dom.connectionText.textContent = labels[value] || labels.unknown;
  }

  function syncDraftFromState(state) {
    if (!state || draftDirty || draftEditing || isDraftFocused()) return;
    const brightness = percentOf(state);
    const temp = tempOf(state);
    if (brightness !== null) draft.brightness = clamp(brightness, 1, 100);
    if (temp !== null) draft.colorTemp = clamp(temp, 2700, 6500);
    hasDraftBaseline = brightness !== null && temp !== null;
  }

  function temperatureColor(kelvin) {
    const amount = clamp((kelvin - 2700) / 3800, 0, 1);
    const warm = [255, 196, 119];
    const cool = [211, 233, 255];
    return `rgb(${warm.map((value, index) => Math.round(value + (cool[index] - value) * amount)).join(", ")})`;
  }

  function renderDraft() {
    dom.brightnessRange.value = String(draft.brightness);
    dom.colorTempRange.value = String(draft.colorTemp);
    dom.brightnessRange.setAttribute("aria-valuetext", `${draft.brightness}%`);
    dom.colorTempRange.setAttribute("aria-valuetext", `${draft.colorTemp} K`);
    dom.brightnessRange.style.setProperty("--range-progress", `${(draft.brightness - 1) / 99 * 100}%`);
    dom.brightnessOutput.replaceChildren(document.createTextNode(String(draft.brightness)), make("span", "", "%"));
    dom.colorTempOutput.replaceChildren(document.createTextNode(String(draft.colorTemp)), make("span", "", "K"));
    dom.draftIndicator.classList.toggle("is-dirty", draftDirty);
    dom.draftStatus.textContent = isReadOnly() ? "只读模式：滑块仅供本页预览，写入已禁用" : isSimulated() ? draftDirty ? "模拟预览已调整，点击应用仅更新模拟状态" : "拖动仅预览；点击应用只更新模拟状态，不连接真实台灯" : draftDirty ? "预览已调整，点击“开灯并应用”后生效" : "拖动只预览，点击应用后才控制台灯";
    dom.previewMode.classList.toggle("is-draft", draftDirty);
    dom.previewMode.textContent = draftDirty ? "草稿预览 · 尚未应用" : !isOnline() ? "光线示意 · 非实时" : currentState() ? isSimulated() ? "模拟回读 · 光线示意" : "设备读回 · 光线示意" : "光线示意 · 等待查询";
    const previewPower = draftDirty || currentState()?.power === true;
    dom.lampStage.classList.toggle("is-off", !previewPower);
    dom.lampStage.classList.toggle("is-uncertain", !isOnline() && !draftDirty);
    dom.lampStage.style.setProperty("--light-color", temperatureColor(draft.colorTemp));
    dom.lampStage.style.setProperty("--emitter-color", temperatureColor(draft.colorTemp));
    dom.lampStage.style.setProperty("--glow-strength", String(.15 + draft.brightness / 100 * .85));
  }

  function renderState() {
    const state = currentState();
    const online = isOnline();
    dom.actualStateLabel.textContent = isSimulated() ? online ? "模拟状态 · 非实物读数" : "模拟状态 · 当前非实时" : online ? "设备实际状态" : state ? "上次读回状态 · 当前非实时" : "设备状态";
    dom.lampStateValue.textContent = !online ? connection === "loading" ? "等待连接…" : connection === "offline" ? isSimulated() ? "模拟服务已离线" : "台灯已离线" : "连接待确认" : !state ? "等待读回状态" : isSimulated() ? state.power ? "模拟灯光 · 已开启" : "模拟灯光 · 已关闭" : state.power ? "光，已经就位。" : "让光休息一会儿。";
    dom.stateCaption.textContent = isSimulated() ? state ? "模拟回读 · 不代表实物状态" : "等待模拟状态" : !online ? state ? "以下为旧值，请勿视为实时" : "等待设备响应" : state ? "实际状态已读回" : "尚未获得实际状态";
    dom.actualBrightness.textContent = state && percentOf(state) !== null ? String(percentOf(state)) : "—";
    dom.actualColorTemp.textContent = state && tempOf(state) !== null ? String(tempOf(state)) : "—";
    dom.actualPower.textContent = state ? `${state.power ? "已开启" : "已关闭"}${online ? "" : " · 旧值"}` : "待查询";
    dom.lastUpdated.textContent = `最后更新：${formatDateTime(state?.observed_at)}${state && !online ? " · 非实时" : ""}`;
    dom.powerButton.setAttribute("aria-pressed", String(state?.power === true));
    dom.powerButton.setAttribute("aria-label", isReadOnly() ? "只读模式，灯光开关已禁用" : !online ? "灯光状态待确认，当前不可控制" : state ? `${isSimulated() ? "模拟" : ""}${state.power ? "关闭灯光" : "开启灯光"}` : "灯光状态待查询");
    dom.powerText.textContent = state ? state.power ? "已开启" : "已关闭" : "待查询";
    dom.powerHint.textContent = isReadOnly() ? "只读模式，不会改变灯光" : isSimulated() ? "只更新模拟状态，不连接真实台灯" : online && state ? "以设备读回为准；副灯已定位协议，实验待验证" : "待设备在线并读回状态后可控制";
    const initial = stateExists(snapshot?.initial_state) ? snapshot.initial_state : null;
    dom.initialStateSummary.textContent = initial ? `本次服务启动首次${isSimulated() ? "模拟回读" : "读回"}：${initial.power ? "开启" : "关闭"} · ${percentOf(initial) ?? "—"}% · ${tempOf(initial) ?? "—"} K。${isReadOnly() ? "只读模式，恢复已禁用。" : isSimulated() ? "恢复仅更新模拟状态。" : "恢复由本地服务执行。"}` : "本地服务会在首次查询时保存本次启动的初始状态。";
    syncDraftFromState(state);
    renderDraft();
    updateDisabled();
  }

  function renderSideLight() {
    dom.sideLightPanel.hidden = snapshot?.experimental_side_light !== true;
    if (dom.sideLightPanel.hidden) return;
    dom.sideLightMode.textContent = isReadOnly() ? `${isSimulated() ? "模拟 / Simulation · " : ""}只读模式 · 实验写入已禁用 / Read-only · experimental writes disabled.` : isSimulated() ? "模拟模式 · 实验按钮仅更新模拟候选字段，不连接真实台灯 / Simulation · candidate fields only, no hardware." : "实物实验 · 每次点击发送一次指令，候选匹配后仍需目视验证 / Live experiment · one command per click; candidate matches still need visual verification.";
    const fields = ["arm_power_raw", "arm_brightness_raw"].filter(hasSideField);
    dom.sideLightChannels.replaceChildren();
    for (const field of fields) {
      const row = make("div");
      row.append(make("dt", "", field), make("dd", "", sideChannels()[field]));
      dom.sideLightChannels.append(row);
    }
    if (!fields.length) {
      const row = make("div");
      row.append(make("dt", "", "候选字段"), make("dd", "", "未返回已知字段 / No known fields returned"));
      dom.sideLightChannels.append(row);
    }
    const brightness = sideChannels()?.arm_brightness_raw;
    if (hasSideField("arm_brightness_raw") && brightness >= 10 && brightness <= 255 && !sideDraftDirty && document.activeElement !== dom.sideLightBrightnessRange) {
      sideBrightnessDraft = brightness;
    }
    renderSideDraft();
  }

  function renderSideDraft() {
    dom.sideLightBrightnessRange.value = String(sideBrightnessDraft);
    dom.sideLightBrightnessRange.setAttribute("aria-valuetext", `原始值 ${sideBrightnessDraft}`);
    dom.sideLightBrightnessRange.style.setProperty("--range-progress", `${(sideBrightnessDraft - 10) / 245 * 100}%`);
    dom.sideLightBrightnessOutput.textContent = String(sideBrightnessDraft);
  }

  function renderScenes(scenes) {
    currentScenes = Array.isArray(scenes) ? scenes.filter((scene) => scene && typeof scene.id === "string") : [];
    dom.sceneList.setAttribute("aria-busy", "false");
    dom.sceneList.replaceChildren();
    if (!currentScenes.length) {
      dom.sceneList.append(make("div", "empty-state", "本地服务暂未提供场景。"));
      return;
    }
    for (const [index, scene] of currentScenes.entries()) {
      const button = make("button", "scene-card");
      button.type = "button";
      button.dataset.sceneId = scene.id;
      const sceneIcon = make("span", "scene-icon");
      const key = `${scene.id} ${scene.name || ""}`.toLowerCase();
      const name = /read|阅读/.test(key) ? "book" : /screen|电脑|屏幕/.test(key) ? "screen" : /relax|放松/.test(key) ? "moon" : ["book", "screen", "moon"][index % 3];
      sceneIcon.append(icon(name));
      const brightness = validNumber(scene.brightness_pct) ? `${Math.round(scene.brightness_pct)}%` : "—%";
      const temp = validNumber(scene.color_temp) ? `${Math.round(scene.color_temp)} K` : "— K";
      button.append(sceneIcon, make("strong", "", scene.name || scene.id), make("span", "scene-settings", `${brightness} · ${temp}`), make("span", "scene-description", scene.description || "本地亮度与色温组合"));
      button.setAttribute("aria-label", `应用本地场景：${scene.name || scene.id}，${brightness}，${temp}`);
      const state = currentState();
      const active = isOnline() && state?.power === true && percentOf(state) === Math.round(scene.brightness_pct) && tempOf(state) === scene.color_temp;
      button.classList.toggle("is-current", active);
      button.addEventListener("click", () => performOperation({
        endpoint: "/api/scene", body: { id: scene.id }, loading: `正在应用“${scene.name || scene.id}”本地场景并读回…`,
        success: `“${scene.name || scene.id}”场景已由设备读回确认。`, resetDraft: true
      }));
      dom.sceneList.append(button);
    }
  }

  function capabilityTarget(capability) {
    if (isSideCapability(capability)) return snapshot?.experimental_side_light === true ? "sideLightPanel" : null;
    const text = `${capability.id} ${capability.title}`.toLowerCase();
    if (/restor|还原|恢复/.test(text)) return "restoreButton";
    if (/scene|场景/.test(text)) return "scenePanel";
    if (/timer|countdown|定时|倒计时/.test(text)) return "timerPanel";
    if (/power|bright|color.temp|cct|开关|亮度|色温|调光/.test(text)) return "mainControls";
    return null;
  }

  function renderCapabilities(capabilities) {
    currentCapabilities = Array.isArray(capabilities) ? capabilities.filter((entry) => entry && typeof entry === "object") : [];
    dom.capabilityList.replaceChildren();
    dom.capabilityCount.textContent = String(currentCapabilities.length);
    if (!currentCapabilities.length) {
      dom.capabilityList.append(make("div", "empty-state", "暂无能力清单。以服务返回为准。"));
      return;
    }
    for (const capability of currentCapabilities) {
      const sideLight = isSideCapability(capability);
      const status = sideLight ? "experimental" : ["verified", "available", "experimental", "unadapted"].includes(capability.status) ? capability.status : "available";
      const visualStatus = status === "verified" && isSimulated() ? "simulated" : status;
      const target = status === "unadapted" ? null : capabilityTarget(capability);
      const card = make(target || status === "unadapted" ? "button" : "article", `capability-card is-${visualStatus}`);
      if (card.tagName === "BUTTON") card.type = "button";
      if (status === "unadapted") card.disabled = true;
      const top = make("span", "capability-top");
      const badgeText = { verified: "实机已验证", simulated: "模拟回读", available: "本地可用", experimental: "实验性待验证", unadapted: "未适配" }[visualStatus];
      top.append(make("span", "capability-title", capability.title || capability.id || "未命名功能"), make("span", `capability-badge is-${visualStatus}`, badgeText));
      const description = sideLight ? "已定位协议，实验待验证。查询字段仅为候选，不代表物理验证 / Candidate query fields; not physically verified." : status === "experimental" ? "实验性功能，待验证 / Experimental; pending verification." : visualStatus === "simulated" ? "仅由模拟服务回读，不代表真实台灯验证 / Simulated readback only; no hardware verification." : capability.description || "暂无说明";
      card.append(top, make("span", "capability-description", description));
      if (target) {
        const hint = make("span", "capability-action", status === "experimental" ? "查看实验面板" : isReadOnly() ? "查看状态" : "前往控制");
        hint.append(icon("arrow"));
        card.append(hint);
        card.addEventListener("click", () => {
          const destination = $(target);
          destination?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
          const focusTarget = destination?.matches("button") ? destination : destination?.querySelector("button:enabled, input:enabled");
          focusTarget?.focus({ preventScroll: true });
        });
      } else if (status === "unadapted") {
        const hint = make("span", "capability-action", "待完成协议适配");
        hint.prepend(icon("lock"));
        card.append(hint);
      }
      dom.capabilityList.append(card);
    }
  }

  function renderDevice(device) {
    const details = device && typeof device === "object" ? device : {};
    const fields = [["设备名称", details.name], ["型号", details.model || MODEL], ["单播 IP", details.ip], ["MAC 地址", details.mac], ["UDP 端口", details.port], ["SKU", details.sku], ["版本字段（原始）", details.version]];
    dom.deviceDetails.replaceChildren();
    for (const [label, value] of fields) {
      const row = make("div");
      row.append(make("dt", "", label), make("dd", "", displayValue(value)));
      dom.deviceDetails.append(row);
    }
  }

  function renderActivity(activity) {
    const entries = Array.isArray(activity) ? activity.filter((entry) => entry && typeof entry === "object").slice(0, 10) : [];
    dom.activityList.replaceChildren();
    if (!entries.length) {
      dom.activityList.append(make("li", "empty-state", "暂时没有操作记录。"));
      return;
    }
    for (const entry of entries) {
      const experimental = entry.experimental === true || /side.light|侧灯|副灯/.test(`${entry.endpoint || ""} ${entry.action || ""} ${entry.label || ""} ${entry.details || ""}`.toLowerCase());
      const recordedOutcome = ["success", "error", "info"].includes(entry.outcome) ? entry.outcome : "info";
      const outcome = experimental && recordedOutcome === "success" ? "info" : recordedOutcome;
      const item = make("li", `activity-item is-${outcome}${isSimulated() ? " is-simulated" : ""}${experimental ? " is-experimental" : ""}`);
      const head = make("div", "activity-head");
      const time = make("time", "", formatTime(entry.at));
      if (dateValue(entry.at)) time.dateTime = entry.at;
      head.append(make("strong", "", `${isSimulated() ? "模拟 · " : ""}${entry.label || "操作记录"}`), time);
      let details = entry.details || "暂无详细信息";
      if (experimental && outcome !== "error") details = entry.candidate_readback_matched === true ? "候选字段匹配，待目视验证 / Candidate fields match; visual verification pending." : "实验操作记录；候选字段与物理效果仍待验证 / Experimental record; candidate fields and physical effects remain unverified.";
      else if (isSimulated() && outcome !== "error") details = "仅记录模拟服务状态，不代表真实台灯执行或验证。";
      const result = outcome === "error" ? "服务记录：失败" : experimental ? "实验性 · 待目视验证" : isSimulated() ? outcome === "success" ? "模拟记录：完成" : "模拟状态信息" : outcome === "success" ? "服务记录：成功" : "状态信息";
      item.append(head, make("p", "", details), make("div", "activity-outcome", result));
      dom.activityList.append(item);
    }
  }

  function renderTimer() {
    const timer = snapshot?.timer;
    if (!timer || typeof timer.active !== "boolean") {
      dom.timerLabel.textContent = "尚无定时读数";
      dom.timerCountdown.textContent = "— : —";
      dom.timerEndTime.textContent = "由本地服务执行";
      return;
    }
    if (!timer.active) {
      dom.timerLabel.textContent = "未设置定时";
      dom.timerCountdown.textContent = "— : —";
      dom.timerEndTime.textContent = "给忙碌的一天，留一点余地";
      return;
    }
    const endsAt = dateValue(timer.ends_at);
    const remaining = endsAt ? Math.ceil((endsAt.getTime() - Date.now()) / 1000) : Math.ceil(Number(timer.seconds_remaining || 0) - (Date.now() - timerReceivedAt) / 1000);
    const seconds = Math.max(0, Number.isFinite(remaining) ? remaining : 0);
    dom.timerLabel.textContent = seconds > 0 ? `距${isSimulated() ? "模拟" : "计划"}关灯${isOnline() ? "" : " · 最近记录"}` : isSimulated() ? "模拟倒计时已到，等待模拟回读" : "倒计时已到，等待读回";
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    dom.timerCountdown.replaceChildren(document.createTextNode(String(minutes).padStart(2, "0")), make("span", "timer-muted", " : "), document.createTextNode(String(rest).padStart(2, "0")));
    dom.timerEndTime.textContent = isSimulated() ? `${endsAt ? `预计 ${formatTime(timer.ends_at, false)} · ` : ""}模拟定时，不控制真实台灯` : endsAt ? `预计 ${formatTime(timer.ends_at, false)} 执行 · 本地服务定时` : "显示为本地估算，结果以设备读回为准";
  }

  function updateDisabled() {
    const controlsDisabled = !hasControls();
    dom.powerButton.disabled = controlsDisabled;
    dom.applyButton.disabled = controlsDisabled;
    dom.restoreButton.disabled = controlsDisabled || !stateExists(snapshot?.initial_state);
    dom.setTimerButton.disabled = controlsDisabled;
    dom.cancelTimerButton.disabled = requestPending || !snapshot?.timer?.active;
    dom.refreshButton.disabled = requestPending;
    dom.refreshButton.classList.toggle("is-spinning", requestPending && !operationPending);
    dom.brightnessRange.disabled = operationPending;
    dom.colorTempRange.disabled = operationPending;
    dom.customMinutes.disabled = operationPending || isReadOnly();
    dom.timerForm.querySelectorAll('input[type="radio"]').forEach((input) => { input.disabled = operationPending || isReadOnly(); });
    dom.sceneList.querySelectorAll("button").forEach((button) => { button.disabled = controlsDisabled; });
    dom.sideLightOnButton.disabled = !hasSideControls("arm_power_raw");
    dom.sideLightOffButton.disabled = !hasSideControls("arm_power_raw");
    dom.sideLightBrightnessRange.disabled = !hasSideControls("arm_brightness_raw");
    dom.sideLightApplyButton.disabled = !hasSideControls("arm_brightness_raw");
    dom.applyButtonText.textContent = operationPending ? "正在处理…" : isReadOnly() ? "只读模式 · 应用已禁用" : isSimulated() ? "模拟开灯并应用" : "开灯并应用";
    $("mainControls").setAttribute("aria-busy", String(operationPending));
    dom.sideLightPanel.setAttribute("aria-busy", String(operationPending));
  }

  function receiveStatus(data, options = {}) {
    const previous = snapshot || {};
    const next = { ...previous, ...data };
    if (!Object.prototype.hasOwnProperty.call(data, "state")) next.state = previous.state;
    snapshot = next;
    renderMode();
    setConnection(next.online === true ? "online" : next.online === false ? "offline" : "unknown");
    if (options.resetDraft && isOnline() && stateExists(next.state)) {
      draftDirty = false;
      hasDraftBaseline = false;
    }
    if (options.resetSideDraft) sideDraftDirty = false;
    if (previous.simulated !== next.simulated || previous.experimental_side_light !== next.experimental_side_light) {
      sideDraftDirty = false;
      dom.sideLightFeedback.className = "side-light-feedback";
      dom.sideLightFeedback.textContent = `${isSimulated() ? "模拟 / Simulation · " : ""}尚未发送实验指令 / No experimental command sent.`;
    }
    if (Object.prototype.hasOwnProperty.call(data, "timer")) timerReceivedAt = Date.now();
    renderState();
    renderSideLight();
    renderScenes(next.scenes);
    renderCapabilities(next.capabilities);
    renderDevice(next.device);
    renderActivity(next.activity);
    renderTimer();
    updateDisabled();
  }

  async function apiRequest(endpoint, method = "GET", body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    try {
      const headers = { Accept: "application/json" };
      const options = { method, headers, signal: controller.signal, cache: "no-store", credentials: "same-origin" };
      if (body !== undefined) {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
      }
      const response = await fetch(endpoint, options);
      let data;
      try { data = await response.json(); } catch {
        throw new Error(`本地服务未返回有效 JSON（HTTP ${response.status}）。`);
      }
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("本地服务返回格式不符合约定。");
      return { response, data };
    } catch (error) {
      if (error.name === "AbortError") throw new Error("本地服务响应超时，请刷新状态后重试。");
      if (error instanceof TypeError) throw new Error("无法连接本地服务，请确认服务地址与运行状态。");
      throw error;
    } finally { clearTimeout(timeout); }
  }

  function schedulePoll() {
    clearTimeout(pollHandle);
    pollDue = Date.now() + POLL_INTERVAL;
    if (!document.hidden) pollHandle = setTimeout(() => fetchStatus(), POLL_INTERVAL);
  }

  async function fetchStatus(manual = false) {
    if (requestPending || document.hidden && !manual) return;
    clearTimeout(pollHandle);
    requestPending = true;
    updateDisabled();
    if (manual) setFeedback("loading", isSimulated() ? "正在重新查询模拟状态…" : "正在重新查询设备实际状态…");
    try {
      const { response, data } = await apiRequest("/api/status");
      if (!response.ok || data.ok !== true) {
        receiveStatus({ ...data, online: data.online === false ? false : undefined });
        throw new Error(data.message || `状态查询失败（HTTP ${response.status}）。`);
      }
      const shouldAnnounce = !snapshot || manual || statusHasFailed || (data.online === true) !== isOnline() || data.simulated !== snapshot?.simulated || data.read_only !== snapshot?.read_only;
      receiveStatus(data);
      statusHasFailed = false;
      if (shouldAnnounce) {
        if (!isOnline()) setFeedback("warning", isSimulated() ? "模拟服务状态待确认。已有模拟读数仅供参考，请刷新。" : data.message || "台灯离线。已有读数仅供参考，请检查同网连接后刷新。");
        else if (!currentState()) setFeedback("warning", isSimulated() ? "服务在线，但尚未获得模拟状态，请稍后刷新。" : "服务在线，但尚未获得设备实际状态，请稍后刷新。");
        else if (isReadOnly()) setFeedback("info", "已读取状态。只读模式不会改变灯光；滑块仅供本页预览，可取消已保存的本地定时。");
        else if (isSimulated()) setFeedback("info", "已读取模拟状态；点击控制仅更新模拟数据，不连接真实台灯 / Simulation · no hardware.");
        else setFeedback("info", data.message || "已读取设备状态。拖动滑块可预览，点击“开灯并应用”后生效。");
      }
    } catch (error) {
      statusHasFailed = true;
      if (connection !== "offline") setConnection("unknown");
      renderState();
      setFeedback("error", `${error.message} ${currentState() ? "现有读数为旧值。" : "尚未获得设备读数。"}`);
      if (!snapshot) {
        dom.sceneList.setAttribute("aria-busy", "false");
        dom.sceneList.replaceChildren(make("div", "empty-state", "连接本地服务后载入场景。"));
        dom.capabilityList.replaceChildren(make("div", "empty-state", "功能清单等待服务连接，不预设设备能力。"));
      }
    } finally {
      requestPending = false;
      updateDisabled();
      schedulePoll();
    }
  }

  async function performOperation({ endpoint, method = "POST", body, loading, success, requireVerified = true, resetDraft = false }) {
    if (requestPending) return;
    const experimental = endpoint === "/api/experimental/side-light";
    const cancellingTimer = endpoint === "/api/timer" && method === "DELETE";
    const feedback = experimental ? setSideFeedback : setFeedback;
    if (!cancellingTimer && !hasControls()) {
      feedback("warning", isReadOnly() ? "只读模式已禁用写入，不会改变灯光 / Read-only · no light changes." : "状态尚未确认，请先刷新并等待服务在线。");
      return;
    }
    if (cancellingTimer && !snapshot?.timer?.active) return;
    if (experimental) {
      const powerCommand = typeof body?.power === "boolean";
      const field = powerCommand ? "arm_power_raw" : "arm_brightness_raw";
      if (!hasSideControls(field) || !powerCommand && (!Number.isInteger(body?.brightness) || body.brightness < 10 || body.brightness > 255)) {
        feedback("warning", "未读到对应候选字段或原始亮度超出 10–255；请先刷新状态 / Missing candidate field or raw brightness outside 10–255.");
        return;
      }
    }
    clearTimeout(pollHandle);
    requestPending = true;
    operationPending = true;
    updateDisabled();
    feedback("loading", loading);
    try {
      const { response, data } = await apiRequest(endpoint, method, body);
      if (!response.ok || data.ok !== true) {
        receiveStatus({ ...data, online: data.online === false ? false : undefined });
        statusHasFailed = true;
        feedback("error", data.message || `操作失败（HTTP ${response.status}），请查询状态后重试。`);
        return;
      }
      const verified = !requireVerified || data.verified === true;
      receiveStatus(data, { resetDraft: !experimental && resetDraft && verified, resetSideDraft: experimental && Number.isInteger(body?.brightness) && data.experimental === true && data.candidate_readback_matched === true });
      if (experimental) {
        statusHasFailed = false;
        if (data.experimental !== true) feedback("warning", "服务未返回实验标记，候选读回待核对；物理效果待目视验证 / Experimental marker missing; readback and physical effects remain unverified.");
        else if (data.candidate_readback_matched === true) feedback("warning", "候选字段匹配，待目视验证 / Candidate fields match; visual verification pending.");
        else if (data.candidate_readback_matched === false) feedback("warning", "候选字段未匹配，物理效果待目视验证；不会自动重发 / Candidate fields did not match; visual verification pending. No automatic resend.");
        else feedback("warning", "未返回候选字段匹配结果，待目视验证 / Candidate match result missing; visual verification pending.");
        return;
      }
      if (!verified) {
        statusHasFailed = true;
        feedback("warning", isSimulated() ? "请求已返回，但未收到模拟回读确认；请刷新模拟状态。" : "请求已返回，但未收到设备验证确认。操作结果待验证，请刷新实际状态。");
        return;
      }
      statusHasFailed = false;
      feedback("success", isSimulated() ? cancellingTimer ? "本地服务已确认取消模拟关灯定时；未连接真实台灯。" : requireVerified ? "模拟操作已完成，模拟状态已回读；未连接真实台灯 / Simulation · no hardware." : "本地服务已确认模拟定时；仅更新模拟状态，不连接真实台灯。" : success);
    } catch (error) {
      statusHasFailed = true;
      setConnection("unknown");
      renderState();
      feedback("error", `${error.message} 操作结果未确认，请刷新${isSimulated() ? "模拟" : "设备"}状态；不会自动重发。${experimental ? " / Experimental result unconfirmed; no automatic resend." : ""}`);
    } finally {
      operationPending = false;
      requestPending = false;
      updateDisabled();
      schedulePoll();
    }
  }

  function updateDraft() {
    draft = { brightness: Number(dom.brightnessRange.value), colorTemp: Number(dom.colorTempRange.value) };
    const state = currentState();
    draftDirty = !hasDraftBaseline || !state || draft.brightness !== clamp(percentOf(state) ?? 60, 1, 100) || draft.colorTemp !== clamp(tempOf(state) ?? 4000, 2700, 6500);
    renderDraft();
  }

  for (const range of [dom.brightnessRange, dom.colorTempRange]) {
    range.addEventListener("input", updateDraft);
    range.addEventListener("change", updateDraft);
    range.addEventListener("pointerdown", () => { draftEditing = true; });
    range.addEventListener("focus", () => { draftEditing = true; });
    range.addEventListener("blur", () => { draftEditing = false; });
  }
  document.addEventListener("pointerup", () => { draftEditing = isDraftFocused(); });
  document.addEventListener("pointercancel", () => { draftEditing = isDraftFocused(); });
  dom.colorTempRange.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"].includes(event.key)) return;
    event.preventDefault();
    const direction = ["ArrowRight", "ArrowUp"].includes(event.key) ? 1 : -1;
    dom.colorTempRange.value = String(clamp(Number(dom.colorTempRange.value) + direction * (event.shiftKey ? 10 : 100), 2700, 6500));
    updateDraft();
  });

  dom.refreshButton.addEventListener("click", () => fetchStatus(true));
  dom.powerButton.addEventListener("click", () => {
    const state = currentState();
    if (!state) return;
    const power = !state.power;
    performOperation({ endpoint: "/api/control", body: { power }, loading: `正在${power ? "开启" : "关闭"}灯光并读回状态…`, success: `${power ? "开灯" : "关灯"}已由设备读回确认。` });
  });
  dom.applyButton.addEventListener("click", () => performOperation({
    endpoint: "/api/control", body: { power: true, brightness: Math.round(draft.brightness * 255 / 100), color_temp: draft.colorTemp },
    loading: "正在开灯并应用光线，等待设备读回…", success: "已开灯并应用亮度与色温，设备状态读回确认。", resetDraft: true
  }));
  dom.restoreButton.addEventListener("click", () => performOperation({
    endpoint: "/api/restore", body: {}, loading: "正在恢复本次启动时状态并读回…", success: "本次启动时的开关、亮度与色温已恢复，设备读回确认。", resetDraft: true
  }));

  dom.sideLightBrightnessRange.addEventListener("input", () => {
    sideBrightnessDraft = clamp(Math.round(Number(dom.sideLightBrightnessRange.value)), 10, 255);
    sideDraftDirty = sideBrightnessDraft !== sideChannels()?.arm_brightness_raw;
    renderSideDraft();
  });
  for (const [button, power] of [[dom.sideLightOnButton, true], [dom.sideLightOffButton, false]]) {
    button.addEventListener("click", () => performOperation({
      endpoint: "/api/experimental/side-light", body: { power }, requireVerified: false,
      loading: `正在发送一次实验${power ? "开启" : "关闭"}侧灯指令，仅核对候选字段 / One experimental request; candidate fields only…`
    }));
  }
  dom.sideLightApplyButton.addEventListener("click", () => performOperation({
    endpoint: "/api/experimental/side-light", body: { brightness: Number(dom.sideLightBrightnessRange.value) }, requireVerified: false,
    loading: "正在发送一次实验侧灯亮度指令，仅核对候选字段 / One experimental brightness request; candidate fields only…"
  }));

  dom.timerForm.addEventListener("change", () => {
    const custom = dom.timerForm.querySelector('input[name="timerMinutes"]:checked')?.value === "custom";
    dom.customTimerRow.hidden = !custom;
    dom.customMinutes.required = custom;
  });
  dom.timerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!hasControls()) return;
    const selected = dom.timerForm.querySelector('input[name="timerMinutes"]:checked')?.value;
    const minutes = Number(selected === "custom" ? dom.customMinutes.value : selected);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 120) {
      setFeedback("error", "请填写 1–120 之间的整数分钟。");
      dom.customMinutes.focus();
      return;
    }
    performOperation({ endpoint: "/api/timer", body: { minutes }, requireVerified: false, loading: `正在设置 ${minutes} 分钟本地关灯定时…`, success: `本地服务已确认设置 ${minutes} 分钟定时；到时关灯后仍需设备读回确认。` });
  });
  dom.cancelTimerButton.addEventListener("click", () => performOperation({
    endpoint: "/api/timer", method: "DELETE", requireVerified: false, loading: "正在取消本地关灯定时…", success: "本地服务已确认取消关灯定时。"
  }));

  function setupTabs(selector) {
    const tabs = Array.from(document.querySelectorAll(selector));
    const activate = (selected) => {
      for (const tab of tabs) {
        const active = tab === selected;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        tab.classList.toggle("is-active", active);
        $(tab.getAttribute("aria-controls")).hidden = !active;
      }
    };
    for (const [index, tab] of tabs.entries()) {
      tab.addEventListener("click", () => activate(tab));
      tab.addEventListener("keydown", (event) => {
        let target = null;
        if (event.key === "ArrowRight") target = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") target = tabs[(index - 1 + tabs.length) % tabs.length];
        if (event.key === "Home") target = tabs[0];
        if (event.key === "End") target = tabs[tabs.length - 1];
        if (target) { event.preventDefault(); activate(target); target.focus(); }
      });
    }
  }
  setupTabs('.tabs [role="tab"]');
  setupTabs('.plan-steps [role="tab"]');

  dom.multicastDemoButton.addEventListener("click", () => {
    const enabled = dom.multicastDemoButton.getAttribute("aria-pressed") !== "true";
    dom.multicastDemoButton.setAttribute("aria-pressed", String(enabled));
    dom.multicastDiagram.classList.toggle("is-demonstrating", enabled);
    dom.multicastDemoButton.replaceChildren(document.createTextNode(enabled ? "停止示意" : "演示同组接收"), icon("arrow"));
    dom.multicastFeedback.textContent = enabled ? "本页示意：数据发往接收组，同组成员可接收；这不代表台灯发现或连接成功，未发送网络数据。" : "点击只播放本页示意，不发送任何网络数据。";
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearTimeout(pollHandle);
    else if (!requestPending && Date.now() >= pollDue) fetchStatus();
    else if (!requestPending) schedulePoll();
  });
  setInterval(renderTimer, 1000);
  renderDraft();
  fetchStatus();
})();
