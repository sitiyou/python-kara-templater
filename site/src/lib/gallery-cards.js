function setupComponentNavigation(grid, signal) {
  const nav = grid.querySelector(".component-index");
  if (!nav) return;

  const toolbar = grid.querySelector(".gallery-toolbar");
  const picker = grid.querySelector("kara-dropdown");
  const pickerMenu = picker.querySelector(".site-dropdown-menu");
  const searchLabel = grid.querySelector(".component-search");
  const search = searchLabel.querySelector("input");
  const status = grid.querySelector(".component-results");
  const motion = toolbar.querySelector("[data-motion]");
  const links = nav.querySelectorAll("a");
  const groups = [...grid.querySelectorAll(".component-section")].map((section) => {
    const id = section.getAttribute("aria-labelledby");
    const category = document.getElementById(id).textContent;
    const cards = [...section.querySelectorAll(".gallery-card")].map((card) => ({
      card,
      terms: `${category} ${card.id} ${card.textContent}`.toLowerCase(),
      animated: Boolean(card.querySelector("video")),
    }));
    return {id, section, cards};
  });

  function update(scroll = false) {
    const target = document.getElementById(location.hash.slice(1));
    const match = target?.closest(".component-section");
    const selected = match ?? groups[0].section;
    const category = selected.getAttribute("aria-labelledby");
    const query = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const searching = query.length > 0;
    let count = 0;
    let canPlay = false;
    for (const {section, cards} of groups) {
      const inCategory = section === selected;
      let matches = 0;
      for (const {card, terms, animated} of cards) {
        const visible = searching ? query.every((term) => terms.includes(term)) : inCategory;
        card.hidden = !visible;
        matches += Number(visible);
        canPlay ||= visible && animated;
      }
      section.hidden = matches === 0;
      count += matches;
    }
    for (const link of links) {
      if (!searching && link.hash === `#${category}`) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
    picker.dataset.value = category;
    status.textContent = !searching ? "" :
      count ? status.dataset.matches.replace("{count}", count) : status.dataset.empty;
    motion.hidden = !canPlay;
    if (scroll && match) target.scrollIntoView();
  }

  searchLabel.hidden = false;
  picker.hidden = false;
  function measureToolbar() {
    grid.style.setProperty("--component-toolbar-height", `${toolbar.offsetHeight}px`);
  }
  measureToolbar();
  const resize = new ResizeObserver(measureToolbar);
  resize.observe(toolbar);
  signal.addEventListener("abort", () => resize.disconnect(), {once: true});
  search.addEventListener("input", () => update(), {signal});
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a") && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      search.value = "";
      update();
    }
  }, {signal});
  pickerMenu.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    search.value = "";
    if (location.hash === link.hash) update(true);
    else location.hash = link.hash;
  }, {signal});
  window.addEventListener("hashchange", () => {
    picker.close?.();
    search.value = "";
    update(true);
  }, {signal});
  update(true);
}

class GalleryCards extends HTMLElement {
  connectedCallback() {
    this.lifecycle = new AbortController();
    const {signal} = this.lifecycle;

    const filters = this.querySelector(".gallery-filters");
    const cards = [...this.querySelectorAll("[data-category]")];
    const motion = this.querySelector("[data-motion]");
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    let autoplay = !preference.matches;
    const previews = new Map();

    function setPlayback(preview) {
      const {video, visible, intent} = preview;
      if (preview.failed || document.hidden || !visible || video.closest("[hidden]") || !(intent ?? autoplay)) {
        video.pause();
        return;
      }
      if (!video.src) video.src = video.dataset.src;
      // A blocked automatic play leaves the poster and manual control available.
      video.play().catch(() => {});
    }

    function setAutoplay(active) {
      autoplay = active;
      motion.textContent = active ? motion.dataset.pause : motion.dataset.play;
      for (const preview of previews.values()) {
        preview.intent = undefined;
        setPlayback(preview);
      }
    }

    motion.hidden = false;
    setupComponentNavigation(this, signal);
    motion.addEventListener("click", () => setAutoplay(!autoplay), {signal});
    preference.addEventListener("change", () => setAutoplay(!preference.matches), {signal});
    document.addEventListener("visibilitychange", () => {
      for (const preview of previews.values()) setPlayback(preview);
    }, {signal});

    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const preview = previews.get(entry.target);
        preview.visible = entry.isIntersecting && entry.intersectionRatio >= 0.4;
        setPlayback(preview);
      }
    }, {threshold: 0.4});

    for (const element of this.querySelectorAll(".card-preview")) {
      const video = element.querySelector("video");
      if (!video) continue;
      const button = element.querySelector("button");
      const preview = {video, visible: false, intent: undefined, failed: false};
      previews.set(element, preview);
      function updateButton(playing) {
        const label = playing ? button.dataset.pause : button.dataset.play;
        button.setAttribute("aria-label", label);
        button.setAttribute("aria-pressed", String(playing));
        button.title = label;
      }
      updateButton(false);
      button.hidden = false;
      button.addEventListener("click", () => {
        preview.intent = video.paused;
        if (preview.intent) {
          if (!video.src) video.src = video.dataset.src;
          video.play().catch(() => {});
        } else {
          video.pause();
        }
      }, {signal});
      video.addEventListener("playing", () => {
        element.dataset.started = "";
        updateButton(true);
      }, {signal});
      video.addEventListener("pause", () => updateButton(false), {signal});
      video.addEventListener("error", () => {
        preview.failed = true;
        delete element.dataset.started;
        button.hidden = true;
      }, {signal});
      observer.observe(element);
    }
    setAutoplay(autoplay);

    if (filters) {
      filters.hidden = false;
      filters.addEventListener("click", (event) => {
        const button = event.target.closest("[data-filter]");
        if (!button) return;
        const category = button.dataset.filter;
        for (const item of filters.querySelectorAll("button")) {
          item.setAttribute("aria-pressed", String(item === button));
        }
        for (const card of cards) {
          card.hidden = category !== "All" && card.dataset.category !== category;
          if (card.hidden) {
            const preview = previews.get(card.querySelector(".card-preview"));
            preview.visible = false;
            preview.video.pause();
          }
        }
      }, {signal});
    }

    signal.addEventListener("abort", () => {
      observer.disconnect();
      for (const {video} of previews.values()) video.pause();
    }, {once: true});
  }

  disconnectedCallback() {
    this.lifecycle?.abort();
  }
}

customElements.define("kara-gallery", GalleryCards);
