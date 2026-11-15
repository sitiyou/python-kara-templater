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
    ASS_Renderer *raster_renderer = nullptr;

    ~Context() {
        if (raster_renderer) ass_renderer_done(raster_renderer);
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

// Keep raster caches and output resolution separate from shape measurement.
// Fonts share the library, and callers receive owned packed bitmap copies.
static PyObject *rasterize(PyObject *module, PyObject *args) {
    const char *script;
    Py_ssize_t size, max_pixels, max_images;
    long long time;
    int width, height;
    if (!PyArg_ParseTuple(args, "s#Liinn", &script, &size, &time, &width, &height,
                          &max_pixels, &max_images)) return nullptr;
    if (width <= 0 || height <= 0 || max_pixels <= 0 || max_images <= 0 ||
        static_cast<long long>(width) * height > max_pixels || size > 16 * 1024 * 1024) {
        PyErr_SetString(PyExc_ValueError, "Raster dimensions or script exceed the declared budget");
        return nullptr;
    }
    auto *ctx = get_context(module);
    if (!ctx) return nullptr;
    if (!ctx->raster_renderer) {
        ctx->raster_renderer = ass_renderer_init(ctx->library);
        if (!ctx->raster_renderer) return PyErr_NoMemory();
        ass_set_fonts(ctx->raster_renderer, nullptr, "sans-serif", ASS_FONTPROVIDER_AUTODETECT, nullptr, 1);
    }
    ass_set_frame_size(ctx->raster_renderer, width, height);
    ass_set_storage_size(ctx->raster_renderer, width, height);
    // ass_read_memory does not retain the input, but its public API takes char*.
    std::unique_ptr<ASS_Track, decltype(&ass_free_track)> track(
        ass_read_memory(ctx->library, const_cast<char *>(script), size, nullptr), ass_free_track);
    if (!track) {
        PyErr_SetString(PyExc_ValueError, "Could not parse raster ASS input");
        return nullptr;
    }
    ASS_Image *images = ass_render_frame(ctx->raster_renderer, track.get(), time, nullptr);
    Py_ssize_t pixels = 0, count = 0;
    for (auto *image = images; image; image = image->next) {
        if (!image->w || !image->h) continue;
        const long long area = static_cast<long long>(image->w) * image->h;
        if (area > max_pixels - pixels || ++count > max_images) {
            PyErr_SetString(PyExc_ValueError, "Raster image coverage exceeds the declared budget");
            return nullptr;
        }
        pixels += area;
    }
    PyObject *result = PyList_New(0);
    if (!result) return nullptr;
    for (auto *image = images; image; image = image->next) {
        if (!image->w || !image->h) continue;
        PyObject *data = PyBytes_FromStringAndSize(nullptr, static_cast<Py_ssize_t>(image->w) * image->h);
        if (!data) { Py_DECREF(result); return nullptr; }
        char *destination = PyBytes_AS_STRING(data);
        for (int y = 0; y < image->h; ++y)
            memcpy(destination + static_cast<Py_ssize_t>(y) * image->w,
                   image->bitmap + static_cast<ptrdiff_t>(y) * image->stride, image->w);
        PyObject *value = Py_BuildValue("(iiiiiIN)", image->dst_x, image->dst_y,
            image->w, image->h, static_cast<int>(image->type), image->color, data);
        if (!value || PyList_Append(result, value) < 0) {
            Py_XDECREF(value); Py_DECREF(result); return nullptr;
        }
        Py_DECREF(value);
    }
    return result;
}

static PyObject *blur_padding(PyObject *, PyObject *args) {
    double radius;
    if (!PyArg_ParseTuple(args, "d", &radius)) return nullptr;
    int padding = ass_blur_padding(radius);
    if (padding < 0) {
        PyErr_SetString(PyExc_ValueError, "Blur radius must be finite and in 0..100 ASS pixels");
        return nullptr;
    }
    return PyLong_FromLong(padding);
}

static PyObject *blur_mask(PyObject *module, PyObject *args) {
    const char *data;
    Py_ssize_t size, max_pixels;
    int width, height;
    double radius;
    if (!PyArg_ParseTuple(args, "y#iidn", &data, &size, &width, &height, &radius, &max_pixels))
        return nullptr;
    if (width <= 0 || height <= 0 || static_cast<long long>(width) * height != size || max_pixels <= 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid blur coverage dimensions or budget");
        return nullptr;
    }
    auto *ctx = get_context(module);
    if (!ctx) return nullptr;
    ASS_Coverage coverage = {};
    int status = ass_blur_coverage(ctx->renderer, reinterpret_cast<const unsigned char *>(data),
                                  width, height, radius, max_pixels, &coverage);
    if (status) {
        if (status == -3) return PyErr_NoMemory();
        PyErr_SetString(PyExc_ValueError, status == -2 ? "Blur workspace exceeds the declared budget" :
                        "Blur radius must be finite and in 0..100 ASS pixels");
        return nullptr;
    }
    PyObject *pixels = PyBytes_FromStringAndSize(nullptr, static_cast<Py_ssize_t>(coverage.w) * coverage.h);
    if (!pixels) { ass_free_coverage(&coverage); return nullptr; }
    char *destination = PyBytes_AS_STRING(pixels);
    for (int y = 0; y < coverage.h; ++y)
        memcpy(destination + static_cast<Py_ssize_t>(y) * coverage.w,
               coverage.buffer + y * coverage.stride, coverage.w);
    PyObject *result = Py_BuildValue("(iiiiN)", coverage.left, coverage.top, coverage.w, coverage.h, pixels);
    ass_free_coverage(&coverage);
    return result;
}

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
    if (ctx->raster_renderer)
        ass_set_fonts(ctx->raster_renderer, nullptr, "sans-serif", ASS_FONTPROVIDER_AUTODETECT, nullptr, 1);
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
    {"rasterize", rasterize, METH_VARARGS, nullptr},
    {"blur_padding", blur_padding, METH_VARARGS, nullptr},
    {"blur_mask", blur_mask, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};

static PyModuleDef definition = {
    PyModuleDef_HEAD_INIT, "_metrics", nullptr, sizeof(State), methods,
    nullptr, nullptr, nullptr, cleanup
};

PyMODINIT_FUNC PyInit__metrics() { return PyModule_Create(&definition); }
