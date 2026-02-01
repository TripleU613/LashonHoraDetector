(() => {
  const STORAGE_KEY = "lh_terms";
  const DEFAULT_TERMS = ["sucks", "bad company", "they are a scam"];

  const termsEl = document.getElementById("terms");
  const fileEl = document.getElementById("file");
  const saveBtn = document.getElementById("save");
  const clearBtn = document.getElementById("clear");
  const statusEl = document.getElementById("status");

  function normalizeLines(text) {
    return text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  }

  function normalizeList(list) {
    return list
      .map((item) => String(item).trim())
      .filter((item) => item.length > 0);
  }

  function parseDelimited(text) {
    const trimmed = text.trim();
    if (!trimmed) return [];
    if (trimmed.includes("\n")) return normalizeLines(trimmed);
    if (trimmed.includes(",") || trimmed.includes(";")) {
      return trimmed
        .split(/[;,]/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
    }
    return [trimmed];
  }

  function parseJson(text) {
    const data = JSON.parse(text);
    if (Array.isArray(data)) return normalizeList(data);
    if (data && typeof data === "object") {
      if (Array.isArray(data.terms)) return normalizeList(data.terms);
      if (Array.isArray(data.list)) return normalizeList(data.list);
      const keys = Object.keys(data).filter((key) => data[key]);
      if (keys.length > 0) return normalizeList(keys);
    }
    return [];
  }

  function parseXml(text) {
    const parser = new DOMParser();
    const xml = parser.parseFromString(text, "application/xml");
    if (xml.querySelector("parsererror")) return [];
    const tags = ["term", "phrase", "item", "word"];
    const collected = [];
    tags.forEach((tag) => {
      xml.querySelectorAll(tag).forEach((node) => {
        if (node.textContent) collected.push(node.textContent.trim());
      });
    });
    return normalizeList(collected);
  }

  function smartParse(text, filename = "") {
    const lower = filename.toLowerCase();
    if (lower.endsWith(".json")) {
      try {
        return parseJson(text);
      } catch (err) {
        return parseDelimited(text);
      }
    }
    if (lower.endsWith(".xml")) {
      const xmlList = parseXml(text);
      if (xmlList.length > 0) return xmlList;
      return parseDelimited(text);
    }

    try {
      const jsonList = parseJson(text);
      if (jsonList.length > 0) return jsonList;
    } catch (err) {
      // ignore
    }

    const xmlList = parseXml(text);
    if (xmlList.length > 0) return xmlList;

    return parseDelimited(text);
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

  function saveTerms(list, note = "Saved") {
    chrome.storage.local.set({ [STORAGE_KEY]: list }, () => {
      setStatus(note);
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

  clearBtn.addEventListener("click", () => {
    renderTerms([]);
    saveTerms([], "Cleared");
  });

  fileEl.addEventListener("change", () => {
    const file = fileEl.files && fileEl.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      const list = smartParse(text, file.name);
      renderTerms(list);
      saveTerms(list, `Imported ${list.length}`);
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
