// YOUtopia docs: scroll reveals and a gentle pointer parallax on the homepage hero.
// Everything here is decorative; the pages read fine without it.
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function reveal() {
    const targets = document.querySelectorAll(".yt-reveal:not(.is-visible)");
    if (reduceMotion.matches || !("IntersectionObserver" in window)) {
      targets.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.2 },
    );
    targets.forEach((el) => observer.observe(el));
  }

  function parallax() {
    const hero = document.querySelector(".yt-hero");
    if (!hero || reduceMotion.matches || hero.dataset.ytParallax) return;
    hero.dataset.ytParallax = "on";
    hero.addEventListener("pointermove", (event) => {
      const box = hero.getBoundingClientRect();
      hero.style.setProperty("--yt-px", ((event.clientX - box.left) / box.width - 0.5).toFixed(3));
      hero.style.setProperty("--yt-py", ((event.clientY - box.top) / box.height - 0.5).toFixed(3));
    });
    hero.addEventListener("pointerleave", () => {
      hero.style.setProperty("--yt-px", "0");
      hero.style.setProperty("--yt-py", "0");
    });
  }

  // Hero headline: show "takes", delete it letter by letter, then type "makes".
  // Without JS, or with reduced motion, the final word is shown from the start.
  function retype() {
    const el = document.querySelector(".yt-retype");
    if (!el || reduceMotion.matches || el.dataset.ytRetype) return;
    el.dataset.ytRetype = "on";
    const from = el.dataset.from;
    const to = el.dataset.to;
    const wait = (ms) => new Promise((done) => setTimeout(done, ms));
    (async () => {
      el.textContent = from;
      el.classList.add("is-typing");
      await wait(1400);
      for (let i = from.length - 1; i >= 0; i--) {
        el.textContent = from.slice(0, i);
        await wait(90);
      }
      await wait(350);
      for (let i = 1; i <= to.length; i++) {
        el.textContent = to.slice(0, i);
        await wait(130);
      }
      await wait(1200);
      el.classList.remove("is-typing");
    })();
  }

  // Full-width sections need the page width without the scrollbar. Browsers disagree on
  // whether 100vw includes it, so measure it.
  function measureWidth() {
    const root = document.documentElement;
    root.style.setProperty("--yt-vw", `${root.clientWidth}px`);
  }

  window.addEventListener("resize", measureWidth);

  function init() {
    document.documentElement.classList.add("yt-js");
    measureWidth();
    reveal();
    parallax();
    retype();
  }

  // With instant navigation, document$ emits on every page load.
  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
