const recordButton = document.getElementById("recordButton");
const fileInput = document.getElementById("fileInput");
const statusEl = document.getElementById("status");
const resultText = document.getElementById("resultText");
const copyButton = document.getElementById("copyButton");
const exportTxtButton = document.getElementById("exportTxtButton");
const exportJsonButton = document.getElementById("exportJsonButton");

let mediaRecorder = null;
let chunks = [];
let currentResult = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#b91c1c" : "";
}

function setResult(result) {
  currentResult = result;
  resultText.value = result?.text || "";
  const enabled = Boolean(result);
  copyButton.disabled = !enabled;
  exportTxtButton.disabled = !enabled;
  exportJsonButton.disabled = !enabled;
}

async function transcribeFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  setStatus("Идёт обработка аудио и транскрибация...");
  setResult(null);

  try {
    const response = await fetch("/api/transcribe", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось транскрибировать аудио.");
    }

    setResult(data);
    setStatus("Готово. Текст успешно получен.");
  } catch (error) {
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
