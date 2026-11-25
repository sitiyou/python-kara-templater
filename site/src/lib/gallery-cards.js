import {createContext, loadPreview} from "./preview-renderer";

class GalleryCards extends HTMLElement {
  connectedCallback() {
    const lifecycle = new AbortController();
    this.lifecycle = lifecycle;
    const {signal} = lifecycle;
    const filters = this.querySelector(".gallery-filters");
    const buttons = [...filters.querySelectorAll("button")];
    const cards = [...this.querySelectorAll("[data-category]")];
    const status = this.querySelector(".gallery-status");
    const errorText =
      this.dataset.errorText ||
      "Some preview images are unavailable. The example pages and source are still accessible.";
    filters.hidden = false;

    filters.addEventListener(
      "click",
      (event) => {
        const button = event.target.closest("[data-filter]");
        if (!button) return;
        const category = button.dataset.filter;
        for (const item of buttons) {
          item.setAttribute("aria-pressed", String(item === button));
        }
        for (const card of cards) {
          card.hidden = category !== "All" && card.dataset.category !== category;
        }
      },
      {signal},
    );

    const canvas = document.createElement("canvas");
    let gl;
    let queue = Promise.resolve();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const {target, isIntersecting} of entries) {
          if (!isIntersecting) continue;
          observer.unobserve(target);
          queue = queue.then(async () => {
            if (signal.aborted) return;
            try {
              gl ??= createContext(canvas);
              canvas.width = 480;
              canvas.height = Math.round(
                (canvas.width * Number(target.dataset.height)) / Number(target.dataset.width),
              );
              const scene = await loadPreview(gl, target.dataset.resources, signal);
              try {
                scene.draw(Math.round(Number(target.dataset.still) * scene.fps));
                const image = target.querySelector("img");
                image.src = canvas.toDataURL();
                image.hidden = false;
              } finally {
                scene.dispose();
              }
            } catch (error) {
              if (signal.aborted) return;
              console.warn(error);
              status.textContent = errorText;
              status.hidden = false;
              if (!gl) observer.disconnect();
            }
          });
        }
      },
      {rootMargin: "120px"},
    );

    signal.addEventListener(
      "abort",
      () => {
        observer.disconnect();
        gl?.getExtension("WEBGL_lose_context")?.loseContext();
      },
      {once: true},
    );
    for (const card of this.querySelectorAll(".gallery-still")) observer.observe(card);
  }

  disconnectedCallback() {
    this.lifecycle?.abort();
  }
}

customElements.define("kara-gallery", GalleryCards);
