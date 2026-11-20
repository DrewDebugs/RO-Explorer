/* RO Desalination Explorer — decorative ocean effects (no physics here).
 *
 * - Bubble trail behind the mouse pointer, and a ripple + bubble burst on click.
 * - Sections float up into view as they scroll in.
 * Everything is skipped for users who prefer reduced motion; the pointer
 * effects only run for a mouse (fine pointer), not on touch screens.
 */
"use strict";

(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;
  const root = document.documentElement;

  // ------------------------------------------------------------ scroll reveal
  if (!reduceMotion && "IntersectionObserver" in window) {
    root.classList.add("js-reveal");
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      }
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    document.addEventListener("DOMContentLoaded", () => {
      document.querySelectorAll("main section").forEach((s) => io.observe(s));
    });
  }

  if (reduceMotion || !finePointer) return;

  // ------------------------------------------------------------ bubble cursor
  root.classList.add("bubble-cursor");
  const layer = document.createElement("div");
  layer.className = "cursor-layer";
  layer.setAttribute("aria-hidden", "true");
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(layer));

  const MAX_BUBBLES = 45;
  const rand = (a, b) => a + Math.random() * (b - a);

  function bubble(x, y, size, rise, drift, dur) {
    if (layer.childElementCount >= MAX_BUBBLES) return;
    const b = document.createElement("span");
    b.className = "cursor-bubble";
    b.style.left = `${x}px`;
    b.style.top = `${y}px`;
    b.style.width = b.style.height = `${size}px`;
    b.style.setProperty("--rise", `${-rise}px`);
    b.style.setProperty("--drift", `${drift}px`);
    b.style.animationDuration = `${dur}s`;
    b.addEventListener("animationend", () => b.remove(), { once: true });
    layer.appendChild(b);
  }

  let last = 0, lx = 0, ly = 0;
  window.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    const now = performance.now();
    const moved = Math.hypot(e.clientX - lx, e.clientY - ly);
    if (now - last < 40 || moved < 8) return;
    last = now; lx = e.clientX; ly = e.clientY;
    bubble(e.clientX + rand(-6, 6), e.clientY + rand(-4, 8), rand(5, 13), rand(50, 110), rand(-18, 18), rand(1.1, 1.9));
  }, { passive: true });

  window.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse") return;
    const r = document.createElement("span");
    r.className = "cursor-ripple";
    r.style.left = `${e.clientX}px`;
    r.style.top = `${e.clientY}px`;
    r.addEventListener("animationend", () => r.remove(), { once: true });
    layer.appendChild(r);
    for (let i = 0; i < 7; i++) {
      bubble(e.clientX + rand(-10, 10), e.clientY + rand(-6, 6), rand(4, 11), rand(70, 150), rand(-35, 35), rand(1.0, 1.8));
    }
  }, { passive: true });
})();
