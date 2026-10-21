// Streamlit owns the UI. This small presentation layer adds focus/inert state
// to named containers and cleans it up on every tutorial transition.
const host = window.parent;
const doc = host.document;
if (host.nightjarTourCleanup) host.nightjarTourCleanup();
let observer, resizer, frame, viewportFrame, missingTimer, missingNotice, stopped = false;
const restricted = new Map();
let highlighted = null;
const signature = JSON.stringify(tour);
const needsFocus = host.nightjarTourSignature !== signature;
host.nightjarTourSignature = signature;
let focused = false;

function releasePresentation() {
  restricted.forEach((wasInert, node) => { node.inert = wasInert; });
  restricted.clear();
  highlighted?.classList.remove("nj-tour-target");
  highlighted = null;
  if (missingTimer) host.clearTimeout(missingTimer);
  missingTimer = null;
  missingNotice?.remove();
  missingNotice = null;
  doc.documentElement.removeAttribute("data-nightjar-tour");
}

function clear() {
  stopped = true;
  observer?.disconnect();
  resizer?.disconnect();
  host.removeEventListener("resize", onViewportResize);
  if (frame) host.cancelAnimationFrame(frame);
  if (viewportFrame) host.cancelAnimationFrame(viewportFrame);
  releasePresentation();
}
host.nightjarTourCleanup = clear;

function visibleTopReserve(guide, destination) {
  const bar = doc.querySelector(".st-key-topbar");
  const wrapper = doc.querySelector('[data-testid="stLayoutWrapper"]:has(>.st-key-demo_slot)');
  const sticky = wrapper && host.getComputedStyle(wrapper).position === "sticky";
  return (bar?.getBoundingClientRect().height || 0)
    + (tour.mode === "act" && sticky && !guide.contains(destination)
      ? guide.getBoundingClientRect().height + 24 : 0) + 22;
}

function onViewportResize() {
  if (viewportFrame) host.cancelAnimationFrame(viewportFrame);
  viewportFrame = host.requestAnimationFrame(() => {
    apply();
    const guide = doc.querySelector(".st-key-guided_demo");
    const main = doc.querySelector('[data-testid="stMain"]');
    const active = doc.activeElement;
    // Keep a focused control visible when switching between sticky desktop
    // and flowing phone/short-screen layouts, without stealing focus or
    // scrolling someone who has moved on to another part of the page.
    if (stopped || !guide || !main || !highlighted?.contains(active)) return;
    const reserve = visibleTopReserve(guide, active);
    const rect = active.getBoundingClientRect();
    const bounds = main.getBoundingClientRect();
    if (rect.top < bounds.top + reserve || rect.bottom > bounds.bottom - 16) {
      const top = rect.top - bounds.top + main.scrollTop - reserve;
      main.scrollTo({top: Math.max(0, top), behavior: "instant"});
    }
  });
}

function apply() {
  if (stopped) return;
  // If the guide was removed by navigation or a failed render, never leave
  // the app locked. The next Streamlit render re-establishes the guide.
  const guide = doc.querySelector(".st-key-guided_demo");
  if (!tour || !guide) {
    releasePresentation();
    return;
  }
  doc.documentElement.setAttribute("data-nightjar-tour", tour.mode);
  const bar = doc.querySelector(".st-key-topbar");
  doc.documentElement.style.setProperty("--nj-nav-height",
    `${bar?.getBoundingClientRect().height || 0}px`);
  doc.querySelectorAll('[class*="st-key-page_"], .st-key-topbar').forEach(node => {
    if (!restricted.has(node)) restricted.set(node, node.inert);
    node.inert = tour.mode === "explain" || restricted.get(node);
  });
  const target = tour.mode === "act" && tour.target ? doc.querySelector(tour.target) : null;
  if (highlighted !== target) {
    highlighted?.classList.remove("nj-tour-target");
    highlighted = target;
  }
  target?.classList.add("nj-tour-target");
  if (tour.mode === "act" && tour.target && !target) {
    // Streamlit can replace the route in several DOM updates. Wait before
    // explaining a genuinely unavailable target; navigation remains usable.
    if (!missingTimer && !missingNotice) {
      missingTimer = host.setTimeout(() => {
        missingTimer = null;
        if (stopped || !guide.isConnected || doc.querySelector(tour.target)) return;
        missingNotice = doc.createElement("p");
        missingNotice.className = "nj-tour-status";
        missingNotice.setAttribute("role", "status");
        missingNotice.textContent = "This action is not visible yet. Read this step again, or use Skip to explore the complete example.";
        guide.appendChild(missingNotice);
      }, 1200);
    }
  } else {
    if (missingTimer) host.clearTimeout(missingTimer);
    missingTimer = null;
    missingNotice?.remove();
    missingNotice = null;
  }
  if (!needsFocus || focused) return;
  const destination = tour.mode === "explain"
    ? guide.querySelector("h3") || guide
    : target;
  if (!destination) return;
  focused = true;
  host.requestAnimationFrame(() => host.requestAnimationFrame(() => {
    if (stopped || !destination.isConnected) return;
    const control = tour.mode === "act"
      ? destination.querySelector('button:not(:disabled), input:not(:disabled), [role="slider"], [role="combobox"]')
      : destination;
    const focusNode = control || destination;
    if (!focusNode.hasAttribute("tabindex") && !focusNode.matches("button,input"))
      focusNode.setAttribute("tabindex", "-1");
    focusNode.focus({preventScroll: true});
    const main = doc.querySelector('[data-testid="stMain"]');
    if (main) {
      // The guide stays in view above the highlighted action on desktop.
      // On short phone screens it is in normal flow, leaving room for controls.
      const reserve = visibleTopReserve(guide, destination);
      const top = destination.getBoundingClientRect().top
        - main.getBoundingClientRect().top + main.scrollTop - reserve;
      main.scrollTo({top: tour.mode === "explain" ? 0 : Math.max(0, top), behavior: "instant"});
    }
  }));
}
observer = new host.MutationObserver(() => {
  if (frame) host.cancelAnimationFrame(frame);
  frame = host.requestAnimationFrame(apply);
});
observer.observe(doc.body, {childList: true, subtree: true});
resizer = new host.ResizeObserver(apply);
resizer.observe(doc.documentElement);
host.addEventListener("resize", onViewportResize);
apply();
