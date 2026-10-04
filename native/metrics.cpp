#define PY_SSIZE_T_CLEAN
#include <Python.h>
extern "C" {
#include <ass.h>
#include <ass_metrics.h>
}
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>

struct Context {
    ASS_Library *library = nullptr;
    ASS_Renderer *renderer = nullptr;

    ~Context() {
        if (renderer) ass_renderer_done(renderer);
        if (library) ass_library_done(library);
    }
};

struct State { Context *context; };

static void quiet(int, const char *, va_list, void *) {}

static PyObject *extents(PyObject *module, PyObject *args) {
    const char *font, *text;
    double size, sx, sy, spacing;
    int bold, italic, encoding;
    if (!PyArg_ParseTuple(args, "sdiidddis", &font, &size, &bold, &italic,
                          &sx, &sy, &spacing, &encoding, &text)) return nullptr;
    if (!std::isfinite(size) || !std::isfinite(sx) || !std::isfinite(sy) ||
        !std::isfinite(spacing) || size <= 0 || sx <= 0 || sy <= 0) {
        PyErr_SetString(PyExc_ValueError, "Font size and scales must be finite and positive");
        return nullptr;
    }
    auto *state = static_cast<State *>(PyModule_GetState(module));
    if (!state->context) {
        auto ctx = std::make_unique<Context>();
        ctx->library = ass_library_init();
        if (ctx->library) {
            ass_set_message_cb(ctx->library, quiet, nullptr);
            ctx->renderer = ass_renderer_init(ctx->library);
        }
        if (!ctx->renderer) {
            PyErr_SetString(PyExc_RuntimeError, "Could not initialize libass");
            return nullptr;
        }
        ass_set_frame_size(ctx->renderer, 1920, 1080);
        ass_set_fonts(ctx->renderer, nullptr, "sans-serif", ASS_FONTPROVIDER_AUTODETECT, nullptr, 1);
        state->context = ctx.release();
    }
    auto &ctx = *state->context;
    std::string script =
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,sans-serif,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,x\n";
    std::unique_ptr<ASS_Track, decltype(&ass_free_track)> track(
        ass_read_memory(ctx.library, script.data(), script.size(), nullptr), ass_free_track);
    if (!track || !track->n_events) {
        PyErr_SetString(PyExc_RuntimeError, "Could not create metrics track");
        return nullptr;
    }
    auto &style = track->styles[track->events[0].Style];
    auto &event = track->events[0];
    std::string literal;
    for (const char *p = text; *p; ++p) {
        if (*p == ' ' || *p == '\t') {
            literal += "\\h";
        } else {
            if (*p == '{' || *p == '}') literal += '\\';
            literal += *p;
        }
    }
    free(style.FontName);
    style.FontName = strdup(font);
    style.FontSize = size;
    style.Bold = bold ? -1 : 0;
    style.Italic = italic ? -1 : 0;
    style.ScaleX = sx / 100;
    style.ScaleY = sy / 100;
    style.Spacing = spacing;
    style.Encoding = encoding;
    free(event.Text);
    event.Text = strdup(literal.empty() ? "\\h" : literal.c_str());
    if (!style.FontName || !event.Text) return PyErr_NoMemory();
    double width = 0, height = 0, descent = 0;
    ASS_Metrics *metrics = ass_get_metrics(ctx.renderer, track.get(), 0);
    if (!metrics) {
        PyErr_SetString(PyExc_RuntimeError, "libass returned no text metrics");
        return nullptr;
    }
    for (auto *ev = metrics; ev; ev = ev->next) {
        double row_width = 0, row_y = 0, top = 0, bottom = 0;
        bool first = true;
        for (auto *run = ev->runs; run; run = run->next) {
            if (first) {
                row_y = run->pos.y;
                top = run->pos.y - run->asc;
                first = false;
            } else if (std::abs(run->pos.y - row_y) > 0.01) {
                width = std::max(width, row_width);
                row_width = 0;
                row_y = run->pos.y;
            }
            row_width += run->advance.x;
            top = std::min(top, run->pos.y - run->asc);
            bottom = std::max(bottom, run->pos.y + run->desc);
            descent = std::max(descent, run->desc);
        }
        width = std::max(width, row_width);
        height = std::max(height, bottom - top);
    }
    return Py_BuildValue("(dddd)", *text ? width : 0, height, descent, 0.0);
}

static void cleanup(void *module) {
    auto *state = static_cast<State *>(PyModule_GetState(static_cast<PyObject *>(module)));
    delete state->context;
}

static PyMethodDef methods[] = {
    {"text_extents", extents, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};

static PyModuleDef definition = {
    PyModuleDef_HEAD_INIT, "_metrics", nullptr, sizeof(State), methods,
    nullptr, nullptr, nullptr, cleanup
};

PyMODINIT_FUNC PyInit__metrics() { return PyModule_Create(&definition); }
