(() => {
  "use strict";

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

    function updateStage() {
      scrollQueued = false;
      const nearest = stages.reduce((current, stage, index) => (
        Math.abs(stageLeft(index) - track.scrollLeft) < Math.abs(stageLeft(current) - track.scrollLeft)
          ? index
          : current
      ), 0);
      if (nearest === active) return;
      active = nearest;
      position.textContent = `Stage ${active + 1} of ${stages.length}`;
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
    updateStage();
  });
})();
