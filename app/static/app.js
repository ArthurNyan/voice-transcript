const recordButton = document.getElementById("recordButton");
const fileInput = document.getElementById("fileInput");
const statusEl = document.getElementById("status");
const resultText = document.getElementById("resultText");
const copyButton = document.getElementById("copyButton");
const exportTxtButton = document.getElementById("exportTxtButton");
const exportJsonButton = document.getElementById("exportJsonButton");
const resetJobButton = document.getElementById("resetJobButton");
const clearJobsButton = document.getElementById("clearJobsButton");
const progressPanel = document.getElementById("progressPanel");
const progressBar = document.getElementById("progressBar");
const progressLabel = document.getElementById("progressLabel");
const progressValue = document.getElementById("progressValue");
const jobsList = document.getElementById("jobsList");

let mediaRecorder = null;
let chunks = [];
let currentResult = null;
let activeJobId = localStorage.getItem("activeJobId");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#b91c1c" : "";
}

function setBusyState(isBusy) {
  recordButton.disabled = isBusy;
  fileInput.disabled = isBusy;
}

function persistActiveJobId(jobId) {
  activeJobId = jobId;
  if (jobId) {
    localStorage.setItem("activeJobId", jobId);
  } else {
    localStorage.removeItem("activeJobId");
  }
}

function setResult(result) {
  currentResult = result;
  resultText.value = result?.text || "";
  const enabled = Boolean(result);
  copyButton.disabled = !enabled;
  exportTxtButton.disabled = !enabled;
  exportJsonButton.disabled = !enabled;
}

function setProgress(progress, step) {
  progressPanel.classList.remove("hidden");
  progressBar.style.width = `${Math.round(progress * 100)}%`;
  progressValue.textContent = `${Math.round(progress * 100)}%`;
  progressLabel.textContent = step;
}

function resetProgress() {
  progressBar.style.width = "0%";
  progressValue.textContent = "0%";
  progressLabel.textContent = "Ожидание";
  progressPanel.classList.add("hidden");
}

function resetUiState() {
  persistActiveJobId(null);
  setBusyState(false);
  setResult(null);
  resetProgress();
  setStatus("Готово к записи или загрузке файла.");
}

function describeStep(step) {
  if (step === "preparing") return "Подготовка аудио";
  if (step === "splitting") return "Разбиение на части";
  if (step === "transcribing") return "Транскрибация";
  if (step === "assembling") return "Сборка результата";
  if (step === "done") return "Готово";
  if (step === "failed") return "Ошибка";
  return "Ожидание";
}

async function pollJob(jobId) {
  persistActiveJobId(jobId);
  while (activeJobId === jobId) {
    const response = await fetch(`/api/jobs/${jobId}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Не удалось получить статус задачи.");
    }

    setProgress(data.progress || 0, describeStep(data.current_step));

    if (data.status === "done") {
      const result = data.result || await fetchJobResult(jobId);
      setResult(result);
      setStatus("Готово. Текст успешно получен.");
      setBusyState(false);
      await loadJobs();
      return;
    }

    if (data.status === "failed") {
      setBusyState(false);
      await loadJobs();
      throw new Error(data.error || "Транскрибация завершилась с ошибкой.");
    }

    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

async function fetchJobResult(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/result`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось получить результат задачи.");
  }
  return data;
}

async function transcribeFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  setStatus("Создаю задачу на обработку аудио...");
  setResult(null);
  setBusyState(true);
  resetProgress();

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось транскрибировать аудио.");
    }

    setStatus("Задача создана. Идёт обработка...");
    await loadJobs();
    await pollJob(data.job_id);
  } catch (error) {
    setBusyState(false);
    setStatus(error.message, true);
  }
}

function renderJobs(jobs) {
  if (!jobs.length) {
    jobsList.innerHTML = '<p class="status">Список задач пока пуст.</p>';
    return;
  }

  jobsList.innerHTML = jobs
    .map((job) => {
      const percent = Math.round((job.progress || 0) * 100);
      return `
        <div class="job-item">
          <div class="job-meta">
            <strong>${job.filename}</strong>
            <span class="status">${describeStep(job.current_step)} · ${percent}%</span>
            <span class="status">Статус: ${job.status}</span>
          </div>
          <div class="job-actions">
            <button type="button" class="secondary" data-action="open-job" data-job-id="${job.job_id}">Открыть</button>
            <button type="button" class="secondary" data-action="delete-job" data-job-id="${job.job_id}">Удалить</button>
          </div>
        </div>
      `;
    })
    .join("");
}

async function loadJobs() {
  const response = await fetch("/api/jobs");
  const jobs = await response.json();
  if (!response.ok) {
    throw new Error("Не удалось загрузить список задач.");
  }
  renderJobs(jobs);
}

async function restoreActiveJob() {
  if (!activeJobId) {
    await loadJobs();
    return;
  }

  setBusyState(true);
  setStatus("Восстанавливаю активную задачу...");

  try {
    await loadJobs();
    await pollJob(activeJobId);
  } catch (error) {
    persistActiveJobId(null);
    setBusyState(false);
    setStatus(error.message, true);
  }
}

recordButton.addEventListener("click", async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    recordButton.textContent = "Начать запись";
    setStatus("Запись остановлена. Загружаю аудио...");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => chunks.push(event.data);
    mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
      const extension = blob.type.includes("mp4") ? "m4a" : "webm";
      const file = new File([blob], `recording.${extension}`, { type: blob.type });
      stream.getTracks().forEach((track) => track.stop());
      await transcribeFile(file);
    };
    mediaRecorder.start();
    recordButton.textContent = "Остановить запись";
    setStatus("Идёт запись. Нажмите ещё раз, чтобы остановить.");
  } catch (error) {
    setStatus("Не удалось получить доступ к микрофону.", true);
  }
});

fileInput.addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (file) {
    await transcribeFile(file);
    event.target.value = "";
  }
});

copyButton.addEventListener("click", async () => {
  if (!currentResult) {
    return;
  }

  await navigator.clipboard.writeText(currentResult.text);
  setStatus("Текст скопирован в буфер обмена.");
});

async function exportResult(endpoint, filename) {
  if (!currentResult) {
    return;
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result: currentResult }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setStatus(payload.detail || "Не удалось экспортировать результат.", true);
    return;
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

exportTxtButton.addEventListener("click", () => exportResult("/api/export/txt", "transcript.txt"));
exportJsonButton.addEventListener("click", () => exportResult("/api/export/json", "transcript.json"));

resetJobButton.addEventListener("click", async () => {
  if (!activeJobId) {
    resetUiState();
    await loadJobs();
    return;
  }

  await fetch(`/api/jobs/${activeJobId}`, { method: "DELETE" });
  resetUiState();
  await loadJobs();
});

clearJobsButton.addEventListener("click", async () => {
  await fetch("/api/jobs", { method: "DELETE" });
  resetUiState();
  await loadJobs();
});

jobsList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const jobId = button.dataset.jobId;
  const action = button.dataset.action;
  if (!jobId) {
    return;
  }

  if (action === "open-job") {
    const response = await fetch(`/api/jobs/${jobId}`);
    const data = await response.json();
    if (!response.ok) {
      setStatus(data.detail || "Не удалось открыть задачу.", true);
      return;
    }

    persistActiveJobId(jobId);
    setProgress(data.progress || 0, describeStep(data.current_step));
    if (data.result) {
      setResult(data.result);
      setStatus("Результат задачи загружен.");
      setBusyState(false);
    } else if (data.status === "processing" || data.status === "queued") {
      setBusyState(true);
      setStatus("Возобновляю отслеживание задачи...");
      await pollJob(jobId);
    } else if (data.status === "failed") {
      setStatus(data.error || "Задача завершилась с ошибкой.", true);
      setBusyState(false);
    }
  }

  if (action === "delete-job") {
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    if (activeJobId === jobId) {
      resetUiState();
    }
    await loadJobs();
  }
});

restoreActiveJob();
