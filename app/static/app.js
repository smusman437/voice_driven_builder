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

let phaseTimers = [];

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(unixSeconds) {
  return new Date(unixSeconds * 1000).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function friendlyAudioTitle(filename, index, total) {
  return `Recording ${total - index}`;
}

/** Preload metadata so native controls show total duration before play. */
function prepareAudioPlayer(player, src) {
  player.preload = "metadata";
  player.src = src;
  player.load();
  return player;
}

function clearPhaseTimers() {
  phaseTimers.forEach(clearTimeout);
  phaseTimers = [];
}

function setStepState(step, state) {
  const el = statusPanel.querySelector(`[data-step="${step}"]`);
  if (!el) return;
  el.classList.remove("active", "done");
  if (state) el.classList.add(state);
}

function resetStatus() {
  clearPhaseTimers();
  statusPanel.classList.add("hidden");
  for (const step of ["understand", "script", "audio"]) {
    setStepState(step, "");
  }
}

function startProgress() {
  statusPanel.classList.remove("hidden");
  errorBox.classList.add("hidden");
  resultPanel.classList.add("hidden");

  setStepState("understand", "active");
  setStepState("script", "");
  setStepState("audio", "");

  phaseTimers.push(
    setTimeout(() => {
      setStepState("understand", "done");
      setStepState("script", "active");
    }, 1200)
  );
  phaseTimers.push(
    setTimeout(() => {
      setStepState("script", "done");
      setStepState("audio", "active");
    }, 3500)
  );
}

function finishProgress() {
  clearPhaseTimers();
  setStepState("understand", "done");
  setStepState("script", "done");
  setStepState("audio", "done");
}

function parseErrorDetail(payload) {
  if (!payload) return "Something went wrong. Please try again.";
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
    healthBadge.textContent = `Ready · AI + ElevenLabs · ${data.llm_provider}`;
    healthBadge.classList.add("ok");
    healthBadge.classList.remove("error");
  } catch {
    healthBadge.textContent = "Agent offline";
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

  items.forEach((item, index) => {
    const li = document.createElement("li");
    li.className = "audio-item";

    const header = document.createElement("div");
    header.className = "audio-item-header";
    header.innerHTML = `
      <span class="audio-item-title">${friendlyAudioTitle(item.filename, index, items.length)}</span>
      <span class="audio-item-meta">${formatBytes(item.size_bytes)}</span>
    `;

    const date = document.createElement("div");
    date.className = "audio-item-date";
    date.textContent = formatDate(item.created_at);

    const player = prepareAudioPlayer(document.createElement("audio"), item.download_path);
    player.controls = true;

    const download = document.createElement("a");
    download.className = "btn-download";
    download.href = item.download_path;
    download.download = item.filename;
    download.textContent = "Download MP3";

    li.append(header, date, player, download);
    audioLibrary.appendChild(li);
  });
}

async function loadLibrary() {
  try {
    const res = await fetch("/v1/audio");
    if (!res.ok) throw new Error("Could not load your audio files.");
    renderLibrary(await res.json());
  } catch (err) {
    libraryEmpty.textContent = err.message || "Failed to load audio files.";
    libraryEmpty.classList.remove("hidden");
  }
}

function showResult(data) {
  resultScript.textContent = data.script;
  resultMeta.innerHTML = `
    <dt>Voice engine</dt><dd>ElevenLabs</dd>
    <dt>AI provider</dt><dd>${data.llm_provider}</dd>
    <dt>File</dt><dd>${data.audio_filename}</dd>
  `;
  prepareAudioPlayer(resultPlayer, data.download_path);
  resultDownload.href = data.download_path;
  resultDownload.download = data.audio_filename;
  resultPanel.classList.remove("hidden");
  resultPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const requirement = requirementInput.value.trim();
  if (requirement.length < 3) return;

  submitBtn.disabled = true;
  submitBtn.querySelector(".btn-label").textContent = "Converting…";
  startProgress();

  try {
    const res = await fetch("/v1/requirements-to-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requirement,
        use_agent_tools: useToolsInput.checked,
      }),
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
    errorBox.textContent = err.message || "Conversion failed. Please try again.";
    errorBox.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector(".btn-label").textContent = "Convert to audio";
  }
});

refreshLibraryBtn.addEventListener("click", loadLibrary);

loadHealth();
loadLibrary();
