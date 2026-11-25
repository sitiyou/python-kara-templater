class SiteDropdown extends HTMLElement {
  static observedAttributes = ["data-value"];

  connectedCallback() {
    this.lifecycle = new AbortController();
    const {signal} = this.lifecycle;
    const details = this.querySelector("details");
    const summary = this.querySelector("summary");
    const menu = this.querySelector(".site-dropdown-menu");
    const options = [...menu.querySelectorAll("[data-option]")];

    const updatePosition = () => {
      if (!details.open) return;
      const {top, bottom, left, right} = summary.getBoundingClientRect();
      const {clientWidth, clientHeight} = document.documentElement;
      const headerBottom = document.querySelector("header.header")?.getBoundingClientRect().bottom ?? 0;
      const below = clientHeight - bottom - 16;
      const above = top - headerBottom - 16;
      const openAbove = below < menu.scrollHeight && above > below;
      details.toggleAttribute("data-open-above", openAbove);
      menu.style.setProperty("--dropdown-height", `${Math.max(0, openAbove ? above : below)}px`);

      const width = menu.offsetWidth;
      const start = this.dataset.align === "end" ? right - width : left;
      const boundedStart = Math.max(8, Math.min(start, clientWidth - width - 8));
      menu.style.setProperty("--dropdown-offset", `${boundedStart - left}px`);
    };
    details.addEventListener("toggle", () => {
      if (!details.open) return;
      updatePosition();
      if (!menu.contains(document.activeElement)) {
        menu.querySelector("[data-selected]")?.scrollIntoView({block: "nearest"});
      }
    }, {signal});
    window.addEventListener("resize", updatePosition, {signal});
    window.addEventListener("scroll", updatePosition, {signal, passive: true, capture: true});
    document.addEventListener("pointerdown", (event) => {
      if (!this.contains(event.target)) this.close();
    }, {signal});
    details.addEventListener("focusout", (event) => {
      if (event.relatedTarget && !this.contains(event.relatedTarget)) this.close();
    }, {signal});
    menu.addEventListener("click", (event) => {
      if (event.target.closest("[data-option]") && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
        this.close(true);
      }
    }, {signal});
    details.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && details.open) {
        event.preventDefault();
        event.stopPropagation();
        this.close(true);
        return;
      }
      const arrows = event.key === "ArrowDown" || event.key === "ArrowUp";
      const boundary = event.key === "Home" || event.key === "End";
      if (!arrows && !(boundary && details.open)) return;
      event.preventDefault();
      details.open = true;
      updatePosition();
      const focused = options.indexOf(document.activeElement);
      let index;
      if (event.key === "Home") index = 0;
      else if (event.key === "End") index = options.length - 1;
      else if (focused < 0) index = event.key === "ArrowDown" ? 0 : options.length - 1;
      else index = (focused + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options[index].focus();
    }, {signal});
    this.updateSelection();
  }

  disconnectedCallback() {
    this.lifecycle?.abort();
  }

  attributeChangedCallback() {
    this.updateSelection();
  }

  close(restoreFocus = false) {
    const details = this.querySelector("details");
    if (!details?.open) return;
    details.open = false;
    if (restoreFocus) this.querySelector("summary").focus({preventScroll: true});
  }

  updateSelection() {
    const current = this.querySelector(".site-dropdown-current");
    for (const option of this.querySelectorAll("[data-option]")) {
      const selected = option.dataset.option === this.dataset.value;
      option.toggleAttribute("data-selected", selected);
      if (option instanceof HTMLButtonElement) {
        option.setAttribute("aria-pressed", String(selected));
      } else if (selected) {
        option.setAttribute("aria-current", this.dataset.variant === "field" ? "location" : "page");
      } else {
        option.removeAttribute("aria-current");
      }
      if (selected && current) current.textContent = option.querySelector(".site-dropdown-name").textContent;
    }
  }
}

customElements.define("kara-dropdown", SiteDropdown);
