#define PY_SSIZE_T_CLEAN
#include <Python.h>
extern "C" {
#include <ass.h>
#include <ass_metrics.h>
#include <ft2build.h>
#include FT_FREETYPE_H
}
#include <algorithm>
#include <cmath>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <sstream>
#include <iomanip>

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

static Context *get_context(PyObject *module) {
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
    return state->context;
}

static PyObject *measure(PyObject *module, PyObject *args, bool shapes) {
    const char *font, *text;
    double size, sx, sy, spacing, placement_x = 0;
    int bold, italic, encoding;
    if (!PyArg_ParseTuple(args, "sdiidddis|d", &font, &size, &bold, &italic,
                          &sx, &sy, &spacing, &encoding, &text, &placement_x)) return nullptr;
    if (!std::isfinite(size) || !std::isfinite(sx) || !std::isfinite(sy) ||
        !std::isfinite(spacing) || !std::isfinite(placement_x) || size <= 0 || sx <= 0 || sy <= 0) {
        PyErr_SetString(PyExc_ValueError, "Font size and scales must be finite and positive");
        return nullptr;
    }
    auto *context = get_context(module);
    if (!context) return nullptr;
    auto &ctx = *context;
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
    if (shapes) {
        std::ostringstream positioned;
        positioned << "{\\an7\\pos(" << std::setprecision(17) << placement_x << ",0)}"
                   << (literal.empty() ? "\\h" : literal);
        literal = positioned.str();
    }
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
    if (!shapes) return Py_BuildValue("(dddd)", *text ? width : 0, height, descent, 0.0);
    // Copy outlines while the renderer owns them. Coordinates are relative to
    // the event's first baseline; unlike bitmap extents these retain spaces.
    PyObject *outlines = PyList_New(0);
    if (!outlines) return nullptr;
    const double origin_x = metrics->runs ? metrics->runs->pos.x : 0;
    const double baseline = metrics->runs ? metrics->runs->pos.y : 0;
    for (auto *ev = metrics; ev; ev = ev->next) {
        for (auto *run = ev->runs; run; run = run->next) {
            for (auto *outline = run->fill; outline; outline = outline->next) {
                if (outline->glyph_index == 0) {
                    Py_DECREF(outlines);
                    PyErr_Format(PyExc_ValueError,
                        "missing glyph for U+%04X after font fallback", outline->codepoint);
                    return nullptr;
                }
                PyObject *points = PyTuple_New(outline->n_points);
                if (!points) { Py_DECREF(outlines); return nullptr; }
                for (size_t i = 0; i < outline->n_points; ++i) {
                    PyObject *point = Py_BuildValue("(dd)",
                        outline->points[i].x + run->pos.x - origin_x,
                        outline->points[i].y + run->pos.y - baseline);
                    if (!point) { Py_DECREF(points); Py_DECREF(outlines); return nullptr; }
                    PyTuple_SET_ITEM(points, i, point);
                }
                PyObject *segments = PyBytes_FromStringAndSize(outline->segments, outline->n_segments);
                if (!segments) { Py_DECREF(points); Py_DECREF(outlines); return nullptr; }
                PyObject *item = Py_BuildValue("(NN(dd)(ssi))", points, segments,
                    outline->glyph_origin.x - origin_x,
                    outline->glyph_origin.y - baseline,
                    outline->font_family ? outline->font_family : "",
                    outline->font_style ? outline->font_style : "",
                    outline->glyph_index);
                if (!item || PyList_Append(outlines, item) < 0) {
                    Py_XDECREF(item); Py_DECREF(outlines); return nullptr;
                }
                Py_DECREF(item);
            }
        }
    }
    PyObject *result = Py_BuildValue("(ddddN)", *text ? width : 0, height, descent, baseline, outlines);
    return result;
}

static PyObject *extents(PyObject *module, PyObject *args) { return measure(module, args, false); }
static PyObject *shape(PyObject *module, PyObject *args) { return measure(module, args, true); }

static PyObject *add_font(PyObject *module, PyObject *args) {
    const char *name, *data;
    Py_ssize_t size;
    if (!PyArg_ParseTuple(args, "sy#", &name, &data, &size)) return nullptr;
    if (size <= 0 || size > INT_MAX) {
        PyErr_SetString(PyExc_ValueError, "Font data length must be in 1..INT_MAX");
        return nullptr;
    }
    FT_Library library = nullptr;
    FT_Face face = nullptr;
    if (FT_Init_FreeType(&library)) {
        PyErr_SetString(PyExc_RuntimeError, "Could not initialize font validation");
        return nullptr;
    }
    if (FT_New_Memory_Face(library, reinterpret_cast<const FT_Byte *>(data), size, 0, &face)) {
        FT_Done_FreeType(library);
        PyErr_SetString(PyExc_ValueError, "Invalid or unsupported font data");
        return nullptr;
    }
    std::string family = face->family_name ? face->family_name : "";
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    auto *ctx = get_context(module);
    if (!ctx) return nullptr;
    ass_add_font(ctx->library, name, data, static_cast<int>(size));
    ass_set_fonts(ctx->renderer, nullptr, "sans-serif", ASS_FONTPROVIDER_AUTODETECT, nullptr, 1);
    return PyUnicode_DecodeUTF8(family.data(), family.size(), "replace");
}

static void cleanup(void *module) {
    auto *state = static_cast<State *>(PyModule_GetState(static_cast<PyObject *>(module)));
    delete state->context;
}

static PyMethodDef methods[] = {
    {"text_extents", extents, METH_VARARGS, nullptr},
    {"text_shape", shape, METH_VARARGS, nullptr},
    {"add_font", add_font, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};

static PyModuleDef definition = {
    PyModuleDef_HEAD_INIT, "_metrics", nullptr, sizeof(State), methods,
    nullptr, nullptr, nullptr, cleanup
};

PyMODINIT_FUNC PyInit__metrics() { return PyModule_Create(&definition); }
