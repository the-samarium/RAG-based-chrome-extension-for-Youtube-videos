// ── State ─────────────────────────────────────────────────────
const params  = new URLSearchParams(window.location.search);
const videoId = params.get("video_id");

const chatBox = document.getElementById("chat-box");
const input   = document.getElementById("question-input");
const btn     = document.getElementById("ask-btn");

// ── Theme toggle ──────────────────────────────────────────────
const themeBtn = document.getElementById("theme-toggle");
let isDark = false;

themeBtn.addEventListener("click", () => {
  isDark = !isDark;
  document.body.classList.toggle("dark", isDark);
});

// ── Clear chat ────────────────────────────────────────────────
document.getElementById("clear-btn").addEventListener("click", () => {
  chatBox.innerHTML = "";
});

// ── Messages ──────────────────────────────────────────────────
function addMessage(text, sender) {
  const msg = document.createElement("div");
  msg.className = `message ${sender}`;
  msg.textContent = text;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
  return msg;
}

// ── Ask ───────────────────────────────────────────────────────
async function askQuestion() {
  const question = input.value.trim();
  if (!question) return;

  addMessage(question, "user");
  input.value = "";
  btn.disabled = true;

  const loadingMsg = addMessage("thinking", "bot loading");

  try {
    const res = await fetch("http://localhost:5000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: videoId, question })
    });

    const data = await res.json();
    loadingMsg.remove();

    if (data.error) {
      addMessage(data.error, "bot error");
    } else {
      addMessage(data.answer, "bot");
    }
  } catch {
    loadingMsg.remove();
    addMessage("cannot reach server — is Flask running?", "bot error");
  }

  btn.disabled = false;
  input.focus();
}

btn.addEventListener("click", askQuestion);
input.addEventListener("keydown", e => e.key === "Enter" && askQuestion());

// ── Resize (drag left edge) ───────────────────────────────────
const handle = document.getElementById("resize-handle");
let resizing = false;
let startX   = 0;
let startW   = 0;

handle.addEventListener("mousedown", (e) => {
  resizing = true;
  startX   = e.clientX;
  startW   = window.innerWidth;
  document.body.style.cursor = "ew-resize";
  e.preventDefault();
});

document.addEventListener("mousemove", (e) => {
  if (!resizing) return;
  const delta    = startX - e.clientX;
  const newWidth = Math.min(600, Math.max(280, startW + delta));
  window.parent.postMessage({ type: "YQA_RESIZE", width: newWidth }, "*");
});

document.addEventListener("mouseup", () => {
  if (resizing) {
    resizing = false;
    document.body.style.cursor = "";
  }
});

// ── Move (drag header) ────────────────────────────────────────
const header = document.getElementById("header");
let moving = false;

header.style.cursor = "grab";

header.addEventListener("mousedown", (e) => {
  // Don't drag if clicking buttons
  if (e.target.tagName === "BUTTON") return;

  moving = true;
  header.style.cursor = "grabbing";

  // Send mouse position in screen coordinates to parent
  window.parent.postMessage({
    type:   "YQA_MOVE_START",
    mouseX: e.screenX - window.screenX + window.scrollX,
    mouseY: e.screenY - window.screenY + window.scrollY,
  }, "*");

  e.preventDefault();
});

document.addEventListener("mouseup", () => {
  if (moving) {
    moving = false;
    header.style.cursor = "grab";
  }
});

// Listen for move end confirmation from parent
window.addEventListener("message", (e) => {
  if (e.data?.type === "YQA_MOVE_END") {
    moving = false;
    header.style.cursor = "grab";
  }
});