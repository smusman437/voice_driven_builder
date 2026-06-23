const form = document.getElementById("generate-form");
const requirementInput = document.getElementById("requirement");
const useToolsInput = document.getElementById("use-agent-tools");
const submitBtn = document.getElementById("submit-btn");
const statusPanel = document.getElementById("status-panel");
const errorBox = document.getElementById("error-box");
const resultPanel = document.getElementById("result-panel");
const resultMeta = document.getElementById("result-meta");
const resultScript = document.getElementById("result-script");
const resultPlayer = document.getElementById("result-player");
const resultDownload = document.getElementById("result-download");
const healthBadge = document.getElementById("health-badge");
const audioLibrary = document.getElementById("audio-library");
const libraryEmpty = document.getElementById("library-empty");
const refreshLibraryBtn = document.getElementById("refresh-library");

let audioPhaseTimer = null;

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(unixSeconds) {
  return new Date(unixSeconds * 1000).toLocaleString();
}

/** Preload metadata so native controls show total duration (e.g. 0:00 / 0:41) before play. */
function prepareAudioPlayer(player, src) {
  player.preload = "metadata";
  player.src = src;
  player.load();
  return player;
}

function setStepState(step, state) {
  const el = statusPanel.querySelector(`[data-step="${step}"]`);
  if (!el) return;
  el.classList.remove("active", "done");
  if (state) el.classList.add(state);
}

function resetStatus() {
  clearTimeout(audioPhaseTimer);
  statusPanel.classList.add("hidden");
  setStepState("script", "");
  setStepState("audio", "");
}

function startProgress() {
  statusPanel.classList.remove("hidden");
  errorBox.classList.add("hidden");
  resultPanel.classList.add("hidden");
  setStepState("script", "active");
  setStepState("audio", "");
  audioPhaseTimer = setTimeout(() => {
    setStepState("script", "done");
    setStepState("audio", "active");
  }, 2000);
}

function finishProgress() {
  clearTimeout(audioPhaseTimer);
  setStepState("script", "done");
  setStepState("audio", "done");
}

function parseErrorDetail(payload) {
  if (!payload) return "Request failed.";
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join(" ");
  }
  return JSON.stringify(detail);
}

async function loadHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();
    healthBadge.textContent = `API ok · LLM: ${data.llm_provider}`;
    healthBadge.classList.add("ok");
    healthBadge.classList.remove("error");
  } catch {
    healthBadge.textContent = "API unreachable";
    healthBadge.classList.add("error");
    healthBadge.classList.remove("ok");
  }
}

function renderLibrary(items) {
  audioLibrary.innerHTML = "";
  if (!items.length) {
    libraryEmpty.classList.remove("hidden");
    return;
  }
  libraryEmpty.classList.add("hidden");

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "audio-item";

    const header = document.createElement("div");
    header.className = "audio-item-header";
    header.innerHTML = `
      <span class="audio-item-name">${item.filename}</span>
      <span class="audio-item-meta">${formatBytes(item.size_bytes)}</span>
    `;

    const meta = document.createElement("div");
    meta.className = "audio-item-meta";
    meta.style.marginBottom = "0.5rem";
    meta.textContent = formatDate(item.created_at);

    const player = prepareAudioPlayer(document.createElement("audio"), item.download_path);
    player.controls = true;

    const download = document.createElement("a");
    download.className = "btn-link";
    download.href = item.download_path;
    download.download = item.filename;
    download.textContent = "Download";

    li.append(header, meta, player, download);
    audioLibrary.appendChild(li);
  }
}

async function loadLibrary() {
  try {
    const res = await fetch("/v1/audio");
    if (!res.ok) throw new Error("Could not load audio list");
    const items = await res.json();
    renderLibrary(items);
  } catch (err) {
    libraryEmpty.textContent = err.message || "Failed to load audio list.";
    libraryEmpty.classList.remove("hidden");
  }
}

function showResult(data) {
  resultMeta.innerHTML = `
    <dt>LLM used</dt><dd>${data.llm_provider}</dd>
    <dt>Configured</dt><dd>${data.llm_provider_configured}</dd>
    <dt>Fallback</dt><dd>${data.llm_fallback_used ? "yes" : "no"}</dd>
    <dt>Agent tools</dt><dd>${data.used_tools ? "yes" : "no"}</dd>
    <dt>File</dt><dd>${data.audio_filename}</dd>
  `;
  resultScript.textContent = data.script;
  prepareAudioPlayer(resultPlayer, data.download_path);
  resultDownload.href = data.download_path;
  resultDownload.download = data.audio_filename;
  resultPanel.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const requirement = requirementInput.value.trim();
  if (requirement.length < 3) return;

  submitBtn.disabled = true;
  startProgress();

  try {
    const body = { requirement };
    if (useToolsInput.checked) {
      body.use_agent_tools = true;
    } else {
      body.use_agent_tools = false;
    }

    const res = await fetch("/v1/requirements-to-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(parseErrorDetail(payload));
    }

    finishProgress();
    showResult(payload);
    await loadLibrary();
  } catch (err) {
    resetStatus();
    errorBox.textContent = err.message || "Something went wrong.";
    errorBox.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
  }
});

refreshLibraryBtn.addEventListener("click", loadLibrary);

loadHealth();
loadLibrary();
