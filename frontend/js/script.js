/* ============================================================
   CodeMentor AI — frontend logic
   ------------------------------------------------------------
   >>> ONE PLACE TO CHANGE THE BACKEND URL <<<
   While testing locally it points at http://127.0.0.1:8000
   After deploying to Render, replace it with your Render URL,
   e.g. "https://codementor-ai-api.onrender.com"
   ============================================================ */
const API_BASE_URL = "http://127.0.0.1:8000";
/* ============================================================ */

const MAX_HINTS = 3;

/* ---------- tiny helpers ---------- */
const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ============================================================
   NAVBAR / THEME / REVEAL ANIMATIONS
   ============================================================ */
function initChrome() {
  // Year in footer
  $("year").textContent = new Date().getFullYear();

  // Sticky navbar shadow
  const navbar = $("navbar");
  const onScroll = () => navbar.classList.toggle("scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile menu
  const links = $("navLinks");
  $("hamburger").addEventListener("click", () => links.classList.toggle("open"));
  links.addEventListener("click", (e) => {
    if (e.target.tagName === "A") links.classList.remove("open");
  });

  // Theme toggle (remembered)
  const root = document.documentElement;
  const saved = localStorage.getItem("cm-theme");
  if (saved) root.setAttribute("data-theme", saved);
  syncThemeButton();
  $("themeToggle").addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("cm-theme", next);
    syncThemeButton();
  });
  function syncThemeButton() {
    $("themeToggle").textContent = root.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
  }

  // Scroll reveal
  const io = new IntersectionObserver(
    (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible")),
    { threshold: 0.12 }
  );
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
}
initChrome();

/* ============================================================
   DEMO STATE
   ============================================================ */
const DEFAULT_CODE = `def average(numbers):
    """Return the average of a list of numbers."""
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)


print(average([2, 4, 6]))
print(average([]))`;

const state = {
  conversation: [], // {role, content} — sent to the backend every turn
  hintsUsed: 0,
  busy: false,
  started: false,
  offline: false,
  turns: 0,
  pathShown: false,
};

const els = {
  editor: $("codeEditor"),
  gutter: $("gutter"),
  log: $("chatLog"),
  typing: $("typing"),
  input: $("chatInput"),
  send: $("sendBtn"),
  hint: $("hintBtn"),
  diagnose: $("diagnoseBtn"),
  reset: $("resetBtn"),
  mode: $("modeBadge"),
  dot: $("statusDot"),
  meterFill: $("meterFill"),
  meterValue: $("meterValue"),
  pips: Array.from(document.querySelectorAll("#hintPips .pip")),
  hintNote: $("hintNote"),
  pathBlock: $("pathBlock"),
  pathList: $("pathList"),
  errBox: $("demoError"),
  errMsg: $("demoErrorMsg"),
  retry: $("retryBtn"),
  offline: $("offlineBtn"),
  bugBadge: $("bugBadge"),
};

/* ---------- editor line numbers ---------- */
function syncGutter() {
  const lines = els.editor.value.split("\n").length;
  els.gutter.textContent = Array.from({ length: lines }, (_, i) => i + 1).join("\n");
}
els.editor.addEventListener("input", syncGutter);
els.editor.addEventListener("scroll", () => (els.gutter.scrollTop = els.editor.scrollTop));
syncGutter();

/* ---------- chat rendering ---------- */
function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role === "user" ? "user" : "assistant"}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "You" : "M";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text; // textContent = never executes HTML
  wrap.append(avatar, bubble);
  els.log.appendChild(wrap);
  els.log.scrollTop = els.log.scrollHeight;
  return bubble;
}

function setBusy(busy) {
  state.busy = busy;
  els.typing.hidden = !busy;
  els.dot.classList.toggle("busy", busy);
  els.input.disabled = busy || !state.started;
  els.send.disabled = busy || !state.started;
  els.hint.disabled = busy || !state.started;
  els.diagnose.disabled = busy;
  if (busy) els.log.scrollTop = els.log.scrollHeight;
}

function setMode(label, kind) {
  els.mode.textContent = label;
  els.mode.className = "badge" + (kind ? ` badge-${kind}` : "");
}

/* ---------- side panel ---------- */
function setMeter(score) {
  const s = Math.max(0, Math.min(100, Number(score) || 0));
  els.meterFill.style.width = `${s}%`;
  els.meterValue.textContent = s;
}

function setHints(left) {
  state.hintsUsed = Math.max(0, MAX_HINTS - left);
  els.pips.forEach((p, i) => p.classList.toggle("spent", i >= left));
  els.hintNote.textContent =
    left === 0
      ? "No hints left — reason it out 💪"
      : `${left} hint${left === 1 ? "" : "s"} left — only if you ask`;
}

function showPath(topics) {
  if (!topics || !topics.length) return;
  els.pathList.innerHTML = "";
  topics.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    els.pathList.appendChild(li);
  });
  els.pathBlock.hidden = false;
  state.pathShown = true;
}

/* ---------- error banner ---------- */
function showError(message) {
  els.errMsg.textContent = message;
  els.errBox.hidden = false;
  els.dot.classList.add("error");
  setMode("error", "err");
}
function hideError() {
  els.errBox.hidden = true;
  els.dot.classList.remove("error");
}

/* ============================================================
   REAL API CALL
   ============================================================ */
async function callMentor(payload) {
  const res = await fetch(`${API_BASE_URL}/api/mentor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON response */
  }

  if (!res.ok) {
    const detail = body && body.detail ? body.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  if (!body || typeof body.reply !== "string") {
    throw new Error("Malformed response from the server.");
  }
  return body;
}

/* ============================================================
   SCRIPTED FALLBACK (works with no backend at all)
   ============================================================ */
const OFFLINE_SCRIPT = [
  {
    reply:
      "Before anything else: run through this code in your head, line by line, with the input `average([])`. What happens to `len(numbers)` at that exact moment?",
    understanding_score: 15,
    next_topics: ["Edge cases: empty input", "ZeroDivisionError", "Guard clauses"],
  },
  {
    reply:
      "Good — so `len([])` gives you 0. Now tell me: what does the `/` operator do when the number on the right is 0, and what does Python call that situation?",
    understanding_score: 32,
    next_topics: ["Edge cases: empty input", "ZeroDivisionError", "Guard clauses"],
  },
  {
    reply:
      "Right. So the crash is a symptom, not the cause. What is the *contract* of this function — should it accept an empty list at all? What do you think the caller expects?",
    understanding_score: 50,
    next_topics: ["Function contracts", "Guard clauses", "Raising vs returning"],
  },
  {
    reply:
      "Now imagine you decide an empty list should return 0 instead of crashing. Where exactly would you put that check — before the loop, inside it, or at the return — and why is the other place wrong?",
    understanding_score: 68,
    next_topics: ["Guard clauses", "Edge cases: empty input", "Early returns"],
  },
  {
    reply:
      "Nice reasoning. Last step: explain your fix to me in your own words — what changed, and why does the function now behave correctly for BOTH inputs?",
    understanding_score: 84,
    next_topics: ["Writing your own test cases", "Tracebacks in Python", "Defensive coding"],
  },
  {
    reply:
      "That's a complete explanation — you found the bug, named the cause and justified the fix yourself. To transfer this skill: what other functions in your code divide by something that could be zero?",
    understanding_score: 95,
    next_topics: ["Writing your own test cases", "Tracebacks in Python", "Defensive coding"],
  },
];

function nextOfflineReply() {
  const idx = Math.min(state.turns, OFFLINE_SCRIPT.length - 1);
  return OFFLINE_SCRIPT[idx];
}

/* ============================================================
   TURN HANDLING
   ============================================================ */
async function askMentor(userText) {
  if (state.busy) return;
  hideError();

  // 1. show the student's message
  if (userText) {
    addMessage("user", userText);
    state.conversation.push({ role: "user", content: userText });
  }

  setBusy(true);

  const payload = {
    code: els.editor.value,
    conversation: state.conversation,
    hints_used: state.hintsUsed,
  };

  let data = null;
  let failure = null;

  if (state.offline) {
    await sleep(650);
    data = nextOfflineReply();
  } else {
    try {
      data = await callMentor(payload);
    } catch (err) {
      failure = err.message || "Network error";
    }
  }

  await sleep(350);
  setBusy(false);

  if (failure) {
    // Keep the student's message in history so a retry does not duplicate it.
    showError(failure);
    addMessage(
      "assistant",
      "⚠️ I couldn't reach the mentor API. Press Retry, or continue with the built-in offline demo."
    );
    return;
  }

  // 2. record mentor reply
  state.turns += 1;
  state.conversation.push({ role: "assistant", content: data.reply });
  addMessage("assistant", data.reply);

  // 3. update the side panel
  setMeter(data.understanding_score);
  setHints(typeof data.hints_left === "number" ? data.hints_left : MAX_HINTS - state.hintsUsed);

  // Show the learning path at the end of the session (or if the model insists)
  if (state.pathShown || state.turns >= 3 || data.understanding_score >= 75) {
    showPath(data.next_topics);
  }

  if (!state.offline) setMode("connected", "ok");
}

/* ============================================================
   BUTTONS
   ============================================================ */
const OPENING_LINE =
  "Here is my code. Something is wrong with it — it works for [2, 4, 6] but blows up on the last line. Start with your first guiding question.";

els.diagnose.addEventListener("click", async () => {
  if (state.busy) return;
  resetSession(true);
  state.started = true;
  setMode("thinking…", "");
  setBusy(false);
  await askMentor(OPENING_LINE);
});

els.send.addEventListener("click", sendMessage);
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !els.input.disabled) sendMessage();
});

function sendMessage() {
  const text = els.input.value.trim();
  if (!text || state.busy) return;
  els.input.value = "";
  askMentor(text);
}

els.hint.addEventListener("click", async () => {
  if (state.busy) return;
  if (state.hintsUsed >= MAX_HINTS) {
    addMessage("assistant", "You're out of hints — you've got this. What do you notice first?");
    return;
  }
  state.hintsUsed += 1;
  await askMentor("I'm stuck. Please give me a hint (not the answer).");
});

els.reset.addEventListener("click", () => resetSession(false));

els.retry.addEventListener("click", () => {
  if (state.busy || !state.started) return;
  askMentor(null); // the conversation already holds the last message
});

els.offline.addEventListener("click", async () => {
  state.offline = true;
  state.started = true;
  hideError();
  setMode("offline demo", "warn");
  setBusy(false);
  if (state.turns === 0) await askMentor(null); // start the scripted mentor
});

function resetSession(silent) {
  state.conversation = [];
  state.hintsUsed = 0;
  state.turns = 0;
  state.started = false;
  state.pathShown = false;
  hideError();
  setMeter(10);
  setHints(MAX_HINTS);
  els.pathBlock.hidden = true;
  els.pathList.innerHTML = "";
  els.editor.value = DEFAULT_CODE;
  syncGutter();
  els.bugBadge.textContent = "● buggy";
  els.bugBadge.className = "badge badge-warn";
  els.log.innerHTML = "";
  addMessage(
    "assistant",
    silent
      ? "Session started. I've read your code — let's find the problem together. Ready?"
      : "Fresh session! Press Diagnose when you're ready."
  );
  els.input.disabled = true;
  els.send.disabled = true;
  els.hint.disabled = true;
  setMode("ready", "");
}

/* ============================================================
   STARTUP: check the backend, but never block the page
   ============================================================ */
(function pingBackend() {
  fetch(`${API_BASE_URL}/health`, { mode: "cors" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("bad status"))))
    .then(() => setMode("connected", "ok"))
    .catch(() => {
      setMode("offline", "warn");
      // The demo still works — the offline script takes over on first failure.
    });
})();

setMeter(10);
setHints(MAX_HINTS);
