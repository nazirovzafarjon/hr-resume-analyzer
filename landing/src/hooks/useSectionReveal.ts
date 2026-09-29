import { useEffect } from "react";

/**
 * Subtle entrance for `[data-reveal]` content: each <section> gets
 * `is-visible` the first time it scrolls into view, and CSS fades its
 * revealable children in. Observing sections (not the children) keeps content
 * visible when a language switch re-renders the lists inside them.
 *
 * Skipped entirely for reduced-motion users or when IntersectionObserver is
 * missing — content is then simply shown.
 */
export function useSectionReveal() {
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !("IntersectionObserver" in window)) return;

    const root = document.documentElement;
    root.classList.add("reveal-ready");

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    document.querySelectorAll("main section").forEach((section) => observer.observe(section));

    return () => {
      observer.disconnect();
      root.classList.remove("reveal-ready");
    };
  }, []);
}
