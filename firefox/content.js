(() => {
  const STORAGE_KEY = "lh_terms";
  const DEFAULT_TERMS = ["sucks", "bad company", "they are a scam"];
  const ARTICLE_SELECTOR = "article[data-post-id], article[id^='post_']";
  const POST_SELECTOR = `.topic-post, ${ARTICLE_SELECTOR}`;
  const STYLE_ID = "lh-blocker-style";

  let terms = DEFAULT_TERMS.slice();

  function normalizeTerms(list) {
    if (!Array.isArray(list)) return [];
    return list
      .map((item) => String(item).trim())
      .filter((item) => item.length > 0);
  }

  function loadTerms() {
    chrome.storage.local.get({ [STORAGE_KEY]: DEFAULT_TERMS }, (result) => {
      terms = normalizeTerms(result[STORAGE_KEY]);
      scanAll();
    });
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
.lh-blocked {
  position: relative !important;
  overflow: hidden;
  border-radius: 12px;
}
.lh-blocked > *:not(.lh-mask) {
  filter: blur(6px);
  pointer-events: none;
}
.lh-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  color: #ffffff;
  font-family: Arial, sans-serif;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  z-index: 9999;
  pointer-events: none;
}
`;
    document.head.appendChild(style);
  }

  function getContainer(el) {
    if (!el || !(el instanceof HTMLElement)) return null;
    if (el.classList.contains("topic-post")) return el;
    const topicPost = el.closest(".topic-post");
    if (topicPost) return topicPost;
    if (el.matches(ARTICLE_SELECTOR)) return el;
    return el.closest(ARTICLE_SELECTOR);
  }

  function getFrame(postEl) {
    if (!postEl || !(postEl instanceof HTMLElement)) return null;
    const row = postEl.querySelector(":scope > .row");
    if (row && row.querySelector(".topic-body")) return row;
    const body = postEl.querySelector(".topic-body");
    if (body && body.parentElement && body.parentElement !== postEl) {
      return body.parentElement;
    }
    return postEl;
  }

  function getPostText(postEl) {
    const cooked = postEl.querySelector(".topic-body .cooked");
    if (cooked && cooked.innerText) return cooked.innerText;
    const body = postEl.querySelector(".topic-body");
    return (body && body.innerText) || postEl.innerText || "";
  }

  function shouldBlock(text) {
    const haystack = text.toLowerCase();
    return terms.some((term) => haystack.includes(term.toLowerCase()));
  }

  function applyBlock(postEl) {
    const frame = getFrame(postEl);
    if (!frame || frame.classList.contains("lh-blocked")) return;

    frame.classList.add("lh-blocked");
    if (!frame.querySelector(".lh-mask")) {
      const mask = document.createElement("div");
      mask.className = "lh-mask";
      mask.textContent = "LASHON HORA";
      frame.appendChild(mask);
    }
  }

  function clearBlock(postEl) {
    const frame = getFrame(postEl);
    if (!frame || !frame.classList.contains("lh-blocked")) return;

    frame.classList.remove("lh-blocked");
    const mask = frame.querySelector(".lh-mask");
    if (mask) mask.remove();
  }

  function scanPost(postEl) {
    const text = getPostText(postEl);
    const hasText = text.trim().length > 0;
    if (shouldBlock(text)) {
      applyBlock(postEl);
    } else if (hasText) {
      clearBlock(postEl);
    }
  }

  function isActualPost(el) {
    if (!el || !(el instanceof HTMLElement)) return false;
    const hasPostId = el.hasAttribute("data-post-id");
    const hasPostIdFromId = typeof el.id === "string" && /^post_\\d+/.test(el.id);
    if (!hasPostId && !hasPostIdFromId) return false;
    if (!el.querySelector(".topic-body")) return false;
    return true;
  }

  function isActualPost(el) {
    const container = getContainer(el);
    if (!container) return null;
    if (!container.querySelector(".topic-body")) return null;
    const hasPostId =
      container.hasAttribute("data-post-id") ||
      /^post_\\d+/.test(container.id || "") ||
      !!container.querySelector(ARTICLE_SELECTOR) ||
      !!container.querySelector("[data-post-id]");
    if (!hasPostId) return null;
    return container;
  }

  function findPosts(root = document) {
    const posts = [];
    const seen = new Set();
    root.querySelectorAll(POST_SELECTOR).forEach((node) => {
      const container = isActualPost(node);
      if (!container || seen.has(container)) return;
      seen.add(container);
      posts.push(container);
    });
    return posts;
  }

  function scanAll() {
    if (!document.body) return;
    ensureStyles();
    findPosts().forEach(scanPost);
  }

  let scanQueued = false;
  function scheduleScan() {
    if (scanQueued) return;
    scanQueued = true;
    requestAnimationFrame(() => {
      scanQueued = false;
      scanAll();
    });
  }

  function handleMutations(mutations) {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof HTMLElement)) continue;
        if (node.matches && node.matches(POST_SELECTOR)) {
          const container = isActualPost(node);
          if (container) scanPost(container);
        } else if (node.querySelectorAll) {
          findPosts(node).forEach(scanPost);
        }
      }
    }
  }

  function observe() {
    if (!document.body) return;
    const observer = new MutationObserver(handleMutations);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (!changes[STORAGE_KEY]) return;
    terms = normalizeTerms(changes[STORAGE_KEY].newValue || []);
    scanAll();
  });

  loadTerms();
  observe();
  window.addEventListener("scroll", scheduleScan, true);
  window.addEventListener("resize", scheduleScan);
})();
