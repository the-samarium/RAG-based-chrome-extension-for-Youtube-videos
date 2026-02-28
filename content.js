// ── Inject sidebar ────────────────────────────────────────────
function injectSidebar() {
  if (document.getElementById("yqa-sidebar")) return;
  if (!window.location.pathname.startsWith("/watch")) return;

  const videoId = new URLSearchParams(window.location.search).get("v");
  if (!videoId) return;

  const sidebar = document.createElement("iframe");
  sidebar.id = "yqa-sidebar";
  sidebar.src = chrome.runtime.getURL("sidebar.html") + `?video_id=${videoId}`;

  Object.assign(sidebar.style, {
    position:   "fixed",
    top:        "0",
    right:      "0",
    width:      "340px",
    height:     "100vh",
    border:     "none",
    zIndex:     "9999",
    background: "transparent",
  });

  document.body.appendChild(sidebar);
}

injectSidebar();

window.addEventListener("yt-navigate-finish", () => {
  document.getElementById("yqa-sidebar")?.remove();
  injectSidebar();
});

// ── Handle messages from sidebar iframe ───────────────────────
window.addEventListener("message", (e) => {
  if (!e.data?.type) return;
  const sidebar = document.getElementById("yqa-sidebar");
  if (!sidebar) return;

  // Resize: drag left edge
  if (e.data.type === "YQA_RESIZE") {
    sidebar.style.width = e.data.width + "px";
    sidebar.style.right = "0";
    sidebar.style.left  = "auto";
  }

  // Move: drag header
  if (e.data.type === "YQA_MOVE_START") {
    const rect = sidebar.getBoundingClientRect();

    // Convert to left-based positioning so we can move freely
    sidebar.style.left   = rect.left   + "px";
    sidebar.style.right  = "auto";
    sidebar.style.top    = rect.top    + "px";
    sidebar.style.height = rect.height + "px";

    const offsetX = e.data.mouseX - rect.left;
    const offsetY = e.data.mouseY - rect.top;

    function onMove(ev) {
      let newLeft = ev.clientX - offsetX;
      let newTop  = ev.clientY - offsetY;

      // Clamp within viewport
      newLeft = Math.max(0, Math.min(window.innerWidth  - sidebar.offsetWidth,  newLeft));
      newTop  = Math.max(0, Math.min(window.innerHeight - sidebar.offsetHeight, newTop));

      sidebar.style.left = newLeft + "px";
      sidebar.style.top  = newTop  + "px";
    }

    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
      sidebar.contentWindow?.postMessage({ type: "YQA_MOVE_END" }, "*");
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
  }
});