(() => {
  "use strict";

  const menuButton = document.querySelector(".menu-toggle");
  const navigation = document.querySelector(".site-nav");
  if (menuButton && navigation) {
    const closeMenu = () => {
      menuButton.setAttribute("aria-expanded", "false");
      navigation.classList.remove("is-open");
    };
    menuButton.addEventListener("click", () => {
      const open = menuButton.getAttribute("aria-expanded") !== "true";
      menuButton.setAttribute("aria-expanded", String(open));
      navigation.classList.toggle("is-open", open);
    });
    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a")) closeMenu();
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 1050) closeMenu();
    });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const revealGroups = [
    ".section-heading",
    ".step-grid > li",
    ".data-layer-cards > article",
    ".score-copy",
    ".score-bands",
    ".explain-flow",
    ".principle-card",
    ".limitation-grid > span",
    ".pwa-section > div",
    ".faq-list > details",
    ".final-cta-inner"
  ];
  const revealItems = [...document.querySelectorAll(revealGroups.join(","))];

  if (!reducedMotion.matches && "IntersectionObserver" in window && revealItems.length) {
    document.documentElement.classList.add("reveal-enabled");
    revealItems.forEach((item, index) => {
      item.classList.add("reveal-item");
      item.style.setProperty("--reveal-delay", `${(index % 4) * 70}ms`);
    });

    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8%", threshold: 0.12 });

    revealItems.forEach((item) => revealObserver.observe(item));
  }
})();
