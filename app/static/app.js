"use strict";

const state = {
  bootstrap: null,
  dashboard: null,
  draft: null,
  authenticated: false,
  username: "",
  editor: false,
  setupImport: null,
  health: new Map(),
  widgets: new Map(),
  widgetSupport: [],
  system: null,
  search: "",
  collapsed: new Set(),
  editingItem: null,
  editorTab: "appearance",
  activePage: "home",
};

const app = document.getElementById("app");
const overlay = document.getElementById("overlay");
const toastElement = document.getElementById("toast");

const LOCAL_ICONS = {
  qbittorrent: "/icons/qbittorrent.svg", prowlarr: "/icons/prowlarr.svg",
  radarr: "/icons/radarr.svg", sonarr: "/icons/sonarr.svg", seerr: "/icons/seerr.svg",
  jellyseerr: "/icons/seerr.svg", overseerr: "/icons/seerr.svg", bazarr: "/icons/bazarr.svg",
  tautulli: "/icons/tautulli.svg", pihole: "/icons/pihole.svg", dozzle: "/icons/dozzle.svg",
  uptimekuma: "/icons/uptime-kuma.svg", dockge: "/icons/dockge.svg",
  flaresolverr: "/icons/flaresolverr.svg",
  github: "/icons/github.svg",
  rogueroutegpx: "/icons/rogueroute-gpx.svg", rogueroutegpxweb: "/icons/rogueroute-gpx.svg",
  roguerouteosrm: "/icons/rogueroute-osrm.svg", rogueroutegpxosrm: "/icons/rogueroute-osrm.svg",
  rogueroutemanager: "/icons/rogueroute-manager.svg", rogueroutegpxmanager: "/icons/rogueroute-manager.svg",
};

const THEME_PRESETS = {
  neon: ["#ff2bd6", "#00e5ff"], midnight: ["#7c5cff", "#1db7bd"],
  graphite: ["#aeb6c5", "#667085"], ocean: ["#24a8ff", "#38f2cf"],
  ember: ["#ff5d3d", "#ffbf36"], light: ["#6d4aff", "#0aa6b7"],
};

const INTEGRATION_DEFAULTS = {
  qbittorrent: { refs: ["RGDASH_QBITTORRENT_API_KEY", "RGDASH_QBITTORRENT_USERNAME", "RGDASH_QBITTORRENT_PASSWORD"], bindings: { api_key: "RGDASH_QBITTORRENT_API_KEY", username: "RGDASH_QBITTORRENT_USERNAME", password: "RGDASH_QBITTORRENT_PASSWORD" } },
  prowlarr: { refs: ["RGDASH_PROWLARR_KEY"], bindings: { key: "RGDASH_PROWLARR_KEY" } },
  radarr: { refs: ["RGDASH_RADARR_KEY"], bindings: { key: "RGDASH_RADARR_KEY" } },
  sonarr: { refs: ["RGDASH_SONARR_KEY"], bindings: { key: "RGDASH_SONARR_KEY" } },
  seerr: { refs: ["RGDASH_SEERR_KEY"], bindings: { key: "RGDASH_SEERR_KEY" } },
  bazarr: { refs: ["RGDASH_BAZARR_KEY"], bindings: { key: "RGDASH_BAZARR_KEY" } },
  tautulli: { refs: ["RGDASH_TAUTULLI_KEY"], bindings: { key: "RGDASH_TAUTULLI_KEY" } },
  pihole: { refs: ["RGDASH_PIHOLE_KEY"], bindings: { key: "RGDASH_PIHOLE_KEY" } },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(value) : "";
  } catch {
    return "";
  }
}

function iconKey(value) {
  return String(value || "").split(/[\\/]/).pop().replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function iconFor(item) {
  const supplied = item.icon || "";
  if (/^(https?:|data:|\/custom\/|\/icons\/)/i.test(supplied)) return safeUrl(supplied);
  const candidates = [iconKey(supplied), iconKey(item.widget?.type), iconKey(item.name)];
  return candidates.map(key => LOCAL_ICONS[key]).find(Boolean) || "";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

function toast(message) {
  toastElement.textContent = message;
  toastElement.hidden = false;
  clearTimeout(toastElement.timer);
  toastElement.timer = setTimeout(() => { toastElement.hidden = true; }, 3200);
}

async function load() {
  try {
    const bootstrap = await request("/api/bootstrap");
    state.bootstrap = bootstrap;
    state.authenticated = bootstrap.authenticated;
    state.username = bootstrap.username || "";
    state.dashboard = bootstrap.dashboard;
    state.draft = structuredClone(bootstrap.dashboard);
    if (!state.draft.pages?.some(page => page.id === state.activePage)) state.activePage = state.draft.pages?.[0]?.id || "home";
    if (bootstrap.setupRequired) renderSetup();
    else renderDashboard();
  } catch (error) {
    app.innerHTML = `<main class="center-stage"><section class="error-card"><div class="brand-mark">R</div><h1>Dashboard unavailable</h1><p>${escapeHtml(error.message)}</p><button class="button primary" id="retry">Try again</button></section></main>`;
    document.getElementById("retry").onclick = load;
  }
}

function renderSetup() {
  app.innerHTML = `
    <main class="setup-shell">
      <div class="setup-glow setup-glow-one"></div><div class="setup-glow setup-glow-two"></div>
      <section class="setup-card">
        <header class="setup-brand"><div class="brand-mark">R</div><div><strong>Rogue Dashboard</strong><span>Docker setup</span></div></header>
        <div class="setup-progress"><span class="active"></span><span class="active"></span><span class="active"></span></div>
        <form class="setup-page" id="setup-form">
          <div class="setup-icon">◆</div><p class="eyebrow">WELCOME HOME</p>
          <h1>Your Docker services, without the configuration headache.</h1>
          <p class="lead">Name the dashboard, optionally import your previous configuration, then create the local administrator who can change it.</p>
          <label class="field"><span>Dashboard name</span><input id="setup-title" maxlength="100" value="${escapeHtml(state.draft.meta.title)}" required></label>
          <label class="upload-zone" id="setup-upload">
            <input id="setup-files" type="file" accept=".json,.zip,.yaml,.yml" multiple>
            <strong>Restore Rogue Dashboard JSON or choose legacy ZIP/YAML</strong><span>Credentials remain environment references</span>
          </label>
          <div id="setup-import-result"></div>
          <div class="form-grid">
            <label class="field full"><span>Administrator username</span><input id="setup-user" autocomplete="username" value="admin" minlength="2" required></label>
            <label class="field"><span>Password</span><input id="setup-password" type="password" autocomplete="new-password" minlength="10" required></label>
            <label class="field"><span>Confirm password</span><input id="setup-confirm" type="password" autocomplete="new-password" minlength="10" required></label>
          </div>
          <div class="notice error" id="setup-error" hidden></div>
          <button class="button primary large full-button" id="setup-submit">Open dashboard <span>→</span></button>
        </form>
      </section>
    </main>`;
  document.getElementById("setup-files").onchange = event => importForSetup(event.target.files);
  document.getElementById("setup-form").onsubmit = completeSetup;
}

async function importPayload(files) {
  const selected = [...files];
  if (!selected.length) throw new Error("Choose a legacy dashboard ZIP or YAML file first.");
  const zip = selected.find(file => file.name.toLowerCase().endsWith(".zip"));
  if (zip) {
    if (zip.size > 2_000_000) throw new Error("The configuration ZIP must be smaller than 2 MB.");
    const bytes = new Uint8Array(await zip.arrayBuffer());
    let binary = "";
    for (let index = 0; index < bytes.length; index += 32768) {
      binary += String.fromCharCode(...bytes.subarray(index, index + 32768));
    }
    return { zipBase64: btoa(binary) };
  }
  const result = {};
  for (const file of selected) {
    if (/\.(yaml|yml)$/i.test(file.name)) result[file.name.split(/[\\/]/).pop()] = await file.text();
  }
  return { files: result };
}

async function previewImport(files) {
  const selected = [...files];
  const jsonFile = selected.find(file => file.name.toLowerCase().endsWith(".json"));
  if (jsonFile) {
    if (jsonFile.size > 2_000_000) throw new Error("The dashboard backup must be smaller than 2 MB.");
    let dashboard;
    try { dashboard = JSON.parse(await jsonFile.text()); }
    catch { throw new Error("The selected JSON backup could not be parsed."); }
    return request("/api/import/dashboard", { method: "POST", body: JSON.stringify({ dashboard }) });
  }
  return request("/api/import/homepage", { method: "POST", body: JSON.stringify(await importPayload(files)) });
}

async function importForSetup(files) {
  const resultBox = document.getElementById("setup-import-result");
  resultBox.innerHTML = `<div class="notice info">Reading configuration…</div>`;
  try {
    const result = await previewImport(files);
    state.setupImport = result;
    state.draft = structuredClone(result.dashboard);
    document.getElementById("setup-title").value = result.dashboard.meta.title;
    const secretText = result.summary.secretReferences.length ? ` · ${result.summary.secretReferences.length} safe environment references` : "";
    resultBox.innerHTML = `<div class="notice good">Ready: ${result.summary.services} services, ${result.summary.bookmarks} bookmarks, ${result.summary.groups} groups${secretText}</div>${result.warnings.map(w => `<div class="notice warning">${escapeHtml(w)}</div>`).join("")}`;
  } catch (error) {
    resultBox.innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`;
  }
}

async function completeSetup(event) {
  event.preventDefault();
  const errorBox = document.getElementById("setup-error");
  const password = document.getElementById("setup-password").value;
  const confirm = document.getElementById("setup-confirm").value;
  if (password !== confirm) {
    errorBox.textContent = "The passwords do not match.";
    errorBox.hidden = false;
    return;
  }
  const dashboard = structuredClone(state.draft);
  dashboard.meta.title = document.getElementById("setup-title").value.trim() || "My Docker Dashboard";
  const button = document.getElementById("setup-submit");
  button.disabled = true;
  button.textContent = "Finishing setup…";
  try {
    await request("/api/setup", {
      method: "POST",
      body: JSON.stringify({ username: document.getElementById("setup-user").value, password, dashboard }),
    });
    await load();
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
    button.disabled = false;
    button.textContent = "Open dashboard →";
  }
}

function initials(name) {
  return name.split(/\s+/).map(part => part[0]).join("").slice(0, 2).toUpperCase();
}

function formatBytes(value) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = Number(value || 0), unit = 0;
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit++; }
  return `${amount.toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`;
}

function formatUptime(seconds) {
  const days = Math.floor((seconds || 0) / 86400);
  const hours = Math.floor(((seconds || 0) % 86400) / 3600);
  return days ? `${days}d ${hours}h` : `${hours}h`;
}

function renderDashboard() {
  const dashboard = state.draft;
  document.title = dashboard.meta.title;
  app.innerHTML = `
    <div class="app-shell theme-${escapeHtml(dashboard.meta.theme)} background-${escapeHtml(dashboard.meta.backgroundMode)} density-${escapeHtml(dashboard.meta.density)} ${state.editor ? "editing" : ""}" id="shell">
      <div class="dashboard-background" id="dashboard-background"></div><div class="ambient ambient-one"></div><div class="ambient ambient-two"></div>
      <main class="dashboard ${dashboard.meta.fullWidth ? "full-width" : ""}">
        <header class="topbar">
          <div class="brand-block"><div class="brand-mark small">R</div><div><h1>${escapeHtml(dashboard.meta.title)}</h1><p>${escapeHtml(dashboard.meta.subtitle)}</p></div></div>
          <div class="topbar-actions"><div class="search-box"><span>⌕</span><input id="search" placeholder="Search apps and bookmarks…" value="${escapeHtml(state.search)}"><button id="clear-search" aria-label="Clear search">×</button></div><button class="button glass" id="customise">${state.authenticated ? "⚙ Customise" : "↪ Admin"}</button></div>
        </header>
        <nav class="page-tabs" aria-label="Dashboard pages">${(dashboard.pages || [{ id: "home", name: "Home" }]).map(page => `<button class="${page.id === state.activePage ? "active" : ""}" data-page="${escapeHtml(page.id)}">${escapeHtml(page.name)}</button>`).join("")}</nav>
        <section class="stat-strip" id="stats">
          <div class="hero-time"><span>◷</span><div><strong id="clock">--:--</strong><span id="date">Loading…</span></div></div>
          <div class="mini-stat"><span>▣</span><div><strong id="container-count">—</strong><span id="container-label">Containers running</span></div></div>
          <div class="mini-stat"><span>●</span><div><strong id="online-count">—</strong><span>Services online</span></div></div>
          <div class="mini-stat"><span>▤</span><div><strong id="memory-count">—</strong><span id="memory-total">Memory</span></div></div>
          <div class="mini-stat"><span>⌁</span><div><strong id="load-count">—</strong><span id="uptime-count">System load</span></div></div>
        </section>
        <div class="result-count" id="result-count"></div><div class="groups" id="groups"></div>
        <footer class="page-footer"><span>Rogue Dashboard <strong>v${escapeHtml(state.bootstrap?.version || "0.8.0")}</strong></span><span>Local-first · Docker-powered</span></footer>
      </main>
      ${state.editor ? editorMarkup() : ""}
    </div>`;
  const shell = document.getElementById("shell");
  shell.style.setProperty("--accent", dashboard.meta.accent);
  shell.style.setProperty("--accent-secondary", dashboard.meta.accentSecondary);
  shell.style.setProperty("--glow-strength", Number(dashboard.meta.glow || 0) / 100);
  shell.style.setProperty("--glow-opacity", Number(dashboard.meta.glow || 0) / 590);
  shell.style.setProperty("--glow-blur", `${Math.round(Number(dashboard.meta.glow || 0) * .38)}px`);
  shell.style.setProperty("--surface-opacity", `${Number(dashboard.meta.surfaceOpacity || 82)}%`);
  const background = document.getElementById("dashboard-background");
  if (dashboard.meta.background) background.style.setProperty("--custom-background", `url("${dashboard.meta.background.replace(/["\\\n\r]/g, "")}")`);
  document.getElementById("search").oninput = event => { state.search = event.target.value; renderGroups(); };
  document.getElementById("clear-search").onclick = () => { state.search = ""; document.getElementById("search").value = ""; renderGroups(); };
  document.getElementById("customise").onclick = () => state.authenticated ? openEditor() : openLogin();
  document.querySelectorAll("[data-page]").forEach(button => button.onclick = () => {
    state.activePage = button.dataset.page;
    renderDashboard();
  });
  if (state.editor) bindEditor();
  renderGroups();
  updateClock();
  updateStats();
  refreshRuntime();
}

function renderGroups() {
  const container = document.getElementById("groups");
  if (!container) return;
  const query = state.search.trim().toLowerCase();
  let visibleCount = 0;
  const html = state.draft.groups.map((group, groupIndex) => {
    if ((group.pageId || state.draft.pages?.[0]?.id || "home") !== state.activePage) return "";
    const items = group.items.map((item, itemIndex) => ({ item, itemIndex })).filter(({ item }) => !query || `${item.name} ${item.description || ""} ${group.name}`.toLowerCase().includes(query));
    if (!items.length && (query || !state.editor)) return "";
    visibleCount += items.length;
    const collapsed = state.collapsed.has(group.id);
    const brandedLinks = group.id === "branded-links";
    return `<section class="service-group ${brandedLinks ? "branded-links-group" : ""}" data-group="${groupIndex}"><header class="group-header"><button class="group-title collapse-group" data-id="${escapeHtml(group.id)}"><span>${collapsed ? "›" : "⌄"}</span><h2>${escapeHtml(group.name)}</h2><span>${items.length}</span></button>${state.editor ? `<button class="button tiny add-card" data-group="${groupIndex}">+ Add card</button>` : ""}</header>${collapsed ? "" : `<div class="card-grid ${group.kind === "bookmarks" ? "bookmark-menu" : ""} ${state.draft.meta.equalHeights ? "equal" : ""}" style="--group-columns:${Math.min(group.columns, state.draft.meta.maxColumns)}">${items.map(({ item, itemIndex }) => cardMarkup(item, groupIndex, itemIndex, group.kind)).join("")}${state.editor && !items.length ? `<button class="empty-group add-card" data-group="${groupIndex}">+ Add the first card</button>` : ""}</div>`}</section>`;
  }).join("");
  container.innerHTML = html || `<section class="empty-search"><h2>No matching cards</h2><p>Try another search or add a service.</p></section>`;
  document.getElementById("result-count").textContent = query ? `${visibleCount} results for “${state.search}”` : "";
  container.querySelectorAll(".collapse-group").forEach(button => button.onclick = () => {
    state.collapsed.has(button.dataset.id) ? state.collapsed.delete(button.dataset.id) : state.collapsed.add(button.dataset.id);
    renderGroups();
  });
  container.querySelectorAll(".add-card").forEach(button => button.onclick = () => openItem(Number(button.dataset.group)));
  container.querySelectorAll(".card-edit").forEach(button => button.onclick = () => openItem(Number(button.dataset.group), Number(button.dataset.item)));
  if (state.editor) bindDragging(container);
}

function cardMarkup(item, groupIndex, itemIndex, groupKind) {
  const status = state.health.get(item.id);
  const widget = state.widgets.get(item.id);
  const statusState = status?.state || "unknown";
  const href = safeUrl(item.href);
  const iconUrl = iconFor(item);
  const statusMarkup = item.statusStyle !== "none" && item.monitorUrl ? `<span class="status ${statusState} ${item.statusStyle === "badge" ? "badge" : ""}">${item.statusStyle === "badge" ? escapeHtml(statusState) : ""}</span>` : "";
  const latency = Number.isFinite(widget?.latencyMs) ? widget.latencyMs : status?.latencyMs;
  const latencyMarkup = state.draft.meta.showLatency && Number.isFinite(latency) ? `<span class="connection-latency ${widget?.state === "error" || statusState === "offline" ? "failed" : ""}">${latency} ms</span>` : "";
  return `<article class="service-card ${groupKind === "bookmarks" || item.type === "bookmark" ? "bookmark-card" : ""} ${state.editor ? "editable" : ""} ${widget?.state === "ok" ? "has-widget" : ""}" data-group="${groupIndex}" data-item="${itemIndex}" draggable="${state.editor}">${state.editor ? `<span class="drag-handle">⋮⋮</span>` : ""}${latencyMarkup}<a ${href ? `href="${href}" target="_blank" rel="noreferrer"` : ""}><div class="service-main"><div class="service-icon">${iconUrl ? `<img src="${iconUrl}" alt="">` : `<span>${escapeHtml(initials(item.name))}</span>`}</div><div class="service-copy"><div class="service-name"><strong>${escapeHtml(item.name)}</strong><span>${href ? "↗" : ""}</span></div><p>${escapeHtml(item.description || (item.type === "bookmark" ? "Bookmark" : "Open service"))}</p></div>${statusMarkup}</div>${widgetCardMarkup(item, widget)}</a>${state.editor ? `<button class="card-edit" data-group="${groupIndex}" data-item="${itemIndex}" aria-label="Edit ${escapeHtml(item.name)}">✎</button>` : ""}</article>`;
}

function widgetCardMarkup(item, widget) {
  if (!item.widget) return "";
  if (widget?.state === "ok") {
    const columns = Math.max(1, Math.min(4, widget.metrics.length));
    return `<div class="widget-metrics" style="--widget-columns:${columns}">${widget.metrics.map(metric => `<span><strong>${escapeHtml(metric.value)}</strong><small>${escapeHtml(metric.label)}</small></span>`).join("")}</div>`;
  }
  const labels = {
    configuration_required: "Setup needed",
    error: "API unavailable",
    unsupported: "Coming later",
  };
  const detail = widget?.missingRefs?.length ? `Missing: ${widget.missingRefs.join(", ")}` : widget?.message || "Waiting for the first refresh";
  return `<span class="widget-chip widget-${escapeHtml(widget?.state || "loading")}" title="${escapeHtml(detail)}">${escapeHtml(labels[widget?.state] || item.widget.type)}</span>`;
}

function connectionDiagnosticsMarkup() {
  const items = state.draft.groups.flatMap(group => group.items).filter(item => item.widget || item.monitorUrl);
  if (!items.length) return `<div class="notice info">No service connections are configured.</div>`;
  return `<div class="widget-diagnostics">${items.map(item => {
    const live = state.widgets.get(item.id);
    const probe = state.health.get(item.id);
    const stateName = live?.state === "ok" ? (probe?.state === "offline" ? "error" : "ok") : live?.state || probe?.state || "loading";
    const latency = Number.isFinite(live?.latencyMs) ? live.latencyMs : probe?.latencyMs;
    const loadedEnvironment = (live?.environment || []).filter(entry => entry.loaded).map(entry => entry.name);
    const environmentDetail = loadedEnvironment.length ? ` · .env loaded: ${loadedEnvironment.join(", ")}` : "";
    const detail = live?.missingRefs?.length ? `Missing ${live.missingRefs.join(", ")}` : `${live?.message || (live?.state === "ok" ? `${live.metrics.length} API metrics responding` : probe?.state === "online" ? "Container endpoint responding" : "Waiting for connection test")}${environmentDetail}`;
    const endpoint = item.widget?.url || item.monitorUrl || "No private URL";
    const action = stateName === "ok" || stateName === "online" ? "Connected" : stateName === "configuration_required" ? "Configure" : stateName === "error" || stateName === "offline" ? "Check" : "Pending";
    return `<div class="widget-diagnostic"><span class="widget-state-dot ${escapeHtml(stateName)}"></span><div><strong>${escapeHtml(item.name)}</strong><small title="${escapeHtml(`${endpoint} · ${detail}`)}">${escapeHtml(item.widget?.type || "health probe")} · ${escapeHtml(endpoint)} · ${escapeHtml(detail)}</small></div><span>${Number.isFinite(latency) ? `${latency} ms · ` : ""}${action}</span></div>`;
  }).join("")}</div><div class="notice info">Credentials use <strong>RGDASH_*</strong> names in <strong>.env</strong>. Changes take effect after <strong>docker compose restart dashboard</strong>.</div>`;
}

function proxyDiagnosticsMarkup() {
  const proxy = state.bootstrap?.proxy || {};
  const host = proxy.requestHost || location.hostname;
  const external = host.includes(".") && !["localhost", "127.0.0.1"].includes(host);
  if (proxy.secure) return `<div class="notice good"><strong>Reverse proxy ready:</strong> HTTPS forwarding is detected for ${escapeHtml(host)}.</div>`;
  if (external) return `<div class="notice error"><strong>Proxy needs attention:</strong> ${escapeHtml(host)} reached the dashboard without X-Forwarded-Proto: https.</div>`;
  return `<div class="notice info"><strong>Local connection:</strong> open the public hostname to test Nginx/Cloudflare HTTPS forwarding.</div>`;
}

function bindDragging(container) {
  container.querySelectorAll(".service-card").forEach(card => {
    card.ondragstart = event => event.dataTransfer.setData("text/plain", JSON.stringify({ group: Number(card.dataset.group), item: Number(card.dataset.item) }));
    card.ondragover = event => event.preventDefault();
    card.ondrop = event => {
      event.preventDefault(); event.stopPropagation();
      const source = JSON.parse(event.dataTransfer.getData("text/plain"));
      moveItem(source.group, source.item, Number(card.dataset.group), Number(card.dataset.item));
    };
  });
  container.querySelectorAll(".service-group").forEach(group => {
    group.ondragover = event => event.preventDefault();
    group.ondrop = event => {
      event.preventDefault();
      const source = JSON.parse(event.dataTransfer.getData("text/plain"));
      moveItem(source.group, source.item, Number(group.dataset.group));
    };
  });
}

function moveItem(sourceGroup, sourceItem, targetGroup, targetItem) {
  const [item] = state.draft.groups[sourceGroup].items.splice(sourceItem, 1);
  let index = targetItem ?? state.draft.groups[targetGroup].items.length;
  if (sourceGroup === targetGroup && sourceItem < index) index--;
  state.draft.groups[targetGroup].items.splice(index, 0, item);
  renderGroups();
}

function editorMarkup() {
  return `<aside class="editor-panel">
    <header class="editor-header"><div><span class="eyebrow">LIVE PREVIEW</span><h2>Customise</h2></div><button class="icon-button" id="close-editor">×</button></header>
    <nav class="editor-tabs"><button data-editor-tab="appearance" class="${state.editorTab === "appearance" ? "active" : ""}">Appearance</button><button data-editor-tab="layout" class="${state.editorTab === "layout" ? "active" : ""}">Layout</button><button data-editor-tab="connect" class="${state.editorTab === "connect" ? "active" : ""}">Connect</button><button data-editor-tab="docker" class="${state.editorTab === "docker" ? "active" : ""}">Docker</button></nav>
    <div class="editor-content">
      <section class="editor-section editor-tab-panel ${state.editorTab === "appearance" ? "active" : ""}" data-editor-panel="appearance">
        <label class="field"><span>Dashboard title</span><input id="edit-title" value="${escapeHtml(state.draft.meta.title)}"></label>
        <label class="field"><span>Subtitle</span><input id="edit-subtitle" value="${escapeHtml(state.draft.meta.subtitle)}"></label>
        <div class="form-grid">
          <label class="field"><span>Theme preset</span><select id="edit-theme"><option value="neon">Electric Neon</option><option value="midnight">Midnight</option><option value="graphite">Graphite</option><option value="ocean">Ocean</option><option value="ember">Ember</option><option value="light">Daylight</option></select></label>
          <label class="field"><span>Card density</span><select id="edit-density"><option value="compact">Compact operations</option><option value="comfortable">Comfortable</option></select></label>
          <label class="field full"><span>Background effect</span><select id="edit-background-mode"><option value="neon-grid">Neon grid</option><option value="aurora">Aurora glow</option><option value="mesh">Colour mesh</option><option value="solid">Solid</option><option value="image">Custom image</option></select></label>
        </div>
        <label class="field color-field"><span>Primary neon colour</span><div><input id="edit-accent" type="color" value="${escapeHtml(state.draft.meta.accent)}"><input id="edit-accent-text" value="${escapeHtml(state.draft.meta.accent)}"></div></label>
        <label class="field color-field"><span>Secondary neon colour</span><div><input id="edit-accent-secondary" type="color" value="${escapeHtml(state.draft.meta.accentSecondary)}"><input id="edit-accent-secondary-text" value="${escapeHtml(state.draft.meta.accentSecondary)}"></div></label>
        <label class="field range-field"><span>Neon glow <strong id="glow-value">${state.draft.meta.glow}%</strong></span><input id="edit-glow" type="range" min="0" max="100" value="${state.draft.meta.glow}"></label>
        <label class="field range-field"><span>Card opacity <strong id="opacity-value">${state.draft.meta.surfaceOpacity}%</strong></span><input id="edit-opacity" type="range" min="45" max="100" value="${state.draft.meta.surfaceOpacity}"></label>
        <label class="field"><span>Custom background URL or local path</span><input id="edit-background" value="${escapeHtml(state.draft.meta.background)}" placeholder="/custom/backgrounds/my-background.jpg"><small>Choose Custom image above to display it.</small></label>
        <button class="button secondary full-button" id="reset-appearance">Restore Electric Neon defaults</button>
      </section>
      <section class="editor-section editor-tab-panel ${state.editorTab === "layout" ? "active" : ""}" data-editor-panel="layout">
        <div class="section-heading"><div><h3>Pages</h3><p>Separate services into focused dashboard views.</p></div><button class="button small" id="add-page">+ Page</button></div>
        <div class="page-editor-list" id="page-editor-list"></div>
        <label class="field"><span>Maximum dashboard columns</span><select id="edit-max-columns">${[1,2,3,4,5,6].map(value => `<option value="${value}" ${state.draft.meta.maxColumns === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
        <label class="toggle-row"><input id="edit-full" type="checkbox" ${state.draft.meta.fullWidth ? "checked" : ""}><span><strong>Full-width layout</strong><small>Use the available browser width.</small></span></label>
        <label class="toggle-row"><input id="edit-equal" type="checkbox" ${state.draft.meta.equalHeights ? "checked" : ""}><span><strong>Equal-height cards</strong><small>Keep groups visually tidy.</small></span></label>
        <label class="toggle-row"><input id="edit-latency" type="checkbox" ${state.draft.meta.showLatency ? "checked" : ""}><span><strong>Response-time badges</strong><small>Show the container or API latency on each card.</small></span></label>
        <div class="section-heading"><div><h3>Groups</h3><p>Rename, reorder and choose their columns.</p></div><button class="button small" id="add-group">+ Add</button></div>
        <div class="group-editor-list" id="group-editor-list"></div>
      </section>
      <section class="editor-section editor-tab-panel ${state.editorTab === "connect" ? "active" : ""}" data-editor-panel="connect">
        <div class="section-heading"><div><h3>Connection centre</h3><p>Private network, .env loading and API authentication.</p></div><button class="button tiny" id="refresh-monitor">↻ Test now</button></div>
        ${proxyDiagnosticsMarkup()}
        <div id="widget-diagnostics">${connectionDiagnosticsMarkup()}</div>
        <label class="compact-upload"><input id="editor-import" type="file" accept=".json,.zip,.yaml,.yml" multiple><span>⇧ Restore Rogue Dashboard JSON or import legacy ZIP/YAML</span></label>
        <button class="button secondary full-button" id="export-json">⇩ Export JSON backup</button>
      </section>
      <section class="editor-section editor-tab-panel ${state.editorTab === "docker" ? "active" : ""}" data-editor-panel="docker">
        <div class="notice info">Scan the restricted Docker agent to add cards or safely start, stop and restart containers.</div>
        <button class="button secondary full-button" id="discover-docker">▣ Scan Docker containers</button><div class="container-list" id="container-list"></div>
      </section>
    </div>
    <footer class="editor-footer"><button class="button ghost danger-text" id="logout">Sign out</button><button class="button primary" id="save-dashboard">Save changes</button></footer>
  </aside>`;
}

function openEditor() {
  state.editor = true;
  state.editorTab = "appearance";
  state.draft = structuredClone(state.dashboard);
  renderDashboard();
}

function bindEditor() {
  document.querySelectorAll("[data-editor-tab]").forEach(button => button.onclick = () => {
    state.editorTab = button.dataset.editorTab;
    document.querySelectorAll("[data-editor-tab]").forEach(entry => entry.classList.toggle("active", entry === button));
    document.querySelectorAll("[data-editor-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.editorPanel === state.editorTab));
  });
  document.getElementById("edit-theme").value = state.draft.meta.theme;
  document.getElementById("edit-density").value = state.draft.meta.density;
  document.getElementById("edit-background-mode").value = state.draft.meta.backgroundMode;
  document.getElementById("close-editor").onclick = () => { state.editor = false; state.draft = structuredClone(state.dashboard); renderDashboard(); };
  const fields = {
    "edit-title": "title", "edit-subtitle": "subtitle", "edit-background": "background",
    "edit-accent": "accent", "edit-accent-text": "accent",
    "edit-accent-secondary": "accentSecondary", "edit-accent-secondary-text": "accentSecondary",
  };
  Object.entries(fields).forEach(([id, key]) => document.getElementById(id).oninput = event => {
    state.draft.meta[key] = event.target.value;
    if (key === "title") document.querySelector(".brand-block h1").textContent = event.target.value || "My Docker Dashboard";
    if (key === "subtitle") document.querySelector(".brand-block p").textContent = event.target.value;
    if (key === "accent" && /^#[0-9a-fA-F]{6}$/.test(event.target.value)) {
      document.getElementById("shell").style.setProperty("--accent", event.target.value);
      document.getElementById(id === "edit-accent" ? "edit-accent-text" : "edit-accent").value = event.target.value;
    }
    if (key === "accentSecondary" && /^#[0-9a-fA-F]{6}$/.test(event.target.value)) {
      document.getElementById("shell").style.setProperty("--accent-secondary", event.target.value);
      document.getElementById(id === "edit-accent-secondary" ? "edit-accent-secondary-text" : "edit-accent-secondary").value = event.target.value;
    }
    if (key === "background") document.getElementById("dashboard-background").style.setProperty("--custom-background", `url("${event.target.value.replace(/["\\\n\r]/g, "")}")`);
  });
  document.getElementById("edit-theme").onchange = event => {
    const shell = document.getElementById("shell");
    shell.classList.replace(`theme-${state.draft.meta.theme}`, `theme-${event.target.value}`);
    state.draft.meta.theme = event.target.value;
    [state.draft.meta.accent, state.draft.meta.accentSecondary] = THEME_PRESETS[event.target.value];
    document.getElementById("edit-accent").value = state.draft.meta.accent;
    document.getElementById("edit-accent-text").value = state.draft.meta.accent;
    document.getElementById("edit-accent-secondary").value = state.draft.meta.accentSecondary;
    document.getElementById("edit-accent-secondary-text").value = state.draft.meta.accentSecondary;
    shell.style.setProperty("--accent", state.draft.meta.accent);
    shell.style.setProperty("--accent-secondary", state.draft.meta.accentSecondary);
  };
  document.getElementById("edit-density").onchange = event => {
    document.getElementById("shell").classList.replace(`density-${state.draft.meta.density}`, `density-${event.target.value}`);
    state.draft.meta.density = event.target.value;
  };
  document.getElementById("edit-background-mode").onchange = event => {
    document.getElementById("shell").classList.replace(`background-${state.draft.meta.backgroundMode}`, `background-${event.target.value}`);
    state.draft.meta.backgroundMode = event.target.value;
  };
  document.getElementById("edit-glow").oninput = event => {
    state.draft.meta.glow = Number(event.target.value); document.getElementById("glow-value").textContent = `${event.target.value}%`;
    document.getElementById("shell").style.setProperty("--glow-strength", Number(event.target.value) / 100);
    document.getElementById("shell").style.setProperty("--glow-opacity", Number(event.target.value) / 590);
    document.getElementById("shell").style.setProperty("--glow-blur", `${Math.round(Number(event.target.value) * .38)}px`);
  };
  document.getElementById("edit-opacity").oninput = event => {
    state.draft.meta.surfaceOpacity = Number(event.target.value); document.getElementById("opacity-value").textContent = `${event.target.value}%`;
    document.getElementById("shell").style.setProperty("--surface-opacity", `${event.target.value}%`);
  };
  document.getElementById("reset-appearance").onclick = () => {
    Object.assign(state.draft.meta, { theme: "neon", accent: "#ff2bd6", accentSecondary: "#00e5ff", background: "", backgroundMode: "neon-grid", density: "compact", glow: 68, surfaceOpacity: 82 });
    state.editorTab = "appearance"; renderDashboard(); toast("Electric Neon defaults restored in the preview");
  };
  document.getElementById("edit-max-columns").onchange = event => { state.draft.meta.maxColumns = Number(event.target.value); renderGroups(); };
  document.getElementById("edit-full").onchange = event => { state.draft.meta.fullWidth = event.target.checked; document.querySelector(".dashboard").classList.toggle("full-width", event.target.checked); };
  document.getElementById("edit-equal").onchange = event => { state.draft.meta.equalHeights = event.target.checked; renderGroups(); };
  document.getElementById("edit-latency").onchange = event => { state.draft.meta.showLatency = event.target.checked; renderGroups(); };
  document.getElementById("add-group").onclick = addGroup;
  document.getElementById("add-page").onclick = addPage;
  document.getElementById("save-dashboard").onclick = saveDashboard;
  document.getElementById("logout").onclick = logout;
  document.getElementById("discover-docker").onclick = discoverDocker;
  document.getElementById("editor-import").onchange = importInEditor;
  document.getElementById("export-json").onclick = exportJson;
  document.getElementById("refresh-monitor").onclick = () => refreshRuntime(true);
  renderGroupEditor();
  renderPageEditor();
}

function renderPageEditor() {
  const list = document.getElementById("page-editor-list");
  if (!list) return;
  list.innerHTML = state.draft.pages.map((page, index) => `<div class="page-editor-row"><input data-page-name="${index}" value="${escapeHtml(page.name)}" aria-label="Page name"><button class="icon-button danger" data-page-delete="${index}" title="Delete page" ${state.draft.pages.length === 1 ? "disabled" : ""}>×</button></div>`).join("");
  list.querySelectorAll("[data-page-name]").forEach(input => input.oninput = () => {
    state.draft.pages[Number(input.dataset.pageName)].name = input.value || "Page";
    const tab = [...document.querySelectorAll("[data-page]")][Number(input.dataset.pageName)];
    if (tab) tab.textContent = input.value || "Page";
  });
  list.querySelectorAll("[data-page-delete]").forEach(button => button.onclick = () => deletePage(Number(button.dataset.pageDelete)));
}

function addPage() {
  if (state.draft.pages.length >= 20) return toast("A dashboard can contain up to 20 pages");
  const name = `Page ${state.draft.pages.length + 1}`;
  const page = { id: uniqueId(name), name };
  state.draft.pages.push(page);
  state.activePage = page.id;
  state.editorTab = "layout";
  renderDashboard();
}

function deletePage(index) {
  const page = state.draft.pages[index];
  if (!page || state.draft.pages.length === 1) return;
  const groups = state.draft.groups.filter(group => group.pageId === page.id);
  const cards = groups.reduce((total, group) => total + group.items.length, 0);
  if (cards && !confirm(`Delete ${page.name} and its ${cards} cards?`)) return;
  state.draft.groups = state.draft.groups.filter(group => group.pageId !== page.id);
  state.draft.pages.splice(index, 1);
  state.activePage = state.draft.pages[Math.max(0, index - 1)].id;
  state.editorTab = "layout";
  renderDashboard();
}

function renderGroupEditor() {
  const list = document.getElementById("group-editor-list");
  if (!list) return;
  const visible = state.draft.groups.map((group, index) => ({ group, index })).filter(({ group }) => (group.pageId || state.draft.pages[0].id) === state.activePage);
  list.innerHTML = visible.map(({ group, index }, position) => `<div class="group-editor-row"><span>▦</span><div><input data-name="${index}" value="${escapeHtml(group.name)}"><span>${group.items.length} cards</span></div><select data-columns="${index}">${[1,2,3,4,5,6].map(value => `<option value="${value}" ${group.columns === value ? "selected" : ""}>${value} cols</option>`).join("")}</select><div class="group-order"><button class="icon-button" data-move-up="${index}" title="Move up" ${position === 0 ? "disabled" : ""}>↑</button><button class="icon-button" data-move-down="${index}" title="Move down" ${position === visible.length - 1 ? "disabled" : ""}>↓</button></div><button class="icon-button danger" data-delete="${index}">×</button></div>`).join("");
  list.querySelectorAll("[data-name]").forEach(input => input.oninput = () => { state.draft.groups[Number(input.dataset.name)].name = input.value; renderGroups(); });
  list.querySelectorAll("[data-columns]").forEach(select => select.onchange = () => { state.draft.groups[Number(select.dataset.columns)].columns = Number(select.value); renderGroups(); });
  list.querySelectorAll("[data-move-up]").forEach(button => button.onclick = () => moveGroup(Number(button.dataset.moveUp), -1));
  list.querySelectorAll("[data-move-down]").forEach(button => button.onclick = () => moveGroup(Number(button.dataset.moveDown), 1));
  list.querySelectorAll("[data-delete]").forEach(button => button.onclick = () => {
    const index = Number(button.dataset.delete), group = state.draft.groups[index];
    if (group.items.length && !confirm(`Delete ${group.name} and its ${group.items.length} cards?`)) return;
    state.draft.groups.splice(index, 1); renderGroupEditor(); renderGroups();
  });
}

function moveGroup(index, direction) {
  const visible = state.draft.groups.map((group, groupIndex) => ({ group, groupIndex })).filter(({ group }) => (group.pageId || state.draft.pages[0].id) === state.activePage);
  const position = visible.findIndex(entry => entry.groupIndex === index);
  const target = visible[position + direction]?.groupIndex;
  if (position < 0 || target === undefined) return;
  [state.draft.groups[index], state.draft.groups[target]] = [state.draft.groups[target], state.draft.groups[index]];
  renderGroupEditor(); renderGroups();
}

function uniqueId(name) {
  const used = new Set([...(state.draft.pages || []).map(page => page.id), ...state.draft.groups.flatMap(group => [group.id, ...group.items.map(item => item.id)])]);
  const base = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "item";
  let id = base, suffix = 2;
  while (used.has(id)) id = `${base}-${suffix++}`;
  return id;
}

function addGroup() {
  const name = `New group ${state.draft.groups.length + 1}`;
  state.draft.groups.push({ id: uniqueId(name), name, kind: "services", columns: 3, collapsed: false, pageId: state.activePage, items: [] });
  renderGroupEditor(); renderGroups();
}

async function saveDashboard() {
  const button = document.getElementById("save-dashboard");
  button.disabled = true; button.textContent = "Saving…";
  try {
    const result = await request("/api/dashboard", { method: "PUT", body: JSON.stringify(state.draft) });
    state.dashboard = result.dashboard; state.draft = structuredClone(result.dashboard);
    toast("Dashboard saved"); renderDashboard();
  } catch (error) {
    toast(error.message); button.disabled = false; button.textContent = "Save changes";
  }
}

async function importInEditor(event) {
  try {
    const result = await previewImport(event.target.files);
    if (!confirm(`Replace this preview with ${result.summary.services} services and ${result.summary.bookmarks} bookmarks?`)) return;
    state.draft = structuredClone(result.dashboard); toast("Import applied. Save when the preview looks right."); renderDashboard();
  } catch (error) { toast(error.message); }
}

async function discoverDocker() {
  const list = document.getElementById("container-list");
  list.innerHTML = `<div class="notice info">Scanning Docker…</div>`;
  try {
    const result = await request("/api/docker/containers");
    list.innerHTML = result.containers.map((container, index) => {
      const added = isContainerAdded(container);
      const publicPort = container.ports.find(port => port.publicPort)?.publicPort || "no public port";
      const networks = container.networks?.length ? container.networks.join(", ") : "no network data";
      const stats = container.stats?.available ? `CPU ${container.stats.cpuPercent.toFixed(1)}% · RAM ${formatBytes(container.stats.memoryUsed)} · ↓ ${formatBytes(container.stats.networkRx)} ↑ ${formatBytes(container.stats.networkTx)}` : container.state === "running" ? "Runtime metrics unavailable" : container.status;
      return `<div class="container-row"><span class="container-state ${container.state === "running" ? "online" : ""}"></span><div><strong>${escapeHtml(container.name)}</strong><span>${escapeHtml(container.image)} · ${publicPort}</span><span class="container-runtime">${escapeHtml(stats)}</span><span class="container-networks">Networks: ${escapeHtml(networks)}</span></div><div class="container-actions"><button class="icon-button ${added ? "is-added" : ""}" data-container="${index}" title="${added ? "Card already added" : "Add card"}" ${added ? "disabled" : ""}>${added ? "✓" : "+"}</button>${container.labels["rogue.dashboard.protected"] === "true" ? `<span class="protected-chip">Protected</span>` : container.state === "running" ? `<button class="icon-button" data-docker-action="restart" data-index="${index}" title="Restart">↻</button><button class="icon-button danger" data-docker-action="stop" data-index="${index}" title="Stop">■</button>` : `<button class="icon-button" data-docker-action="start" data-index="${index}" title="Start">▶</button>`}</div></div>`;
    }).join("") || `<div class="notice info">No containers found.</div>`;
    list.querySelectorAll("[data-container]").forEach(button => button.onclick = () => addContainer(result.containers[Number(button.dataset.container)]));
    list.querySelectorAll("[data-docker-action]").forEach(button => button.onclick = () => runDockerAction(result.containers[Number(button.dataset.index)], button.dataset.dockerAction));
  } catch (error) { list.innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`; }
}

function isContainerAdded(container) {
  const wanted = iconKey(container.name);
  return state.draft.groups.some(group => group.items.some(item =>
    item.containerName === container.name || (!item.containerName && iconKey(item.name) === wanted)
  ));
}

async function runDockerAction(container, action) {
  if (!confirm(`${action[0].toUpperCase() + action.slice(1)} ${container.name}?`)) return;
  try {
    await request("/api/docker/action", { method: "POST", body: JSON.stringify({ containerId: container.id, action }) });
    toast(`${container.name}: ${action} requested`);
    setTimeout(discoverDocker, 1200);
  } catch (error) { toast(error.message); }
}

function addContainer(container) {
  if (isContainerAdded(container)) {
    toast(`${container.name} already has a dashboard card`);
    return;
  }
  const identity = iconKey(container.name);
  const port = container.ports.find(entry => entry.publicPort) || container.ports[0];
  const publicRogueRouteUrl = state.bootstrap?.serviceUrls?.rogueRoute || "";
  const presets = {
    rogueroutegpx: { name: "RogueRoute GPX", href: publicRogueRouteUrl || (port?.publicPort ? `${location.protocol}//${location.hostname}:${port.publicPort}` : ""), monitorUrl: "http://rogueroute-gpx-web:9080/api/health", description: "Route generator", icon: "/icons/rogueroute-gpx.svg" },
    rogueroutegpxweb: { name: "RogueRoute GPX", href: publicRogueRouteUrl || (port?.publicPort ? `${location.protocol}//${location.hostname}:${port.publicPort}` : ""), monitorUrl: "http://rogueroute-gpx-web:9080/api/health", description: "Route generator", icon: "/icons/rogueroute-gpx.svg" },
    roguerouteosrm: { name: "RogueRoute OSRM", href: "", monitorUrl: "http://rogueroute-gpx-osrm:5000/", description: "Local route engine", icon: "/icons/rogueroute-osrm.svg" },
    rogueroutegpxosrm: { name: "RogueRoute OSRM", href: "", monitorUrl: "http://rogueroute-gpx-osrm:5000/", description: "Local route engine", icon: "/icons/rogueroute-osrm.svg" },
    rogueroutemanager: { name: "RogueRoute Manager", href: "", monitorUrl: "http://rogueroute-gpx-manager:9090/health", description: "Private region manager", icon: "/icons/rogueroute-manager.svg" },
    rogueroutegpxmanager: { name: "RogueRoute Manager", href: "", monitorUrl: "http://rogueroute-gpx-manager:9090/health", description: "Private region manager", icon: "/icons/rogueroute-manager.svg" },
  };
  const preset = presets[identity];
  let group = preset ? state.draft.groups.find(entry => entry.pageId === state.activePage && entry.kind === "services" && /gpx|rogueroute/i.test(entry.name)) : state.draft.groups.find(entry => entry.pageId === state.activePage && entry.kind === "services");
  if (!group) {
    group = { id: uniqueId(preset ? "rogueroute-gpx" : "services"), name: preset ? "RogueRoute GPX" : "Services", kind: "services", columns: 3, collapsed: false, pageId: state.activePage, items: [] };
    state.draft.groups.push(group);
  }
  const defaults = preset || { name: container.name, href: port?.publicPort ? `${location.protocol}//${location.hostname}:${port.publicPort}` : "", monitorUrl: port?.privatePort ? `http://${container.name}:${port.privatePort}` : "", description: container.image, icon: "" };
  group.items.push({ id: uniqueId(defaults.name), ...defaults, containerName: container.name, type: "service", statusStyle: "dot" });
  toast(`${container.name} added to ${group.name}`); renderGroupEditor(); renderGroups();
}

function exportJson() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.draft, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = "rogue-dashboard-backup.json"; link.click(); URL.revokeObjectURL(url);
}

function integrationHint(type) {
  const config = INTEGRATION_DEFAULTS[type];
  if (type === "qbittorrent") return "qBittorrent 5.2+: use RGDASH_QBITTORRENT_API_KEY. Username and password are the automatic fallback.";
  return config ? `Add ${config.refs.join(" and ")} to .env.` : "Health-check monitoring only; no API credentials required.";
}

function openItem(groupIndex, itemIndex) {
  state.editingItem = { groupIndex, itemIndex };
  const item = itemIndex === undefined ? { name: "", href: "", monitorUrl: "", description: "", icon: "", type: "service", statusStyle: "dot" } : state.draft.groups[groupIndex].items[itemIndex];
  overlay.innerHTML = `<div class="modal-backdrop"><section class="modal modal-wide"><header class="modal-header"><h2>${itemIndex === undefined ? "Add a card" : `Edit ${escapeHtml(item.name)}`}</h2><button class="icon-button" id="item-close">×</button></header><form class="modal-body" id="item-form"><div class="form-grid">
    <label class="field"><span>Name</span><input id="item-name" value="${escapeHtml(item.name)}" required autofocus></label>
    <label class="field"><span>Card type</span><select id="item-type"><option value="service">Service</option><option value="bookmark">Bookmark</option></select></label>
    <label class="field full"><span>Open URL</span><input id="item-href" value="${escapeHtml(item.href || "")}" placeholder="https://…"></label>
    <label class="field full"><span>Private health-check URL</span><input id="item-monitor" value="${escapeHtml(item.monitorUrl || "")}" placeholder="http://container:port"></label>
    <label class="field full"><span>Description</span><input id="item-description" value="${escapeHtml(item.description || "")}"></label>
    <label class="field"><span>Icon URL or local path</span><input id="item-icon" value="${escapeHtml(item.icon || "")}" placeholder="/custom/icons/my-service.svg"><small>Leave blank to use a bundled icon when recognised.</small></label>
    <label class="field"><span>Status</span><select id="item-status"><option value="dot">Dot</option><option value="badge">Badge</option><option value="none">Hidden</option></select></label>
    <label class="field"><span>Live integration</span><select id="item-integration"><option value="">Health check only</option>${Object.keys(INTEGRATION_DEFAULTS).map(type => `<option value="${type}">${type === "pihole" ? "Pi-hole" : type === "qbittorrent" ? "qBittorrent" : type[0].toUpperCase() + type.slice(1)}</option>`).join("")}</select></label>
    <label class="field"><span>Private API URL</span><input id="item-widget-url" value="${escapeHtml(item.widget?.url || item.monitorUrl || "")}" placeholder="http://container:port"></label>
    <div class="notice info full" id="integration-env">${escapeHtml(integrationHint(item.widget?.type || ""))}</div>
  </div><div class="button-row spread">${itemIndex === undefined ? "<span></span>" : `<button type="button" class="button ghost danger-text" id="item-delete">Delete</button>`}<button class="button primary">Save card</button></div></form></section></div>`;
  document.getElementById("item-type").value = item.type;
  document.getElementById("item-status").value = item.statusStyle;
  document.getElementById("item-integration").value = item.widget?.type || "";
  document.getElementById("item-integration").onchange = event => {
    document.getElementById("integration-env").textContent = integrationHint(event.target.value);
    if (event.target.value && !document.getElementById("item-widget-url").value) document.getElementById("item-widget-url").value = document.getElementById("item-monitor").value;
  };
  document.getElementById("item-close").onclick = closeOverlay;
  document.getElementById("item-form").onsubmit = saveItem;
  if (itemIndex !== undefined) document.getElementById("item-delete").onclick = deleteItem;
}

function saveItem(event) {
  event.preventDefault();
  const { groupIndex, itemIndex } = state.editingItem;
  const previous = itemIndex === undefined ? null : state.draft.groups[groupIndex].items[itemIndex];
  const item = { id: previous?.id || uniqueId(document.getElementById("item-name").value), name: document.getElementById("item-name").value, type: document.getElementById("item-type").value, href: document.getElementById("item-href").value, monitorUrl: document.getElementById("item-monitor").value, description: document.getElementById("item-description").value, icon: document.getElementById("item-icon").value, statusStyle: document.getElementById("item-status").value };
  if (previous?.containerName) item.containerName = previous.containerName;
  const integration = document.getElementById("item-integration").value;
  if (integration) {
    const defaults = INTEGRATION_DEFAULTS[integration];
    const previousWidget = previous?.widget?.type === integration ? previous.widget : {};
    item.widget = { ...previousWidget, type: integration, url: document.getElementById("item-widget-url").value || item.monitorUrl, secretRefs: defaults.refs, secretBindings: defaults.bindings };
    if (integration === "pihole") item.widget.version = 6;
  }
  if (itemIndex === undefined) state.draft.groups[groupIndex].items.push(item); else state.draft.groups[groupIndex].items[itemIndex] = item;
  closeOverlay(); renderGroupEditor(); renderGroups();
}

function deleteItem() {
  const { groupIndex, itemIndex } = state.editingItem;
  state.draft.groups[groupIndex].items.splice(itemIndex, 1); closeOverlay(); renderGroupEditor(); renderGroups();
}

function openLogin() {
  overlay.innerHTML = `<div class="modal-backdrop"><section class="modal"><header class="modal-header"><h2>Administrator sign in</h2><button class="icon-button" id="login-close">×</button></header><form class="modal-body" id="login-form"><p class="muted">Sign in to add, arrange and customise services.</p><label class="field"><span>Username</span><input id="login-user" value="admin" autocomplete="username" required autofocus></label><label class="field"><span>Password</span><input id="login-password" type="password" autocomplete="current-password" required></label><div class="notice error" id="login-error" hidden></div><button class="button primary full-button">Sign in</button></form></section></div>`;
  document.getElementById("login-close").onclick = closeOverlay;
  document.getElementById("login-form").onsubmit = login;
}

async function login(event) {
  event.preventDefault();
  try {
    await request("/api/auth/login", { method: "POST", body: JSON.stringify({ username: document.getElementById("login-user").value, password: document.getElementById("login-password").value }) });
    closeOverlay(); await load(); openEditor();
  } catch (error) { const box = document.getElementById("login-error"); box.textContent = error.message; box.hidden = false; }
}

async function logout() {
  await request("/api/auth/logout", { method: "POST", body: "{}" }); state.editor = false; closeOverlay(); await load();
}

function closeOverlay() { overlay.innerHTML = ""; state.editingItem = null; }

function updateClock() {
  const now = new Date();
  const clock = document.getElementById("clock"), date = document.getElementById("date");
  if (clock) clock.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (date) date.textContent = now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });
}

function updateStats() {
  if (!document.getElementById("container-count")) return;
  const online = [...state.health.values()].filter(item => item.state === "online").length;
  document.getElementById("online-count").textContent = state.health.size ? `${online}/${state.health.size}` : "—";
  if (!state.system) return;
  const containerCount = document.getElementById("container-count");
  const containerLabel = document.getElementById("container-label");
  containerCount.textContent = state.system.totalContainers == null ? "—" : `${state.system.runningContainers}/${state.system.totalContainers}`;
  containerCount.title = state.system.dockerStatus === "ok" ? "Running / total Docker containers" : "Docker agent unavailable; check DOCKER_GID and agent logs";
  containerLabel.textContent = state.system.dockerStatus === "ok" ? "Containers running" : "Docker agent offline";
  document.getElementById("memory-count").textContent = formatBytes(state.system.memoryUsed);
  document.getElementById("memory-total").textContent = `of ${formatBytes(state.system.memoryTotal)} memory`;
  document.getElementById("load-count").textContent = Number(state.system.load).toFixed(2);
  document.getElementById("uptime-count").textContent = `${state.system.cpuCount} CPU · ${formatUptime(state.system.uptimeSeconds)} up`;
}

async function refreshRuntime(force = false) {
  const refreshButton = document.getElementById("refresh-monitor");
  if (force) {
    if (refreshButton) { refreshButton.disabled = true; refreshButton.textContent = "Testing…"; }
    try { await request("/api/monitor/refresh", { method: "POST", body: "{}" }); }
    catch (error) { toast(error.message); }
  }
  const [health, system, widgets] = await Promise.allSettled([
    request("/api/health"), request("/api/system"), request("/api/widgets"),
  ]);
  if (health.status === "fulfilled") state.health = new Map(health.value.map(item => [item.itemId, item]));
  if (system.status === "fulfilled") state.system = system.value;
  if (widgets.status === "fulfilled") {
    state.widgets = new Map(widgets.value.widgets.map(item => [item.itemId, item]));
    state.widgetSupport = widgets.value.supported;
  }
  updateStats(); renderGroups();
  const diagnostics = document.getElementById("widget-diagnostics");
  if (diagnostics) diagnostics.innerHTML = connectionDiagnosticsMarkup();
  if (refreshButton) { refreshButton.disabled = false; refreshButton.textContent = "↻ Test now"; }
}

setInterval(updateClock, 1000);
setInterval(refreshRuntime, 30000);
load();
