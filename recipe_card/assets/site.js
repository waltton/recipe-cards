(() => {
  "use strict";

  const groceryCheckboxes = [...document.querySelectorAll("[data-grocery-id]")];
  if (groceryCheckboxes.length) {
    const recipeKey = window.location.pathname.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "");
    const cookieName = `recipe_cards_groceries_${recipeKey}`;
    const cookiePrefix = `${cookieName}=`;
    const storedCookie = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(cookiePrefix));
    const checkedIds = new Set(
      storedCookie
        ? decodeURIComponent(storedCookie.slice(cookiePrefix.length)).split(",").filter(Boolean)
        : []
    );

    groceryCheckboxes.forEach((checkbox) => {
      checkbox.checked = checkedIds.has(checkbox.dataset.groceryId);
      checkbox.addEventListener("change", () => {
        const selectedIds = groceryCheckboxes
          .filter((item) => item.checked)
          .map((item) => item.dataset.groceryId);
        document.cookie = `${cookieName}=${encodeURIComponent(selectedIds.join(","))}; Max-Age=31536000; Path=/; SameSite=Lax`;
      });
    });
  }

  const scalers = [...document.querySelectorAll(".diagram-scaler")];
  if (!scalers.length) return;

  document.documentElement.classList.add("diagram-fit-ready");

  function pixels(styles, name) {
    return Number.parseFloat(styles.getPropertyValue(name)) || 0;
  }

  function fitDiagram(scaler) {
    const diagram = scaler.querySelector(".recipe-diagram");
    const scroller = scaler.closest(".diagram-scroller");
    if (!diagram || !scroller) return;

    const diagramStyles = getComputedStyle(scaler);
    const scrollerStyles = getComputedStyle(scroller);
    const naturalWidth = pixels(diagramStyles, "--diagram-width");
    const naturalHeight = pixels(diagramStyles, "--diagram-height");
    const horizontalPadding = pixels(scrollerStyles, "padding-left") + pixels(scrollerStyles, "padding-right");
    const verticalPadding = pixels(scrollerStyles, "padding-top") + pixels(scrollerStyles, "padding-bottom");
    const availableWidth = Math.max(0, scroller.clientWidth - horizontalPadding);
    const availableHeight = Math.max(0, scroller.clientHeight - verticalPadding);
    const widthScale = naturalWidth > 0 ? availableWidth / naturalWidth : 1;
    const heightScale = naturalHeight > 0 ? availableHeight / naturalHeight : 1;
    const scale = Math.max(0, Math.min(heightScale, Math.max(1, widthScale)));

    diagram.style.transform = `scale(${scale})`;
    scaler.style.width = `${naturalWidth * scale}px`;
    scaler.style.height = `${naturalHeight * scale}px`;
    scaler.dataset.scale = String(scale);
  }

  let queued = false;
  function fitAll() {
    queued = false;
    scalers.forEach(fitDiagram);
  }

  function scheduleFit() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(fitAll);
  }

  const observer = new ResizeObserver(scheduleFit);
  scalers.forEach((scaler) => observer.observe(scaler.closest(".diagram-scroller")));
  window.addEventListener("orientationchange", scheduleFit);
  document.fonts?.ready.then(scheduleFit);
  scheduleFit();

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const mobileView = window.matchMedia("(max-width: 700px), (max-height: 520px) and (pointer: coarse)");
  document.querySelectorAll("[data-mobile-process]").forEach((process) => {
    const track = process.querySelector("[data-stage-track]");
    const stages = [...process.querySelectorAll(".mobile-stage")];
    const previous = process.querySelector("[data-stage-previous]");
    const next = process.querySelector("[data-stage-next]");
    const position = process.querySelector("[data-stage-position]");
    if (!track || !stages.length || !previous || !next || !position) return;

    let active = -1;
    let scrollQueued = false;

    function stageLeft(index) {
      return stages[index].offsetLeft - stages[0].offsetLeft;
    }

    function updateStageUrl(stageNumber) {
      if (!mobileView.matches) return;
      const url = new URL(window.location.href);
      url.hash = `stage-${stageNumber}`;
      history.replaceState(null, "", url);
    }

    function stageFromUrl() {
      const match = /^#stage-(\d+)$/.exec(window.location.hash);
      if (!match) return 0;
      const index = stages.findIndex((stage) => stage.dataset.stageNumber === match[1]);
      return index === -1 ? 0 : index;
    }

    function updateStage() {
      scrollQueued = false;
      const nearest = stages.reduce((current, stage, index) => (
        Math.abs(stageLeft(index) - track.scrollLeft) < Math.abs(stageLeft(current) - track.scrollLeft)
          ? index
          : current
      ), 0);
      if (nearest === active) return;
      active = nearest;
      const stageNumber = stages[active].dataset.stageNumber ?? String(active);
      const finalStageNumber = stages[stages.length - 1].dataset.stageNumber ?? String(stages.length - 1);
      position.textContent = `Stage ${stageNumber} of ${finalStageNumber}`;
      updateStageUrl(stageNumber);
      previous.disabled = active === 0;
      next.disabled = active === stages.length - 1;
      stages.forEach((stage, index) => {
        if (index === active) stage.setAttribute("aria-current", "step");
        else stage.removeAttribute("aria-current");
      });
    }

    function scheduleStageUpdate() {
      if (scrollQueued) return;
      scrollQueued = true;
      requestAnimationFrame(updateStage);
    }

    function goToStage(index) {
      const target = Math.max(0, Math.min(stages.length - 1, index));
      track.scrollTo({
        left: stageLeft(target),
        behavior: reduceMotion.matches ? "auto" : "smooth"
      });
    }

    previous.addEventListener("click", () => goToStage(active - 1));
    next.addEventListener("click", () => goToStage(active + 1));
    track.addEventListener("scroll", scheduleStageUpdate, {passive: true});
    window.addEventListener("resize", scheduleStageUpdate);
    if (mobileView.matches) track.scrollLeft = stageLeft(stageFromUrl());
    updateStage();
  });
})();
