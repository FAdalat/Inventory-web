// AI Insights widget behavior. Two things happen here:
//   1. Simple collapse/expand of the floating panel.
//   2. A fetch() call to regenerate the report without a full page reload,
//      since the widget needs to look the same on every page.
//
// Security note: everything the AI returns is treated as untrusted text,
// not markup. Every string from the API response is inserted with
// `textContent`, never `innerHTML` — this is the same rule you'd apply to
// any third-party API response, and it's what stops a stray HTML-looking
// string in a model's output from ever being interpreted as real markup.
(function () {
  const widget = document.getElementById("ai-widget");
  if (!widget) return;

  const toggleBtn = document.getElementById("ai-widget-toggle");
  const closeBtn = document.getElementById("ai-widget-close");
  const generateBtn = document.getElementById("ai-generate-btn");
  const body = document.getElementById("ai-widget-body");

  toggleBtn.addEventListener("click", () => widget.classList.remove("collapsed"));
  closeBtn.addEventListener("click", () => widget.classList.add("collapsed"));

  if (!generateBtn) return; // AI isn't configured server-side; nothing else to wire up

  function clearBody() {
    while (body.firstChild) body.removeChild(body.firstChild);
  }

  function addHint(text) {
    const p = document.createElement("p");
    p.className = "hint";
    p.textContent = text;
    body.appendChild(p);
  }

  function addSection(title, items, extraClass) {
    if (!items || items.length === 0) return;
    const heading = document.createElement("strong");
    heading.textContent = title;
    body.appendChild(heading);

    const ul = document.createElement("ul");
    if (extraClass) ul.className = extraClass;
    items.forEach((text) => {
      const li = document.createElement("li");
      li.textContent = text; // never innerHTML: AI output is untrusted text
      ul.appendChild(li);
    });
    body.appendChild(ul);
  }

  function renderInsight(data) {
    clearBody();
    addHint("Generated " + data.generated_at);

    if (data.summary) {
      const p = document.createElement("p");
      p.textContent = data.summary;
      body.appendChild(p);
    }

    addSection("Top products", data.top_products);
    addSection("Slow movers", data.slow_products);
    addSection("Recommendations", data.recommendations);
    addSection("Watch out for", data.warnings, "ai-warnings");
  }

  generateBtn.addEventListener("click", async () => {
    const originalLabel = generateBtn.textContent;
    generateBtn.disabled = true;
    generateBtn.textContent = "Thinking…";
    clearBody();
    addHint("Analyzing this month's sales…");

    try {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
      const res = await fetch("/api/ai-insights/generate", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Request failed");
      }
      renderInsight(data);
      generateBtn.textContent = "Regenerate report";
    } catch (err) {
      clearBody();
      addHint("Could not generate a report: " + err.message);
      generateBtn.textContent = originalLabel;
    } finally {
      generateBtn.disabled = false;
    }
  });
})();
