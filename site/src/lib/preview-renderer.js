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

export function createContext(canvas) {
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

export async function loadPreview(gl, base, signal) {
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
