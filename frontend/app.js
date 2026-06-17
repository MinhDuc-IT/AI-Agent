const API_BASE =
  (window.APP_CONFIG && window.APP_CONFIG.apiBaseUrl) ||
  "http://127.0.0.1:8000";

const STORAGE_CHATS = "legal_qa_chats";
const STORAGE_SIDEBAR = "legal_qa_sidebar_collapsed";

const appEl = document.getElementById("app");
const chatView = document.getElementById("chat-view");
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const errorBanner = document.getElementById("error-banner");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const asOfInput = document.getElementById("as-of");
const docNumberInput = document.getElementById("document-number");
const topKInput = document.getElementById("top-k");
const quickActionsEl = document.getElementById("quick-actions");
const recentsListEl = document.getElementById("recents-list");
const searchInput = document.getElementById("search-input");
const sidebarSearch = document.getElementById("sidebar-search");

const QUICK_ACTIONS = [
  {
    label: "Thẩm quyền đầu tư Thủ đô",
    query: "Hội đồng nhân dân Hà Nội có thẩm quyền gì về đầu tư công?",
  },
  {
    label: "Kiểm tra ô tô nhập khẩu",
    query: "Ô tô nhập khẩu phải kiểm tra những gì về đèn phanh?",
  },
  {
    label: "Chứng chỉ thẩm tra viên",
    query: "Điều kiện cấp đổi chứng chỉ thẩm tra viên an toàn giao thông?",
  },
];

let messagesInner = null;
let isLoading = false;
let currentChatId = null;
let currentMessages = [];
let chatSessions = [];
let searchQuery = "";

function apiUrl(path) {
  return `${API_BASE.replace(/\/$/, "")}${path}`;
}

function newChatId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadSessions() {
  try {
    chatSessions = JSON.parse(localStorage.getItem(STORAGE_CHATS) || "[]");
  } catch {
    chatSessions = [];
  }
}

function persistSessions() {
  localStorage.setItem(
    STORAGE_CHATS,
    JSON.stringify(chatSessions.slice(0, 50)),
  );
}

function chatTitle(messages) {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "Cuộc trò chuyện mới";
  const t = first.text.trim();
  return t.length > 42 ? t.slice(0, 42) + "…" : t;
}

function ensureMessagesInner() {
  if (!messagesInner) {
    messagesInner = document.createElement("div");
    messagesInner.className = "messages-inner";
    messagesEl.appendChild(messagesInner);
  }
  return messagesInner;
}

function setChatMode(active) {
  chatView.classList.toggle("is-empty", !active);
}

function setSidebarCollapsed(collapsed) {
  appEl.classList.toggle("sidebar-collapsed", collapsed);
  localStorage.setItem(STORAGE_SIDEBAR, collapsed ? "1" : "0");
}

function toggleSidebar() {
  setSidebarCollapsed(!appEl.classList.contains("sidebar-collapsed"));
}

function setError(message) {
  if (!message) {
    errorBanner.classList.remove("visible");
    errorBanner.textContent = "";
    return;
  }
  errorBanner.textContent = message;
  errorBanner.classList.add("visible");
}

function updateSendButton() {
  sendBtn.disabled = isLoading || !input.value.trim();
}

function setLoading(loading) {
  isLoading = loading;
  input.disabled = loading;
  updateSendButton();
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setDefaultFilters() {
  asOfInput.value = "";
  docNumberInput.value = "";
  topKInput.value = 5;
}

function getFilters() {
  return {
    as_of: asOfInput.value.trim() || null,
    document_number: docNumberInput.value.trim() || null,
    top_k: parseInt(topKInput.value, 10) || 5,
  };
}

function applyFilters(filters) {
  asOfInput.value = filters?.as_of ?? "";
  docNumberInput.value = filters?.document_number || "";
  topKInput.value = filters?.top_k || 5;
}

function renderMessageDom(role, text, sources) {
  const inner = ensureMessagesInner();
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;

  let body;
  if (role === "user") {
    body = document.createElement("div");
    body.className = "message-body";
    body.textContent = text;
    wrap.appendChild(body);
  } else {
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "LQ";
    body = document.createElement("div");
    body.className = "message-body";
    body.textContent = text;
    wrap.appendChild(avatar);
    wrap.appendChild(body);
    if (sources?.length) attachSources(body, sources);
  }

  inner.appendChild(wrap);
  return body;
}

function createMessage(role, text, sources) {
  setChatMode(true);
  const msg = { role, text, sources: sources || null };
  currentMessages.push(msg);
  return renderMessageDom(role, text, sources);
}

function createTypingIndicator() {
  setChatMode(true);
  const inner = ensureMessagesInner();
  const wrap = document.createElement("div");
  wrap.className = "message assistant";
  wrap.id = "typing-indicator";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "LQ";

  const body = document.createElement("div");
  body.className = "message-body";
  const typing = document.createElement("div");
  typing.className = "typing";
  typing.innerHTML = "<span></span><span></span><span></span>";
  body.appendChild(typing);

  wrap.appendChild(avatar);
  wrap.appendChild(body);
  inner.appendChild(wrap);
  scrollToBottom();
}

function removeTypingIndicator() {
  document.getElementById("typing-indicator")?.remove();
}

function attachSources(messageBody, sources) {
  if (!sources?.length) return;

  const sourcesWrap = document.createElement("div");
  sourcesWrap.className = "sources";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "sources-toggle";
  toggle.textContent = `Xem ${sources.length} nguồn tham chiếu`;

  const list = document.createElement("div");
  list.className = "sources-list";

  sources.forEach((src, idx) => {
    const card = document.createElement("div");
    card.className = "source-card";
    const score = src.score != null ? ` · ${src.score.toFixed(3)}` : "";
    const from = src.effective_from || "—";
    const to = src.effective_to || "—";
    card.innerHTML = `
      <div class="meta">[${idx + 1}] ${escapeHtml(src.document_number || "Không rõ")}${score}</div>
      <div class="path">${escapeHtml(src.path_text || "")}</div>
      <div class="content">${escapeHtml(truncate(src.content || "", 280))}</div>
      <div class="meta" style="margin-top:0.3rem">Hiệu lực: ${escapeHtml(from)} → ${escapeHtml(to)}</div>
    `;
    list.appendChild(card);
  });

  toggle.addEventListener("click", () => {
    const open = list.classList.toggle("open");
    toggle.textContent = open
      ? `Ẩn nguồn tham chiếu (${sources.length})`
      : `Xem ${sources.length} nguồn tham chiếu`;
  });

  sourcesWrap.appendChild(toggle);
  sourcesWrap.appendChild(list);
  messageBody.appendChild(sourcesWrap);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function truncate(text, max) {
  const trimmed = text.trim();
  return trimmed.length <= max ? trimmed : trimmed.slice(0, max) + "…";
}

function saveCurrentChat() {
  if (!currentMessages.length) return;

  const session = {
    id: currentChatId || newChatId(),
    title: chatTitle(currentMessages),
    messages: currentMessages,
    filters: getFilters(),
    updatedAt: Date.now(),
  };

  const idx = chatSessions.findIndex((s) => s.id === session.id);
  if (idx >= 0) chatSessions[idx] = session;
  else chatSessions.unshift(session);

  chatSessions.sort((a, b) => b.updatedAt - a.updatedAt);
  currentChatId = session.id;
  persistSessions();
  renderRecents();
}

function clearChatUi() {
  messagesEl.innerHTML = "";
  messagesInner = null;
  currentMessages = [];
  setChatMode(false);
  setError("");
  input.value = "";
  input.style.height = "auto";
  updateSendButton();
}

function loadChatSession(session) {
  if (!session) return;
  saveCurrentChat();

  currentChatId = session.id;
  currentMessages = JSON.parse(JSON.stringify(session.messages));
  applyFilters(session.filters);

  messagesEl.innerHTML = "";
  messagesInner = null;

  if (currentMessages.length) {
    setChatMode(true);
    const inner = ensureMessagesInner();
    currentMessages.forEach((m) => {
      renderMessageDom(m.role, m.text, m.sources);
    });
    scrollToBottom();
  } else {
    setChatMode(false);
  }

  renderRecents();
  input.focus();
}

function resetChat() {
  saveCurrentChat();
  currentChatId = null;
  clearChatUi();
  setDefaultFilters();
  renderRecents();
  input.focus();
}

function renderRecents() {
  const q = searchQuery.trim().toLowerCase();
  const items = chatSessions.filter(
    (s) => !q || s.title.toLowerCase().includes(q),
  );

  recentsListEl.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "recents-empty";
    empty.textContent = q ? "Không tìm thấy." : "Chưa có cuộc trò chuyện.";
    recentsListEl.appendChild(empty);
    return;
  }

  items.forEach((session) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "recent-item";
    if (session.id === currentChatId) btn.classList.add("active");
    btn.textContent = session.title;
    btn.title = session.title;
    btn.addEventListener("click", () => loadChatSession(session));
    recentsListEl.appendChild(btn);
  });
}

function toggleSearch() {
  const show = sidebarSearch.classList.toggle("hidden");
  if (!show) {
    searchInput.focus();
  } else {
    searchQuery = "";
    searchInput.value = "";
    renderRecents();
  }
}

async function consumeSseStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      onEvent(JSON.parse(line.slice(6)));
    }
  }
}

function beginAssistantStream() {
  removeTypingIndicator();
  const body = createMessage("assistant", "", null);
  return body;
}

function updateAssistantStream(body, text) {
  body.textContent = text;
  const last = currentMessages[currentMessages.length - 1];
  if (last?.role === "assistant") last.text = text;
  scrollToBottom();
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message || isLoading) return;

  if (!currentChatId) currentChatId = newChatId();

  setError("");
  setLoading(true);
  createMessage("user", message);
  input.value = "";
  input.style.height = "auto";
  updateSendButton();
  createTypingIndicator();

  let assistantBody = null;
  let sources = null;
  let fullAnswer = "";
  let streamError = null;

  try {
    const res = await fetch(apiUrl("/api/chat/stream"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ message, ...getFilters() }),
    });

    if (!res.ok) {
      removeTypingIndicator();
      const data = await res.json().catch(() => ({}));
      const detail = data.detail || `Lỗi HTTP ${res.status}`;
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      createMessage("assistant", "Không thể trả lời. Vui lòng thử lại.");
      saveCurrentChat();
      return;
    }

    await consumeSseStream(res, (event) => {
      if (event.type === "error") {
        streamError = event.message || "Lỗi xử lý.";
        return;
      }
      if (event.type === "sources") {
        sources = event.sources || [];
        if (!assistantBody) assistantBody = beginAssistantStream();
        return;
      }
      if (event.type === "token") {
        if (!assistantBody) assistantBody = beginAssistantStream();
        fullAnswer += event.content || "";
        updateAssistantStream(assistantBody, fullAnswer);
        return;
      }
      if (event.type === "done") {
        fullAnswer = event.answer || fullAnswer;
        if (!assistantBody) assistantBody = beginAssistantStream();
        updateAssistantStream(
          assistantBody,
          fullAnswer || "(Không có nội dung trả lời)",
        );
        if (sources?.length) {
          attachSources(assistantBody, sources);
          const last = currentMessages[currentMessages.length - 1];
          if (last?.role === "assistant") last.sources = sources;
        }
      }
    });

    if (streamError) {
      if (!assistantBody) assistantBody = beginAssistantStream();
      setError(streamError);
      updateAssistantStream(
        assistantBody,
        "Không thể trả lời. Vui lòng thử lại.",
      );
    } else if (!assistantBody) {
      removeTypingIndicator();
      createMessage("assistant", "Không có nội dung trả lời.");
    }

    saveCurrentChat();
  } catch {
    removeTypingIndicator();
    setError(
      `Không kết nối được backend tại ${API_BASE}. Chạy: cd ai-service && python main.py && cd backend && python main.py`,
    );
    createMessage("assistant", "Lỗi kết nối mạng.");
    saveCurrentChat();
  } finally {
    setLoading(false);
    input.focus();
  }
}

function renderQuickActions() {
  quickActionsEl.innerHTML = "";
  QUICK_ACTIONS.forEach(({ label, query }) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "quick-chip";
    btn.textContent = label;
    btn.addEventListener("click", () => sendMessage(query));
    quickActionsEl.appendChild(btn);
  });
}

async function checkHealth() {
  try {
    const res = await fetch(apiUrl("/api/health"));
    const data = await res.json();
    if (res.ok && data.ready) {
      statusDot.className = "status-dot ready";
      statusText.textContent = data.model || "Sẵn sàng";
    } else {
      statusDot.className = "status-dot error";
      statusText.textContent = "Chưa sẵn sàng";
    }
  } catch {
    statusDot.className = "status-dot error";
    statusText.textContent = "Offline";
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(input.value);
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 200) + "px";
  updateSendButton();
});

searchInput.addEventListener("input", () => {
  searchQuery = searchInput.value;
  renderRecents();
});

document
  .getElementById("sidebar-toggle")
  .addEventListener("click", toggleSidebar);
document
  .getElementById("topbar-sidebar-btn")
  .addEventListener("click", toggleSidebar);
document.getElementById("new-chat-btn").addEventListener("click", resetChat);
document
  .getElementById("search-chats-btn")
  .addEventListener("click", toggleSearch);
loadSessions();
setDefaultFilters();
setSidebarCollapsed(localStorage.getItem(STORAGE_SIDEBAR) === "1");
renderRecents();
renderQuickActions();
checkHealth();
updateSendButton();
