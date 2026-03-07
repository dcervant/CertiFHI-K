const STORAGE_KEY = "fhir_quiz_state_v1";

let questions = [];
let state = {
  order: [],
  cursor: 0,
  answered: {} // qid -> { choice, correct }
};

const el = (id) => document.getElementById(id);

function saveState() {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function loadState() {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return false;
  try {
    state = JSON.parse(raw);
    return true;
  } catch {
    return false;
  }
}

function resetState() {
  state = {
    order: questions.map(q => q.id),
    cursor: 0,
    answered: {}
  };
  saveState();
}

function computeStats() {
  const total = state.order.length;
  const answeredIds = Object.keys(state.answered);
  const answered = answeredIds.length;
  const correct = answeredIds.filter(id => state.answered[id].correct).length;
  const accuracy = answered ? (correct / answered * 100) : 0;
  const progress = total ? (answered / total * 100) : 0;
  return { total, answered, correct, incorrect: answered - correct, accuracy, progress };
}

function prettyJson(maybeObjOrString) {
  if (typeof maybeObjOrString === "object") {
    return JSON.stringify(maybeObjOrString, null, 2);
  }
  if (typeof maybeObjOrString === "string") {
    const s = maybeObjOrString.trim();
    try {
      const parsed = JSON.parse(s);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return maybeObjOrString; // no es JSON válido, lo devolvemos tal cual
    }
  }
  return String(maybeObjOrString);
}

function getCurrentQuestion() {
  if (state.cursor >= state.order.length) return null;
  const qid = state.order[state.cursor];
  return questions.find(q => q.id === qid);
}

function setFeedback(feedback) {
  const box = el("feedbackBox");
  if (!feedback) {
    box.className = "mt-4 hidden rounded-xl p-4 border";
    box.innerHTML = "";
    return;
  }

  const showExplain = el("toggleExplain").checked;
  const ok = feedback.isCorrect;

  box.className =
    "mt-4 rounded-xl p-4 border " +
    (ok ? "border-emerald-500/30 bg-emerald-500/10" : "border-rose-500/30 bg-rose-500/10");

  let html = `<div class="font-semibold">${ok ? "✅ Correcto" : "❌ Incorrecto"}</div>`;

  if (!ok) {
    let correctTextContent;
    if (feedback.optionsFormat === 'json') {
      const pretty = prettyJson(feedback.correctText);
      correctTextContent = `<pre class="language-json my-1 text-xs whitespace-pre-wrap bg-slate-900/50 p-2 rounded"><code>${escapeHtml(pretty)}</code></pre>`;
    } else {
      correctTextContent = escapeHtml(feedback.correctText);
    }

    html += `<div class="mt-1 text-sm text-slate-200">
      <div>Correcta: <span class="font-semibold">${feedback.correctChoice})</span></div>
      <div class="mt-1">${correctTextContent}</div>
    </div>`;
  }

  if (showExplain && feedback.explanation) {
    html += `<div class="mt-2 text-sm text-slate-300">
      <span class="text-slate-400">Explicación:</span> ${escapeHtml(feedback.explanation)}
    </div>`;
  }

  box.innerHTML = html;

  if (!ok && feedback.optionsFormat === 'json' && window.Prism) {
    Prism.highlightAll();
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderStats() {
  const st = computeStats();
  el("progressText").textContent = `${st.answered}/${st.total} respondidas`;
  el("scoreText").textContent = `${st.correct} correctas (${st.accuracy.toFixed(1)}%)`;
  el("progressBar").style.width = `${st.progress}%`;
  el("progressPct").textContent = `${st.progress.toFixed(1)}%`;
}

function renderJumpToQuestion() {
  const jumpSelect = el("jumpToQuestion");
  const currentIndex = state.cursor;
  jumpSelect.innerHTML = ""; // Clear existing options

  state.order.forEach((qid, index) => {
    const answered = state.answered[qid];
    // Usamos non-breaking space para alinear cuando no hay ícono
    const prefix = answered ? (answered.correct ? "✅ " : "❌ ") : "\u00A0\u00A0 ";
    const option = new Option(`${prefix}Pregunta ${index + 1}`, index);
    jumpSelect.add(option);
  });

  jumpSelect.value = currentIndex;
}

function renderQuestion() {
  renderStats();
  renderJumpToQuestion();
  setFeedback(null);

  const q = getCurrentQuestion();
  const finished = el("finishedWrap");
  const quizSection = el("quizSection");

  if (!q) {
    // terminado
    const st = computeStats();
    el("finalText").textContent = `Correctas: ${st.correct}/${st.total} • Accuracy: ${st.accuracy.toFixed(1)}%`;
    finished.classList.remove("hidden");
    quizSection.classList.add("hidden");
    return;
  }

  finished.classList.add("hidden");
  quizSection.classList.remove("hidden");

  el("qCounter").textContent = `Pregunta ${state.cursor + 1} / ${state.order.length}`;
  el("qPrompt").textContent = q.prompt;

  // Contexto
  const contextWrap = el("contextWrap");
  const contextPre = el("contextPre");
  const stem = q.stem || null;

  if (stem && stem.content !== undefined && String(stem.content).trim() !== "") {
    contextWrap.classList.remove("hidden");

    const stemType = (stem.type || "text").toLowerCase();
    contextPre.innerHTML = "";
    contextPre.className = "rounded-xl border border-slate-800 bg-slate-950 p-4 overflow-auto text-sm";

    if (stemType === "json") {
      const code = prettyJson(stem.content);
      contextPre.innerHTML = `<code class="language-json">${escapeHtml(code)}</code>`;
    } else if (stemType === "tsv") {
      const table = document.createElement("table");
      table.className = "w-full text-left border-collapse";
      const lines = Array.isArray(stem.content)
        ? stem.content
        : String(stem.content).trim().split("\n");

      if (lines.length > 0) {
        const header = table.createTHead().insertRow();
        lines[0].split("\t").forEach(text => {
          const th = document.createElement("th");
          th.className = "p-2 border-b border-slate-700 bg-slate-900 font-semibold";
          th.textContent = text.trim();
          header.appendChild(th);
        });
      }

      const tbody = table.createTBody();
      lines.slice(1).forEach(line => {
        const row = tbody.insertRow();
        row.className = "hover:bg-slate-800/50";
        line.split("\t").forEach(text => {
          const cell = row.insertCell();
          cell.className = "p-2 border-b border-slate-800";
          cell.textContent = text.trim();
        });
      });
      contextPre.appendChild(table);
    } else {
      contextPre.classList.add("whitespace-pre-wrap");
      contextPre.textContent = String(stem.content);
    }
  } else {
    contextWrap.classList.add("hidden");
    contextPre.textContent = "";
  }

  // Opciones
  const optionsWrap = el("optionsWrap");
  optionsWrap.innerHTML = "";
  const optionsFormat = q.options_format || "text";

  ["A", "B", "C", "D"].forEach((k) => {
    const text = q.options[k];
    const label = document.createElement("label");
    label.className =
      "group flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/50 p-4 hover:border-indigo-500/40 hover:bg-slate-950 transition cursor-pointer";

    let contentWrapper;
    if (optionsFormat === 'json') {
      const pretty = prettyJson(text);
      const optionContent = `<pre class="language-json mt-1 text-xs whitespace-pre-wrap bg-transparent p-0"><code>${escapeHtml(pretty)}</code></pre>`;
      contentWrapper = `
        <div class="w-full overflow-x-auto">
          <div class="text-sm font-semibold text-slate-200">${k})</div>
          ${optionContent}
        </div>
      `;
    } else {
      contentWrapper = `
        <div class="text-sm text-slate-300">
          <span class="font-semibold text-slate-200">${k})</span>
          <span class="ml-2">${escapeHtml(text)}</span>
        </div>
      `;
    }

    label.innerHTML = `
      <input type="radio" name="choice" value="${k}" class="mt-1 h-4 w-4 accent-indigo-500" required />
      ${contentWrapper}
    `;
    optionsWrap.appendChild(label);
  });

  // Botones
  el("btnConfirm").disabled = false;
  el("btnConfirm").classList.remove("hidden");
  el("btnNext").classList.add("hidden");

  // reset del form
  el("answerForm").reset();

  // Re-lanzar el resaltado de sintaxis si hemos añadido bloques de código
  if (q.stem?.type === 'json' || optionsFormat === 'json') {
    if (window.Prism) Prism.highlightAll();
  }
}

function handleSubmit(e) {
  e.preventDefault();
  const q = getCurrentQuestion();
  if (!q) return;

  const form = e.target;
  const choice = new FormData(form).get("choice");
  if (!choice) return;

  const correctChoice = String(q.answer).toUpperCase();
  const isCorrect = String(choice).toUpperCase() === correctChoice;

  // Guardar respuesta local
  state.answered[q.id] = { choice: String(choice).toUpperCase(), correct: isCorrect };
  saveState();

  // Mostrar feedback
  setFeedback({
    isCorrect,
    correctChoice,
    correctText: q.options[correctChoice],
    explanation: q.explanation || null,
    optionsFormat: q.options_format || 'text'
  });

  // Cambiar UI a "Siguiente"
  el("btnConfirm").disabled = true;
  el("btnConfirm").classList.add("hidden");
  el("btnNext").classList.remove("hidden");

  renderStats();
}

function nextQuestion() {
  let newCursor = state.cursor + 1;
  // Avanza cursor a la siguiente no respondida
  while (newCursor < state.order.length && state.answered[state.order[newCursor]]) {
    newCursor += 1;
  }
  state.cursor = newCursor;
  saveState();
  renderQuestion();
}

function initResizer() {
  const sidebar = el('sidebar');
  const resizer = el('resizer');
  const SIDEBAR_WIDTH_KEY = 'fhir_quiz_sidebar_width';

  const savedWidth = localStorage.getItem(SIDEBAR_WIDTH_KEY);
  if (savedWidth) {
    sidebar.style.width = `${savedWidth}px`;
  }

  resizer.addEventListener('mousedown', () => {
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const mouseMoveHandler = (e) => {
      const newWidth = e.clientX;
      // Limitar el tamaño mínimo y máximo de la barra lateral
      if (newWidth > 320 && newWidth < (window.innerWidth - 400)) {
        sidebar.style.width = `${newWidth}px`;
      }
    };

    const mouseUpHandler = () => {
      document.removeEventListener('mousemove', mouseMoveHandler);
      document.removeEventListener('mouseup', mouseUpHandler);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
      localStorage.setItem(SIDEBAR_WIDTH_KEY, sidebar.offsetWidth);
    };

    document.addEventListener('mousemove', mouseMoveHandler);
    document.addEventListener('mouseup', mouseUpHandler);
  });
}

async function init() {
  // Cargar preguntas
  const res = await fetch("./questions.json", { cache: "no-store" });
  const data = await res.json();

  questions = (data.questions || []).map((q, idx) => ({
    id: q.id || `idx-${idx}`,
    prompt: q.prompt,
    stem: q.stem || null,
    options: q.options,
    answer: q.answer,
    explanation: q.explanation || null,
    options_format: q.options_format || null
  }));

  // Estado
  const hasState = loadState();
  if (!hasState || !state.order || state.order.length !== questions.length) {
    resetState();
  }

  // Eventos
  el("answerForm").addEventListener("submit", handleSubmit);
  el("btnNext").addEventListener("click", nextQuestion);

  el("jumpToQuestion").addEventListener("change", (e) => {
    const newIndex = parseInt(e.target.value, 10);
    if (!isNaN(newIndex)) {
      state.cursor = newIndex;
      saveState();
      renderQuestion();
    }
  });

  el("btnReset").addEventListener("click", () => {
    resetState();
    el("quizSection").classList.remove("hidden");
    el("finishedWrap").classList.add("hidden");
    setFeedback(null);
    renderQuestion();
  });

  el("btnRestart").addEventListener("click", () => {
    resetState();
    el("quizSection").classList.remove("hidden");
    el("finishedWrap").classList.add("hidden");
    setFeedback(null);
    renderQuestion();
  });

  el("toggleExplain").addEventListener("change", () => {
    // no recalcula nada, solo afecta futuros feedback; si quieres re-render del último feedback, lo implementamos
  });

  initResizer();
  renderQuestion();
}

init();
