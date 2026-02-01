(() => {
  const STORAGE_KEY = "lh_terms";
  const DEFAULT_TERMS = ["sucks", "bad company", "they are a scam"];

  const termsEl = document.getElementById("terms");
  const fileEl = document.getElementById("file");
  const saveBtn = document.getElementById("save");
  const statusEl = document.getElementById("status");

  function normalizeLines(text) {
    return text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  }

  function setStatus(message) {
    statusEl.textContent = message;
    if (!message) return;
    window.clearTimeout(setStatus._timer);
    setStatus._timer = window.setTimeout(() => {
      statusEl.textContent = "";
    }, 2200);
  }

  function renderTerms(list) {
    termsEl.value = list.join("\n");
  }

  function saveTerms(list) {
    chrome.storage.local.set({ [STORAGE_KEY]: list }, () => {
      setStatus("Saved");
    });
  }

  function loadTerms() {
    chrome.storage.local.get({ [STORAGE_KEY]: DEFAULT_TERMS }, (result) => {
      const list = Array.isArray(result[STORAGE_KEY])
        ? result[STORAGE_KEY]
        : DEFAULT_TERMS;
      renderTerms(list);
    });
  }

  saveBtn.addEventListener("click", () => {
    const list = normalizeLines(termsEl.value);
    saveTerms(list);
  });

  fileEl.addEventListener("change", () => {
    const file = fileEl.files && fileEl.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      const list = normalizeLines(text);
      renderTerms(list);
      saveTerms(list);
      fileEl.value = "";
    };
    reader.onerror = () => {
      setStatus("Failed to read file");
      fileEl.value = "";
    };
    reader.readAsText(file);
  });

  loadTerms();
})();
