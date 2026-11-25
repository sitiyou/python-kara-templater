import {createContext, loadPreview} from "./preview-renderer";

function rgbToHex(rgb) {
  return "#" + rgb.map((n) => Math.round(n * 255).toString(16).padStart(2, "0")).join("");
}

function hexToRgb(hex) {
  return hex.slice(1).match(/../g).map((channel) => parseInt(channel, 16) / 255);
}

class LivePreview extends HTMLElement {
  connectedCallback() {
    this.gl = null;
    this.startSession();
  }

  disconnectedCallback() {
    this.lifecycle?.abort();
    this.gl?.getExtension("WEBGL_lose_context")?.loseContext();
    this.gl = null;
  }

  reloadDemo({resources, still, width, height, accent, title}) {
    this.dataset.resources = resources;
    this.dataset.still = String(still);
    if (accent) this.style.setProperty("--sample-accent", accent);
    const canvas = this.querySelector("canvas");
    if (canvas) {
      if (width) canvas.width = width;
      if (height) canvas.height = height;
      if (title) canvas.setAttribute("aria-label", title);
    }
    this.startSession();
  }

  startSession() {
    this.lifecycle?.abort();
    this.lifecycle = new AbortController();
    this.initialize(this.lifecycle.signal);
  }

  async initialize(signal) {
    const status = this.querySelector(".preview-status");
    const canvas = this.querySelector("canvas");
    const controls = this.querySelector(".preview-controls");
    const button = this.querySelector(".preview-play");
    const seek = this.querySelector(".preview-time");
    const position = this.querySelector(".preview-position");
    const parameters = this.querySelector(".preview-parameters");
    const resetButton = this.querySelector(".preview-reset");

    const playText = this.dataset.play || "Play";
    const pauseText = this.dataset.pause || "Pause";
    const unavailableText =
      this.dataset.unavailable ||
      "The live preview is unavailable. You can still read or download the example.";
    const secondsUnit = this.dataset.seconds || "s";

    status.hidden = false;
    let scene;
    let frame = 0;
    let animation = 0;

    function setPlaying(active) {
      const label = active ? pauseText : playText;
      button.setAttribute("aria-pressed", String(active));
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    }

    function pause() {
      cancelAnimationFrame(animation);
      animation = 0;
      setPlaying(false);
    }

    function report(error) {
      if (signal.aborted) return;
      pause();
      console.warn(error);
      status.textContent = unavailableText;
      status.hidden = false;
      controls.hidden = true;
      if (parameters) parameters.hidden = true;
    }

    signal.addEventListener(
      "abort",
      () => {
        pause();
        scene?.dispose();
      },
      {once: true},
    );
    canvas.addEventListener(
      "webglcontextlost",
      () => {
        this.gl = null;
        report(new Error("Preview WebGL context lost."));
      },
      {signal},
    );

    try {
      this.gl ??= createContext(canvas);
      scene = await loadPreview(this.gl, this.dataset.resources, signal);
      signal.throwIfAborted();
      const {fps, frames} = scene;
      const duration = frames / fps;

      function draw(next) {
        frame = next;
        scene.draw(frame);
        seek.value = String(frame);
        const pct = frames > 1 ? (frame / (frames - 1)) * 100 : 0;
        seek.style.setProperty("--progress", `${pct.toFixed(2)}%`);
        const time = (frame / fps).toFixed(2);
        seek.setAttribute("aria-valuetext", `${time}${secondsUnit}`);
        position.textContent = `${time} / ${duration.toFixed(2)}${secondsUnit}`;
      }

      function play() {
        const start = performance.now() - (frame * 1000) / fps;
        setPlaying(true);
        function tick(now) {
          const next = Math.max(0, Math.floor(((now - start) * fps) / 1000)) % frames;
          if (next !== frame) draw(next);
          animation = requestAnimationFrame(tick);
        }
        animation = requestAnimationFrame(tick);
      }

      const toggle = () => (animation ? pause() : play());
      button.addEventListener("click", toggle, {signal});
      canvas.addEventListener("click", toggle, {signal});
      document.addEventListener(
        "visibilitychange",
        () => {
          if (document.hidden) pause();
        },
        {signal},
      );
      seek.addEventListener(
        "input",
        () => {
          pause();
          draw(seek.valueAsNumber);
        },
        {signal},
      );

      if (parameters && scene.parameters.length) {
        const fields = parameters.querySelector(".preview-fields");
        fields.replaceChildren();
        const labels = JSON.parse(this.dataset.labels || "{}");
        const updaters = [];

        for (const slot of scene.parameters) {
          const field = document.createElement("label");
          field.className = "preview-field";
          const head = document.createElement("span");
          head.className = "preview-field-head";
          const name = document.createElement("span");
          name.className = "preview-field-name";
          name.textContent = labels[slot.name] ?? slot.name;
          const readout = document.createElement("output");
          readout.className = "preview-field-value";
          head.append(name, readout);

          const input = document.createElement("input");
          const setDefault = () => {
            if (slot.kind === "color") {
              const hex = rgbToHex(slot.defaults);
              input.value = hex;
              readout.textContent = hex.toUpperCase();
            } else {
              input.value = String(slot.defaults[0]);
              readout.textContent = Number(slot.defaults[0]).toFixed(2);
            }
            scene.setParameter(slot, slot.defaults);
          };

          if (slot.kind === "color") {
            input.type = "color";
          } else {
            input.type = "range";
            input.min = String(Math.min(0, slot.defaults[0]));
            input.max = String(Math.max(1, slot.defaults[0]));
            input.step = "0.01";
          }
          setDefault();

          input.addEventListener(
            "input",
            () => {
              const value =
                slot.kind === "color" ? hexToRgb(input.value) : [input.valueAsNumber];
              readout.textContent =
                slot.kind === "color"
                  ? input.value.toUpperCase()
                  : input.valueAsNumber.toFixed(2);
              scene.setParameter(slot, value);
              draw(frame);
              if (resetButton) resetButton.hidden = false;
            },
            {signal},
          );
          updaters.push(setDefault);
          field.append(head, input);
          fields.append(field);
        }

        if (resetButton) {
          resetButton.hidden = true;
          resetButton.addEventListener(
            "click",
            () => {
              for (const fn of updaters) fn();
              draw(frame);
              resetButton.hidden = true;
            },
            {signal},
          );
        }
        parameters.hidden = false;
      } else if (parameters) {
        parameters.hidden = true;
      }

      seek.max = String(frames - 1);
      draw(Math.min(frames - 1, Math.round(Number(this.dataset.still) * fps)));
      controls.hidden = false;
      status.hidden = true;
    } catch (error) {
      report(error);
    }
  }
}

customElements.define("kara-preview", LivePreview);
