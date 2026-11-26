const vertexSource = `#version 300 es
out vec2 uv;
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  uv = vec2(p.x, 1.0 - p.y);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const fragmentHeader = `#version 300 es
precision highp float;
precision highp int;
precision highp sampler2D;
in vec2 uv;
out vec4 pixel;
uniform sampler2D KARAMASK, KARADATA;
uniform float PTS;
#define HOOKED_pos uv
#define HOOKED_tex(p) vec4(0.0)
#define frame 1
`;

function createContext(canvas) {
  const gl = canvas.getContext("webgl2", {alpha: true, premultipliedAlpha: true, antialias: false});
  if (!gl) throw new Error("This browser could not start WebGL 2.");
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  return gl;
}

function makeShader(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("Could not allocate a preview shader.");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return shader;
}

function makeProgram(gl, fragment) {
  const program = gl.createProgram();
  if (!program) throw new Error("Could not allocate a preview program.");
  const shaders = [];
  try {
    shaders.push(makeShader(gl, gl.VERTEX_SHADER, vertexSource));
    shaders.push(makeShader(gl, gl.FRAGMENT_SHADER, fragment));
    for (const shader of shaders) gl.attachShader(program, shader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(shaders.map((shader) => gl.getShaderInfoLog(shader)).filter(Boolean).join("\n")
        || gl.getProgramInfoLog(program) || "Could not link the preview shader.");
    }
    return program;
  } catch (error) {
    gl.deleteProgram(program);
    throw error;
  } finally {
    for (const shader of shaders) gl.deleteShader(shader);
  }
}

function makeTexture(gl, size, data, isMask) {
  const [width, height] = size;
  const limit = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  const bytesPerTexel = isMask ? 1 : 16;
  if (width > limit || height > limit || data.byteLength !== width * height * bytesPerTexel) {
    throw new Error("Invalid or unsupported preview texture size.");
  }
  const texture = gl.createTexture();
  if (!texture) throw new Error("Could not allocate a preview texture.");
  gl.bindTexture(gl.TEXTURE_2D, texture);
  const filter = isMask ? gl.LINEAR : gl.NEAREST;
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  if (isMask) {
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, width, height, 0, gl.RED, gl.UNSIGNED_BYTE, new Uint8Array(data));
  } else {
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, width, height, 0, gl.RGBA, gl.FLOAT, new Float32Array(data));
  }
  if (gl.getError() !== gl.NO_ERROR) {
    gl.deleteTexture(texture);
    throw new Error("Could not upload a preview texture.");
  }
  return texture;
}

async function loadPreview(gl, base, signal) {
  async function resource(filename) {
    const response = await fetch(base + filename, {signal});
    if (!response.ok) throw new Error(`Could not load ${filename} (${response.status}).`);
    return response;
  }

  const [data, frag, mask, table] = await Promise.all([
    resource("textures.json").then((r) => r.json()),
    resource("scene.frag").then((r) => r.text()),
    resource("KARAMASK.bin").then((r) => r.arrayBuffer()),
    resource("KARADATA.bin").then((r) => r.arrayBuffer()),
  ]);
  signal?.throwIfAborted();
  return createPreview(gl, data, frag, mask, table);
}

function loadEmbeddedPreview(gl, element) {
  function resource(name) {
    return element.querySelector(`[data-preview-asset="${name}"]`).textContent;
  }

  function texture(name) {
    const encoded = resource(name);
    if (Uint8Array.fromBase64) return Uint8Array.fromBase64(encoded).buffer;
    const raw = atob(encoded);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes.buffer;
  }

  return createPreview(
    gl, JSON.parse(resource("manifest")), JSON.parse(resource("shader")),
    texture("mask"), texture("table"),
  );
}

function createPreview(gl, data, frag, mask, table) {
  const materialSlots = Object.entries(data.parameters ?? {});
  const uniforms = materialSlots.flatMap(([, slot]) => slot.uniforms)
    .map((name) => `uniform float ${name};`).join("\n");
  const program = makeProgram(gl, `${fragmentHeader}${uniforms}\n${frag}\nvoid main() { pixel = hook(); }`);
  const textures = [];
  function dispose() {
    for (const texture of textures) gl.deleteTexture(texture);
    gl.deleteProgram(program);
  }
  try {
    textures.push(makeTexture(gl, data.KARAMASK, mask, true));
    textures.push(makeTexture(gl, data.KARADATA, table, false));
    gl.useProgram(program);
    for (const [unit, name] of ["KARAMASK", "KARADATA"].entries()) {
      gl.uniform1i(gl.getUniformLocation(program, name), unit);
    }
    const timeLocation = gl.getUniformLocation(program, "PTS");
    const parameters = materialSlots.map(([name, slot]) => ({
      name,
      kind: slot.kind,
      defaults: slot.default,
      control: slot.control ?? {},
      locations: slot.uniforms.map((symbol) => gl.getUniformLocation(program, symbol)),
    }));
    function setParameter(slot, values) {
      gl.useProgram(program);
      for (const [index, location] of slot.locations.entries()) {
        gl.uniform1f(location, values[index]);
      }
    }
    for (const slot of parameters) setParameter(slot, slot.defaults);
    const [fps, firstFrame, frames] = data.clock;
    return {
      fps,
      frames,
      parameters,
      setParameter,
      dispose,
      draw(frame) {
        gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
        gl.useProgram(program);
        for (const [unit, texture] of textures.entries()) {
          gl.activeTexture(gl.TEXTURE0 + unit);
          gl.bindTexture(gl.TEXTURE_2D, texture);
        }
        gl.uniform1f(timeLocation, (firstFrame + frame) / fps);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      },
    };
  } catch (error) {
    dispose();
    throw error;
  }
}

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
      scene = this.dataset.resources
        ? await loadPreview(this.gl, this.dataset.resources, signal)
        : loadEmbeddedPreview(this.gl, this);
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

        const slots = [...scene.parameters].sort((a, b) =>
          (a.control.group || "").localeCompare(b.control.group || "")
          || (a.control.order ?? 0) - (b.control.order ?? 0));
        let currentGroup;
        for (const slot of slots) {
          if (slot.control.group && slot.control.group !== currentGroup) {
            currentGroup = slot.control.group;
            const heading = document.createElement("h3");
            heading.className = "preview-field-group";
            heading.textContent = currentGroup;
            fields.append(heading);
          }
          const label = labels[slot.name] ?? (slot.control.label || slot.name);
          const {bounds, step, unit} = slot.control;
          const readNumber = (value) => `${Number(value.toFixed(4))}${unit ? ` ${unit}` : ""}`;
          if (slot.kind === "vec2") {
            const field = document.createElement("fieldset");
            field.className = "preview-field";
            const legend = document.createElement("legend");
            legend.textContent = label;
            field.append(legend);
            const inputs = ["X", "Y"].map((axis) => {
              const axisLabel = document.createElement("label");
              axisLabel.textContent = axis;
              const input = document.createElement("input");
              input.type = "number";
              input.step = String(step ?? "any");
              if (bounds) [input.min, input.max] = bounds.map(String);
              input.setAttribute("aria-label", `${label} ${axis}`);
              axisLabel.append(input);
              field.append(axisLabel);
              return input;
            });
            const setDefault = () => {
              inputs.forEach((input, index) => (input.value = String(slot.defaults[index])));
              scene.setParameter(slot, slot.defaults);
            };
            setDefault();
            field.addEventListener("input", () => {
              const values = inputs.map((input) => input.valueAsNumber);
              if (inputs.some((input) => !input.validity.valid) || !values.every(Number.isFinite)) return;
              scene.setParameter(slot, values);
              draw(frame);
              if (resetButton) resetButton.hidden = false;
            }, {signal});
            updaters.push(setDefault);
            fields.append(field);
            continue;
          }
          const field = document.createElement("label");
          field.className = "preview-field";
          const head = document.createElement("span");
          head.className = "preview-field-head";
          const name = document.createElement("span");
          name.className = "preview-field-name";
          name.textContent = label;
          const readout = document.createElement("span");
          readout.className = "preview-field-value";
          head.append(name, readout);

          const input = document.createElement("input");
          input.setAttribute("aria-label", label);
          const setDefault = () => {
            if (slot.kind === "color") {
              const hex = rgbToHex(slot.defaults);
              input.value = hex;
              readout.textContent = hex.toUpperCase();
            } else {
              input.value = String(slot.defaults[0]);
              readout.textContent = readNumber(slot.defaults[0]);
            }
            scene.setParameter(slot, slot.defaults);
          };

          if (slot.kind === "color") {
            input.type = "color";
          } else {
            input.type = "range";
            input.min = String(bounds?.[0] ?? Math.min(0, slot.defaults[0]));
            input.max = String(bounds?.[1] ?? Math.max(1, slot.defaults[0]));
            input.step = String(step ?? "0.01");
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
                  : readNumber(input.valueAsNumber);
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
      draw(Math.min(frames - 1, Math.round(Number(this.dataset.still ?? 0) * fps)));
      controls.hidden = false;
      status.hidden = true;
    } catch (error) {
      report(error);
    }
  }
}

customElements.define("kara-preview", LivePreview);
