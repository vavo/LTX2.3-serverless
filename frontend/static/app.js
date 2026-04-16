const state = {
  aspectRatio: "16:9",
  fps: 24,
  file: null,
  filePreviewUrl: "",
  payload: null,
  payloadJson: "",
  runMode: "worker",
  submissionMode: "endpoint",
};

const ratioDimensions = {
  "16:9": { width: 1280, height: 720 },
  "9:16": { width: 720, height: 1280 },
  "1:1": { width: 1024, height: 1024 },
};

const form = document.querySelector("#payload-form");
const promptField = document.querySelector("#prompt");
const optimizeField = document.querySelector("#optimize-prompt");
const secondsField = document.querySelector("#seconds");
const secondsValue = document.querySelector("#seconds-value");
const framesValue = document.querySelector("#frames-value");
const fpsValue = document.querySelector("#fps-value");
const resolutionValue = document.querySelector("#resolution-value");
const charCount = document.querySelector("#char-count");
const feedback = document.querySelector("#feedback");
const uploadPanel = document.querySelector("#upload-panel");
const uploadIcon = document.querySelector("#upload-icon");
const uploadTitle = document.querySelector("#upload-title");
const uploadCopy = document.querySelector("#upload-copy");
const sourceImageInput = document.querySelector("#source-image");
const filePill = document.querySelector("#file-pill");
const fileName = document.querySelector("#file-name");
const imagePreviewCard = document.querySelector("#image-preview-card");
const imagePreview = document.querySelector("#image-preview");
const previewName = document.querySelector("#preview-name");
const payloadPanel = document.querySelector("#payload-panel");
const payloadOutput = document.querySelector("#payload-output");
const payloadSummary = document.querySelector("#payload-summary");
const generateButton = document.querySelector("#generate-button");
const submitButton = document.querySelector("#submit-button");
const copyButton = document.querySelector("#copy-button");
const downloadButton = document.querySelector("#download-button");
const endpointPanel = document.querySelector("#endpoint-panel");
const endpointUrlField = document.querySelector("#endpoint-url");
const authTokenField = document.querySelector("#auth-token");
const submitModeTitle = document.querySelector("#submit-mode-title");
const submitModeCopy = document.querySelector("#submit-mode-copy");
const helperCopy = document.querySelector("#helper-copy");
const responsePanel = document.querySelector("#response-panel");
const responseSummary = document.querySelector("#response-summary");
const responseOutput = document.querySelector("#response-output");
const aspectButtons = document.querySelectorAll("[data-aspect-ratio]");

function secondsToFrames(seconds) {
  return Math.round(seconds * state.fps) + 1;
}

function setFeedback(message, type = "") {
  feedback.textContent = message;
  feedback.className = type ? `feedback ${type}` : "feedback";
}

function updatePromptCounter() {
  charCount.textContent = String(promptField.value.length);
}

function updateDurationSummary() {
  const seconds = Number.parseFloat(secondsField.value);
  const dimensions = ratioDimensions[state.aspectRatio];
  secondsValue.textContent = seconds.toFixed(1);
  framesValue.textContent = String(secondsToFrames(seconds));
  fpsValue.textContent = String(state.fps);
  resolutionValue.textContent = `${dimensions.width} × ${dimensions.height}`;
}

function updateAspectButtons() {
  aspectButtons.forEach((button) => {
    const isActive = button.dataset.aspectRatio === state.aspectRatio;
    button.classList.toggle("aspect-button-active", isActive);
    button.setAttribute("aria-checked", String(isActive));
  });
}

function updateSubmitModeUi() {
  if (state.submissionMode === "pod") {
    endpointPanel.hidden = true;
    endpointUrlField.disabled = true;
    authTokenField.disabled = true;
    generateButton.hidden = true;
    generateButton.disabled = true;
    generateButton.type = "button";
    payloadPanel.hidden = true;
    helperCopy.hidden = true;
    submitButton.textContent = "Generate Video";
    submitButton.classList.remove("secondary-hero-action");
    submitButton.classList.add("primary-action");
    return;
  }

  endpointPanel.hidden = false;
  endpointUrlField.disabled = false;
  authTokenField.disabled = false;
  generateButton.hidden = false;
  generateButton.disabled = false;
  generateButton.type = "submit";
  helperCopy.hidden = false;
  submitModeTitle.textContent = "Real endpoint";
  submitModeCopy.innerHTML =
    'Full POST URL, for example <code>https://api.runpod.ai/v2/&lt;endpoint_id&gt;/runsync</code>';
  submitButton.textContent = "Submit to Endpoint";
  submitButton.classList.remove("primary-action");
  submitButton.classList.add("secondary-hero-action");
}

function setFile(file) {
  if (state.filePreviewUrl) {
    URL.revokeObjectURL(state.filePreviewUrl);
    state.filePreviewUrl = "";
  }

  state.file = file;
  if (!file) {
    filePill.hidden = true;
    fileName.textContent = "";
    imagePreviewCard.hidden = true;
    imagePreview.removeAttribute("src");
    previewName.textContent = "";
    uploadIcon.hidden = false;
    uploadTitle.hidden = false;
    uploadCopy.hidden = false;
    uploadPanel.classList.remove("has-preview");
    return;
  }

  fileName.textContent = file.name;
  state.filePreviewUrl = URL.createObjectURL(file);
  imagePreview.src = state.filePreviewUrl;
  previewName.textContent = file.name;
  imagePreviewCard.hidden = false;
  uploadIcon.hidden = true;
  uploadTitle.hidden = true;
  uploadCopy.hidden = true;
  uploadPanel.classList.add("has-preview");
  filePill.hidden = true;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Failed to read the source image."));
    reader.readAsDataURL(file);
  });
}

function renderSummary(summary) {
  const chips = [
    `${summary.frames} frames`,
    `${summary.seconds.toFixed(1)}s`,
    `${summary.width} × ${summary.height}`,
    `${summary.aspect_ratio}`,
    `${summary.fps} fps`,
    summary.optimize_prompt ? "AI prompt on" : "AI prompt off",
  ];

  payloadSummary.innerHTML = "";
  chips.forEach((text) => {
    const chip = document.createElement("span");
    chip.className = "payload-summary-chip";
    chip.textContent = text;
    payloadSummary.appendChild(chip);
  });
}

async function copyPayload() {
  if (!state.payloadJson) {
    return;
  }

  await navigator.clipboard.writeText(state.payloadJson);
  setFeedback("Payload copied.", "success");
}

function downloadPayload() {
  if (!state.payloadJson) {
    return;
  }

  const blob = new Blob([state.payloadJson], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ltx-payload.json";
  link.click();
  URL.revokeObjectURL(url);
}

function renderResponse(result) {
  const chips = [
    result.ok ? `HTTP ${result.status_code} ok` : `HTTP ${result.status_code}`,
    result.content_type,
    result.endpoint_url || "local ComfyUI",
  ];

  responseSummary.innerHTML = "";
  chips.forEach((text) => {
    const chip = document.createElement("span");
    chip.className = "payload-summary-chip";
    chip.textContent = text;
    responseSummary.appendChild(chip);
  });

  responseOutput.textContent = result.response_json
    ? JSON.stringify(result.response_json, null, 2)
    : (result.response_text || "");
  responsePanel.hidden = false;
}

async function initializeConfig() {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw new Error("Failed to load app configuration.");
  }

  const config = await response.json();
  state.fps = config.fps;
  state.runMode = config.run_mode || "worker";
  state.submissionMode = config.submission_mode || "endpoint";
  secondsField.min = String(config.seconds.min);
  secondsField.max = String(config.seconds.max);
  secondsField.step = String(config.seconds.step);
  secondsField.value = String(config.seconds.default);
  updateSubmitModeUi();
  updateDurationSummary();
}

async function buildPayload({ scroll = true, successMessage = "Payload ready." } = {}) {
  if (!promptField.value.trim()) {
    setFeedback("Prompt is required.", "error");
    promptField.focus();
    return null;
  }

  if (!state.file) {
    setFeedback("Source image is required for the current workflow.", "error");
    return null;
  }

  const imageDataUrl = await readFileAsDataUrl(state.file);
  const response = await fetch("/api/payload", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt: promptField.value,
      seconds: Number.parseFloat(secondsField.value),
      aspect_ratio: state.aspectRatio,
      image_name: state.file.name,
      image_data_url: imageDataUrl,
      optimize_prompt: optimizeField.checked,
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Failed to generate payload.");
  }

  state.payload = data.payload;
  state.payloadJson = JSON.stringify(data.payload, null, 2);
  payloadOutput.textContent = state.payloadJson;
  renderSummary(data.summary);
  payloadPanel.hidden = state.submissionMode === "pod";
  if (scroll && state.submissionMode !== "pod") {
    payloadPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  if (successMessage) {
    setFeedback(successMessage, "success");
  }
  return data.payload;
}

aspectButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.aspectRatio = button.dataset.aspectRatio;
    updateAspectButtons();
    updateDurationSummary();
  });
});

promptField.addEventListener("input", updatePromptCounter);
secondsField.addEventListener("input", updateDurationSummary);
copyButton.addEventListener("click", copyPayload);
downloadButton.addEventListener("click", downloadPayload);

uploadPanel.addEventListener("click", () => sourceImageInput.click());
uploadPanel.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    sourceImageInput.click();
  }
});

sourceImageInput.addEventListener("change", (event) => {
  const [file] = event.target.files;
  setFile(file || null);
});

["dragenter", "dragover"].forEach((eventName) => {
  uploadPanel.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadPanel.classList.add("drag-active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  uploadPanel.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadPanel.classList.remove("drag-active");
  });
});

uploadPanel.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer.files;
  if (file && file.type.startsWith("image/")) {
    setFile(file);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.submissionMode === "pod") {
    submitButton.click();
    return;
  }

  setFeedback("");

  generateButton.disabled = true;
  generateButton.textContent = "Generating...";

  try {
    await buildPayload();
  } catch (error) {
    setFeedback(error.message, "error");
  } finally {
    generateButton.disabled = false;
    generateButton.textContent = "Generate Payload";
  }
});

submitButton.addEventListener("click", async () => {
  setFeedback("");

  let endpointUrl = "";
  if (state.submissionMode === "endpoint") {
    endpointUrl = endpointUrlField.value.trim();
  }

  if (state.submissionMode === "endpoint" && !endpointUrl) {
    setFeedback("Endpoint URL is required before submit.", "error");
    endpointUrlField.focus();
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = state.submissionMode === "pod" ? "Running..." : "Submitting...";

  try {
    const payload = await buildPayload({
      scroll: false,
      successMessage:
        state.submissionMode === "pod"
          ? ""
          : "Payload refreshed for submit.",
    });
    if (!payload) {
      return;
    }

    const response = await fetch(
      state.submissionMode === "pod" ? "/api/pod-submit" : "/api/submit",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          payload,
          ...(state.submissionMode === "endpoint"
            ? {
                endpoint_url: endpointUrl,
                auth_token: authTokenField.value,
              }
            : {}),
        }),
      }
    );

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || "Submit failed.");
    }

    renderResponse(result);
    responsePanel.scrollIntoView({ behavior: "smooth", block: "start" });
    setFeedback(
      result.ok
        ? state.submissionMode === "pod"
          ? "Local pod run finished successfully."
          : `Submitted successfully. Endpoint returned HTTP ${result.status_code}.`
        : state.submissionMode === "pod"
          ? `Local pod run returned HTTP ${result.status_code}.`
          : `Submitted. Endpoint returned HTTP ${result.status_code}.`,
      result.ok ? "success" : "error"
    );
  } catch (error) {
    setFeedback(error.message, "error");
  } finally {
    submitButton.disabled = false;
    updateSubmitModeUi();
  }
});

updatePromptCounter();
updateAspectButtons();
initializeConfig().catch((error) => {
  setFeedback(error.message, "error");
});
