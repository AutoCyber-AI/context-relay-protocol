// Auto-rotating announcement ticker for the CRP Material site.
// Re-initialises on every Material instant-navigation page change via document$.
(function () {
  "use strict";

  const messages = [
    { icon: "✅", text: "<strong>3,482 tests passing</strong> — ruff and mypy at zero errors", href: "/testing/", cta: "See test suite →" },
    { icon: "🖥️", text: "<strong>Live agent console</strong> — console.crprotocol.io or self-hosted; connect any local backend", href: "https://console.crprotocol.io", cta: "Open console →" },
    { icon: "🧠", text: "<strong>Reasoning, safeguards &amp; emotions in one preset file</strong> — enforced, not prompted", href: "https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/docs/CRPv6_COGNITIVE_PRESETS_GUIDE.md", cta: "Preset guide →" },
    { icon: "🔐", text: "<strong>Every answer carries an HMAC provenance chain</strong> your auditors can verify", href: "/control-evidence/", cta: "See the evidence →" },
    { icon: "🏠", text: "<strong>Works with local models via LM Studio / Ollama</strong> — your data never leaves the machine", href: "/getting-started/local-models/", cta: "Run local →" },
    { icon: "⚡", text: "<strong>Get started in 5 minutes</strong> — run your first governed agent", href: "/getting-started/quickstart/", cta: "Get started →" },
    { icon: "🛡️", text: "<strong>AI Safety</strong> — detect hallucinations, injections, and PII on every call", href: "/topics/ai-safety/", cta: "Explore →" },
    { icon: "🧠", text: "<strong>Context Management</strong> — unbounded context and automatic continuation", href: "/topics/context-management/", cta: "Explore →" },
    { icon: "✅", text: "<strong>Conformance &amp; certification</strong> — validate CRP implementations", href: "/protocol/conformance/", cta: "Get certified →" },
    { icon: "❓", text: "<strong>Have questions?</strong> — browse the CRP FAQ", href: "/faq/", cta: "Read FAQ →" },
    { icon: "⭐", text: "<strong>Star us on GitHub</strong> — follow CRP development", href: "https://github.com/AutoCyber-AI/context-relay-protocol", cta: "Open repo →" }
  ];

  const INTERVAL = 6000;

  function stripHtml(html) {
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || "";
  }

  function initTicker() {
    const announce = document.querySelector(".crp-announce");
    if (!announce) return;

    // Avoid binding twice on the same element.
    if (announce.dataset.crpTickerBound === "1") return;
    announce.dataset.crpTickerBound = "1";

    const link = announce.querySelector("#crp-ticker-link");
    const icon = announce.querySelector("#crp-ticker-icon");
    const text = announce.querySelector("#crp-ticker-text");
    const cta = announce.querySelector(".crp-announce-cta");
    const prevBtn = announce.querySelector("#crp-ticker-prev");
    const nextBtn = announce.querySelector("#crp-ticker-next");
    const pauseBtn = announce.querySelector("#crp-ticker-pause");
    const controls = announce.querySelector(".crp-announce-controls");
    const progressWrap = announce.querySelector(".crp-announce-progress");
    let progressBar = announce.querySelector("#crp-ticker-progress");

    if (!link || !icon || !text || !cta || !controls) return;

    let index = 0;
    let timer = null;
    let resumeTimer = null;
    let paused = false;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function restartProgress() {
      if (reducedMotion || messages.length <= 1) return;
      if (!progressBar) return;
      const newBar = progressBar.cloneNode(true);
      progressBar.parentNode.replaceChild(newBar, progressBar);
      progressBar = newBar;
    }

    function setProgressPaused(isPaused) {
      if (progressWrap) progressWrap.classList.toggle("paused", isPaused);
    }

    function render(i) {
      const m = messages[i];
      link.style.opacity = "0.7";
      setTimeout(function () {
        link.href = m.href;
        icon.textContent = m.icon;
        text.innerHTML = m.text;
        cta.textContent = m.cta;
        link.setAttribute("aria-label", stripHtml(m.text) + ". " + stripHtml(m.cta));
        link.style.opacity = "1";
        updateDots();
        restartProgress();
      }, 180);
    }

    function next() {
      index = (index + 1) % messages.length;
      render(index);
    }

    function prev() {
      index = (index - 1 + messages.length) % messages.length;
      render(index);
    }

    function goTo(i) {
      index = i % messages.length;
      render(index);
    }

    function updatePauseButton() {
      pauseBtn.setAttribute("aria-pressed", paused ? "true" : "false");
      pauseBtn.setAttribute("aria-label", paused ? "Play announcements" : "Pause announcements");
      pauseBtn.textContent = paused ? "▶" : "⏸";
      setProgressPaused(paused);
    }

    function stop() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      setProgressPaused(true);
    }

    function start() {
      if (paused || reducedMotion || messages.length <= 1) return;
      stop();
      clearTimeout(resumeTimer);
      resumeTimer = null;
      timer = setInterval(next, INTERVAL);
      setProgressPaused(false);
    }

    function scheduleResume() {
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(function () {
        paused = false;
        updatePauseButton();
        start();
      }, 8000);
    }

    function manualStep(stepFn) {
      stop();
      paused = true;
      updatePauseButton();
      stepFn();
      scheduleResume();
    }

    function togglePause() {
      paused = !paused;
      updatePauseButton();
      if (paused) {
        stop();
      } else {
        clearTimeout(resumeTimer);
        start();
      }
    }

    // Build dot indicators if they don't already exist
    let dots = announce.querySelector(".crp-announce-dots");
    if (!dots) {
      dots = document.createElement("span");
      dots.className = "crp-announce-dots";
      dots.setAttribute("aria-hidden", "true");
      messages.forEach(function (_, i) {
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.title = "Announcement " + (i + 1);
        dot.addEventListener("click", function () { manualStep(function () { goTo(i); }); });
        dots.appendChild(dot);
      });
      controls.insertBefore(dots, prevBtn);
    }

    function updateDots() {
      dots.querySelectorAll(".dot").forEach(function (dot, i) {
        dot.classList.toggle("active", i === index);
      });
    }

    announce.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { e.preventDefault(); manualStep(prev); }
      if (e.key === "ArrowRight") { e.preventDefault(); manualStep(next); }
    });

    let touchStartX = 0;
    let touchEndX = 0;
    const swipeThreshold = 40;
    announce.addEventListener("touchstart", function (e) {
      touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });
    announce.addEventListener("touchend", function (e) {
      touchEndX = e.changedTouches[0].screenX;
      const diff = touchEndX - touchStartX;
      if (Math.abs(diff) > swipeThreshold) {
        manualStep(diff < 0 ? next : prev);
      }
    }, { passive: true });

    announce.addEventListener("mouseenter", stop);
    announce.addEventListener("mouseleave", start);
    announce.addEventListener("focusin", stop, true);
    announce.addEventListener("focusout", start, true);
    document.addEventListener("visibilitychange", function () {
      document.hidden ? stop() : start();
    });

    if (prevBtn) prevBtn.addEventListener("click", function () { manualStep(prev); });
    if (nextBtn) nextBtn.addEventListener("click", function () { manualStep(next); });
    if (pauseBtn) pauseBtn.addEventListener("click", togglePause);

    render(0);
    start();
  }

  // Material for MkDocs exposes document$ for instant-navigation lifecycle.
  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(initTicker);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTicker);
  } else {
    initTicker();
  }
})();
