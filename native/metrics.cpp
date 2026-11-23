// Text geometry for authoring. All face and layout state belongs to the Python
// module.
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <fontconfig/fontconfig.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_OUTLINE_H
#include FT_STROKER_H
#include FT_SYNTHESIS_H
#include FT_TRUETYPE_TABLES_H
#include <algorithm>
#include <cmath>
#include <cstring>
#ifdef _WIN32
#include <cstdlib>
#include <filesystem>
#endif
#include <fribidi.h>
#include <hb-ft.h>
#include <hb-ot.h>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using Code = uint32_t;
struct Face {
  std::string data;
  FT_Face ft = nullptr;
  hb_font_t *hb = nullptr;
  int ascender = 0;
  int descender = 0;
  ~Face() {
    if (hb)
      hb_font_destroy(hb);
    if (ft)
      FT_Done_Face(ft);
  }
  void initialize() {
    // ASS script pixels scale the Windows cell height, which can exceed the em.
    ascender = ft->ascender;
    descender = ft->descender;
    const auto *os2 = static_cast<const TT_OS2 *>(FT_Get_Sfnt_Table(ft, ft_sfnt_os2));
    if (os2 && os2->version != 0xffff) {
      const int top = static_cast<FT_Short>(os2->usWinAscent);
      const int bottom = static_cast<FT_Short>(os2->usWinDescent);
      if (top + bottom > 0) {
        ascender = top;
        descender = -bottom;
      }
    }
    hb_face_t *face = hb_ft_face_create_referenced(ft);
    hb = hb_font_create(face);
    hb_face_destroy(face);
    hb_ot_font_set_funcs(hb);
  }
  const char *family() const { return ft->family_name ? ft->family_name : ""; }
  const char *style() const { return ft->style_name ? ft->style_name : ""; }
  double height() const {
    return std::max(1, ascender - descender);
  }
};
using FontKey = std::tuple<std::string, bool, bool, Code>;
struct Fonts {
  FT_Library ft = nullptr;
  std::unique_ptr<FcConfig, decltype(&FcConfigDestroy)> config{nullptr,
                                                               FcConfigDestroy};
  std::vector<std::unique_ptr<Face>> registered;
  std::map<std::pair<std::string, int>, std::unique_ptr<Face>> system;
  std::map<FontKey, Face *> choices;
  Fonts() {
#ifdef _WIN32
    // Repaired wheels can run outside MSYS2, without its fonts.conf.
    if (!std::getenv("FONTCONFIG_FILE")) {
      config.reset(FcConfigCreate());
      if (!config)
        throw std::bad_alloc();
      auto add_directory = [&](const wchar_t *variable, const wchar_t *suffix) {
        if (const auto *root = _wgetenv(variable)) {
          auto path = (std::filesystem::path(root) / suffix).u8string();
          FcConfigAppFontAddDir(
              config.get(), reinterpret_cast<const FcChar8 *>(path.c_str()));
        }
      };
      add_directory(L"WINDIR", L"Fonts");
      add_directory(L"LOCALAPPDATA", L"Microsoft/Windows/Fonts");
    }
#endif
    if (FT_Init_FreeType(&ft))
      throw std::runtime_error("FreeType initialization failed");
  }
  ~Fonts() {
    system.clear();
    registered.clear();
    FT_Done_FreeType(ft);
  }

  Face *match(const char *family, bool bold, bool italic, Code cp) {
    FontKey key(family, bold, italic, cp);
    auto hit = choices.find(key);
    if (hit != choices.end())
      return hit->second;
    Face *best = nullptr;
    int best_score = -1;
    for (auto &face : registered) {
      if (FcStrCmpIgnoreCase((const FcChar8 *)family,
                             (const FcChar8 *)face->family()) ||
          (cp && !FT_Get_Char_Index(face->ft, cp)))
        continue;
      int score =
          (bool(face->ft->style_flags & FT_STYLE_FLAG_BOLD) == bold) +
          (bool(face->ft->style_flags & FT_STYLE_FLAG_ITALIC) == italic);
      if (score >= best_score) {
        best = face.get();
        best_score = score;
      }
    }
    if (!best) {
      std::unique_ptr<FcPattern, decltype(&FcPatternDestroy)> query(
          FcPatternCreate(), FcPatternDestroy);
      if (!query)
        throw std::bad_alloc();
      FcPatternAddString(query.get(), FC_FAMILY, (const FcChar8 *)family);
      FcPatternAddInteger(query.get(), FC_WEIGHT,
                          bold ? FC_WEIGHT_BOLD : FC_WEIGHT_REGULAR);
      FcPatternAddInteger(query.get(), FC_SLANT,
                          italic ? FC_SLANT_ITALIC : FC_SLANT_ROMAN);
      if (cp) {
        auto *chars = FcCharSetCreate();
        if (!chars)
          throw std::bad_alloc();
        FcCharSetAddChar(chars, cp);
        FcPatternAddCharSet(query.get(), FC_CHARSET, chars);
        FcCharSetDestroy(chars);
      }
      FcConfigSubstitute(config.get(), query.get(), FcMatchPattern);
      FcDefaultSubstitute(query.get());
      FcResult status;
      std::unique_ptr<FcPattern, decltype(&FcPatternDestroy)> result(
          FcFontMatch(config.get(), query.get(), &status), FcPatternDestroy);
      FcChar8 *file;
      if (result && FcPatternGetString(result.get(), FC_FILE, 0, &file) ==
                        FcResultMatch) {
        int index = 0;
        FcPatternGetInteger(result.get(), FC_INDEX, 0, &index);
        auto &face = system[{reinterpret_cast<char *>(file), index}];
        if (!face) {
          auto loaded = std::make_unique<Face>();
          if (!FT_New_Face(ft, reinterpret_cast<char *>(file), index,
                           &loaded->ft)) {
            loaded->initialize();
            face = std::move(loaded);
          }
        }
        best = face.get();
      }
      if ((!best || (cp && !FT_Get_Char_Index(best->ft, cp)))) {
        for (auto &face : registered)
          if (!cp || FT_Get_Char_Index(face->ft, cp)) {
            best = face.get();
            break;
          }
      }
    }
    if (!best)
      throw std::runtime_error("no usable font face");
    choices.emplace(std::move(key), best);
    return best;
  }
};
static Fonts &fonts(PyObject *module) {
  auto **slot = static_cast<Fonts **>(PyModule_GetState(module));
  if (!*slot)
    *slot = new Fonts();
  return **slot;
}
static PyObject *add_font(PyObject *module, PyObject *args) {
  const char *name, *data;
  Py_ssize_t size;
  if (!PyArg_ParseTuple(args, "sy#", &name, &data, &size))
    return nullptr;
  try {
    auto &db = fonts(module);
    auto face = std::make_unique<Face>();
    face->data.assign(data, size);
    if (FT_New_Memory_Face(db.ft, (const FT_Byte *)face->data.data(), size, 0,
                           &face->ft))
      throw std::runtime_error("invalid or unsupported font data");
    face->initialize();
    db.registered.push_back(std::move(face));
    db.choices.clear();
    return PyUnicode_DecodeUTF8(db.registered.back()->family(),
                                std::strlen(db.registered.back()->family()),
                                "replace");
  } catch (const std::bad_alloc &) {
    return PyErr_NoMemory();
  } catch (const std::exception &e) {
    PyErr_SetString(PyExc_ValueError, e.what());
    return nullptr;
  }
}

static double subpixel(double x) { return std::round(x * 64) / 64; }

using Point = std::pair<double, double>;
struct Pen {
  double x, y, sx, sy, slant;
  Point start, current;
  std::vector<Point> points;
  std::string segments;
  bool open = false;
  Point point(const FT_Vector *p) {
    return {x + subpixel((p->x + p->y * slant) * sx), y - subpixel(p->y * sy)};
  }
  void close() {
    if (!open)
      return;
    if (current != start) {
      points.push_back(current);
      segments.push_back(1);
    }
    if (!segments.empty())
      segments.back() |= 4;
    open = false;
  }
};
static int move_to(const FT_Vector *p, void *user) {
  auto &pen = *static_cast<Pen *>(user);
  pen.close();
  pen.start = pen.current = pen.point(p);
  pen.open = true;
  return 0;
}
static int line_to(const FT_Vector *p, void *user) {
  auto &pen = *static_cast<Pen *>(user);
  pen.points.push_back(pen.current);
  pen.segments.push_back(1);
  pen.current = pen.point(p);
  return 0;
}
static int conic_to(const FT_Vector *a, const FT_Vector *b, void *user) {
  auto &pen = *static_cast<Pen *>(user);
  pen.points.push_back(pen.current);
  pen.points.push_back(pen.point(a));
  pen.segments.push_back(2);
  pen.current = pen.point(b);
  return 0;
}
static int cubic_to(const FT_Vector *a, const FT_Vector *b, const FT_Vector *c,
                    void *user) {
  auto &pen = *static_cast<Pen *>(user);
  pen.points.push_back(pen.current);
  pen.points.push_back(pen.point(a));
  pen.points.push_back(pen.point(b));
  pen.segments.push_back(3);
  pen.current = pen.point(c);
  return 0;
}
struct Glyph {
  Face *face;
  unsigned id;
  double x, y;
};
static PyObject *outline(const Glyph &g, double xscale, double yscale,
                         bool bold, bool italic) {
  auto ft = g.face->ft;
  Pen pen{g.x, g.y, xscale / g.face->height(), yscale / g.face->height(),
          italic && !(ft->style_flags & FT_STYLE_FLAG_ITALIC) ? .2 : 0};
  if (!FT_Load_Glyph(ft, g.id, FT_LOAD_NO_SCALE | FT_LOAD_NO_BITMAP) &&
      ft->glyph->format == FT_GLYPH_FORMAT_OUTLINE) {
    auto &shape = ft->glyph->outline;
    if (bold && !(ft->style_flags & FT_STYLE_FLAG_BOLD))
      FT_Outline_Embolden(&shape, ft->units_per_EM / 32);
    FT_Outline_Funcs funcs{move_to, line_to, conic_to, cubic_to, 0, 0};
    FT_Outline_Decompose(&shape, &funcs, &pen);
    pen.close();
  }
  PyObject *points = PyTuple_New(pen.points.size());
  if (!points)
    return nullptr;
  for (size_t i = 0; i < pen.points.size(); i++) {
    auto [x, y] = pen.points[i];
    auto *point = Py_BuildValue("(dd)", x, y);
    if (!point) {
      Py_DECREF(points);
      return nullptr;
    }
    PyTuple_SET_ITEM(points, i, point);
  }
  return Py_BuildValue("(Ny#(dd)(ssid))", points, pen.segments.data(),
                       Py_ssize_t(pen.segments.size()), g.x, g.y,
                       g.face->family(), g.face->style(), int(g.id),
                       ft->units_per_EM / g.face->height());
}
static PyObject *measure(PyObject *module, PyObject *args, bool shapes) {
  const char *family;
  PyObject *text;
  double size, sx, sy, spacing, placement = 0;
  int bold, italic, encoding, palt = 0;
  if (!PyArg_ParseTuple(args, "sdiidddiU|dp", &family, &size, &bold, &italic,
                        &sx, &sy, &spacing, &encoding, &text, &placement,
                        &palt))
    return nullptr;
  if (!(size > 0 && sx > 0 && sy > 0) || !std::isfinite(size * sx) ||
      !std::isfinite(size * sy) || !std::isfinite(placement) ||
      !std::isfinite(spacing)) {
    PyErr_SetString(PyExc_ValueError,
                    "invalid font size, scale, spacing or placement");
    return nullptr;
  }
  try {
    auto &db = fonts(module);
    sx *= size / 100;
    sy *= size / 100;
    std::vector<std::vector<Code>> lines(1);
    for (Py_ssize_t i = 0; i < PyUnicode_GET_LENGTH(text); i++) {
      Code c = PyUnicode_ReadChar(text, i);
      if (c == '\\' && i + 1 < PyUnicode_GET_LENGTH(text)) {
        Code next = PyUnicode_ReadChar(text, i + 1);
        if (next == 'N' || next == 'n') {
          c = '\n';
          ++i;
        } else if (next == 'h') {
          c = 0xa0;
          ++i;
        }
      }
      if (c == '\n')
        lines.emplace_back();
      else if (c != 0x2060)
        lines.back().push_back(c == '\t' ? ' ' : c);
    }
    std::vector<Glyph> glyphs;
    double width = 0, height = 0, descent = 0, baseline = 0;
    for (const auto &line : lines) {
      const size_t n = line.size();
      std::vector<FriBidiLevel> levels(n);
      std::vector<FriBidiStrIndex> visual(n);
      FriBidiParType direction = FRIBIDI_PAR_ON;
      if (n && !fribidi_log2vis(line.data(), n, &direction, nullptr,
                                visual.data(), nullptr, levels.data()))
        throw std::runtime_error("bidirectional layout failed");
      struct Run {
        size_t begin, end;
        Face *face;
        hb_script_t script;
      };
      std::vector<Run> runs;
      Face *primary = db.match(family, bold, italic, 0);
      double asc = primary->ascender / primary->height() * sy;
      double desc = -primary->descender / primary->height() * sy;
      for (size_t i = 0; i < n; i++) {
        Face *face = FT_Get_Char_Index(primary->ft, line[i])
                         ? primary
                         : db.match(family, bold, italic, line[i]);
        auto script =
            hb_unicode_script(hb_unicode_funcs_get_default(), line[i]);
        bool common =
            script == HB_SCRIPT_COMMON || script == HB_SCRIPT_INHERITED;
        if (!runs.empty() && runs.back().face == face &&
            levels[i] == levels[runs.back().begin] &&
            (common || runs.back().script == HB_SCRIPT_COMMON ||
             runs.back().script == script)) {
          runs.back().end = i + 1;
          if (!common)
            runs.back().script = script;
        } else
          runs.push_back({i, i + 1, face, script});
        asc = std::max(asc, face->ascender / face->height() * sy);
        desc = std::max(desc, -face->descender / face->height() * sy);
      }
      asc = subpixel(asc);
      desc = subpixel(desc);
      if (&line == &lines.front())
        baseline = asc;
      std::sort(runs.begin(), runs.end(), [&](auto &a, auto &b) {
        return visual[a.begin] < visual[b.begin];
      });
      double x = 0;
      for (auto &run : runs) {
        auto *face = run.face;
        std::unique_ptr<hb_buffer_t, decltype(&hb_buffer_destroy)> buf(
            hb_buffer_create(), hb_buffer_destroy);
        hb_buffer_add_codepoints(buf.get(), line.data(), n, run.begin,
                                 run.end - run.begin);
        hb_buffer_set_direction(buf.get(), levels[run.begin] % 2
                                               ? HB_DIRECTION_RTL
                                               : HB_DIRECTION_LTR);
        hb_buffer_set_script(buf.get(), run.script);
        hb_buffer_guess_segment_properties(buf.get());
        hb_feature_t features[] = {
            {HB_TAG('k', 'e', 'r', 'n'), 0, 0, ~0u},
            {HB_TAG('p', 'a', 'l', 't'), unsigned(palt), 0, ~0u}};
        hb_shape(face->hb, buf.get(), features, 2);
        unsigned count;
        auto infos = hb_buffer_get_glyph_infos(buf.get(), &count);
        auto positions = hb_buffer_get_glyph_positions(buf.get(), nullptr);
        for (unsigned j = 0; j < count; j++) {
          auto &pos = positions[j];
          if (shapes) {
            if (!infos[j].codepoint) {
              PyErr_Format(PyExc_ValueError,
                           "missing glyph for U+%04X after font fallback",
                           line[infos[j].cluster]);
              return nullptr;
            }
            glyphs.push_back(
                {face, infos[j].codepoint,
                 x + subpixel(pos.x_offset * sx / face->height()),
                 height + asc - baseline -
                     subpixel(pos.y_offset * sy / face->height())});
          }
          x += subpixel(pos.x_advance * sx / face->height() +
                        spacing * sx / size);
        }
      }
      width = std::max(width, x);
      height += asc + desc;
      descent = std::max(descent, desc);
    }
    if (!shapes)
      return Py_BuildValue("(dddd)", width, height, descent, 0.);
    using List = std::unique_ptr<PyObject, decltype(&Py_DecRef)>;
    List out(PyList_New(0), Py_DecRef);
    if (!out)
      return nullptr;
    for (auto &glyph : glyphs) {
      List item(outline(glyph, sx, sy, bold, italic), Py_DecRef);
      if (!item || PyList_Append(out.get(), item.get()) < 0)
        return nullptr;
    }
    return Py_BuildValue("(ddddO)", width, height, descent, baseline,
                         out.get());
  } catch (const std::bad_alloc &) {
    return PyErr_NoMemory();
  } catch (const std::exception &e) {
    PyErr_SetString(PyExc_ValueError, e.what());
    return nullptr;
  }
}
static PyObject *shape(PyObject *m, PyObject *a) { return measure(m, a, true); }
static PyObject *extents(PyObject *m, PyObject *a) {
  return measure(m, a, false);
}
// Coordinates arrive in bitmap-local, y-up pixels. FreeType's round join
// bounds the stroke at cusps even when the adjacent tangents nearly reverse.
static PyObject *round_stroke(PyObject *module, PyObject *args) {
  int width, height;
  double radius;
  PyObject *contours;
  if (!PyArg_ParseTuple(args, "iidO!", &width, &height, &radius, &PyList_Type, &contours))
    return nullptr;
  if (width <= 0 || height <= 0 || !std::isfinite(radius) || radius <= 0 ||
      radius > 32767 || Py_ssize_t(width) > PY_SSIZE_T_MAX / height) {
    PyErr_SetString(PyExc_ValueError, "invalid stroke bitmap dimensions or radius");
    return nullptr;
  }
  try {
    auto ft = fonts(module).ft;
    FT_Stroker raw;
    if (FT_Stroker_New(ft, &raw))
      throw std::bad_alloc();
    std::unique_ptr<FT_StrokerRec_, decltype(&FT_Stroker_Done)> stroke(raw, FT_Stroker_Done);
    FT_Stroker_Set(raw, std::lround(radius * 64), FT_STROKER_LINECAP_ROUND,
                   FT_STROKER_LINEJOIN_ROUND, 0);
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(contours); ++i) {
      auto contour = PyList_GET_ITEM(contours, i);
      if (!PyList_Check(contour) || PyList_GET_SIZE(contour) < 2)
        throw std::invalid_argument("expected a contour with segments");
      for (Py_ssize_t j = 0; j < PyList_GET_SIZE(contour); ++j) {
        auto segment = PyList_GET_ITEM(contour, j);
        if (!PyTuple_Check(segment))
          throw std::invalid_argument("expected stroke coordinates");
        auto n = PyTuple_GET_SIZE(segment);
        if (n != 2 && !(j && n == 6))
          throw std::invalid_argument("expected a line or cubic stroke segment");
        FT_Vector points[3];
        for (Py_ssize_t k = 0; k < n; k += 2) {
          auto coord = [&](Py_ssize_t index) {
            double v = PyFloat_AsDouble(PyTuple_GET_ITEM(segment, index));
            if (PyErr_Occurred() || !std::isfinite(v) || std::abs(v) > 16777215)
              throw std::invalid_argument("invalid stroke coordinate");
            return std::lround(v * 64);
          };
          points[k / 2] = {coord(k), coord(k + 1)};
        }
        FT_Error error;
        if (j == 0)
          error = FT_Stroker_BeginSubPath(raw, points, false);
        else if (n == 2)
          error = FT_Stroker_LineTo(raw, points);
        else
          error = FT_Stroker_CubicTo(raw, points, points + 1, points + 2);
        if (error)
          throw std::runtime_error("cannot stroke contour segment");
      }
      if (FT_Stroker_EndSubPath(raw))
        throw std::runtime_error("cannot close stroke contour");
    }
    unsigned points, paths;
    if (FT_Stroker_GetCounts(raw, &points, &paths) ||
        points > FT_OUTLINE_POINTS_MAX || paths > FT_OUTLINE_CONTOURS_MAX)
      throw std::invalid_argument("stroke exceeds FreeType outline limits");
    FT_Outline outline{};
    if (FT_Outline_New(ft, points, paths, &outline))
      throw std::bad_alloc();
    outline.n_points = outline.n_contours = 0;
    FT_Stroker_Export(raw, &outline);
    auto result = PyBytes_FromStringAndSize(nullptr, Py_ssize_t(width) * height);
    if (result) {
      FT_Bitmap bitmap{};
      bitmap.width = bitmap.pitch = width;
      bitmap.rows = height;
      bitmap.pixel_mode = FT_PIXEL_MODE_GRAY;
      bitmap.num_grays = 256;
      bitmap.buffer = reinterpret_cast<unsigned char *>(PyBytes_AS_STRING(result));
      std::memset(bitmap.buffer, 0, PyBytes_GET_SIZE(result));
      if (FT_Outline_Get_Bitmap(ft, &outline, &bitmap)) {
        Py_CLEAR(result);
        PyErr_SetString(PyExc_ValueError, "cannot rasterize round stroke");
      }
    }
    FT_Outline_Done(ft, &outline);
    return result;
  } catch (const std::bad_alloc &) {
    return PyErr_NoMemory();
  } catch (const std::exception &e) {
    PyErr_SetString(PyExc_ValueError, e.what());
    return nullptr;
  }
}
static void cleanup(void *m) {
  delete *static_cast<Fonts **>(PyModule_GetState(static_cast<PyObject *>(m)));
}
static PyMethodDef methods[] = {
    {"round_stroke", round_stroke, METH_VARARGS, nullptr},
    {"add_font", add_font, METH_VARARGS, nullptr},
    {"text_extents", extents, METH_VARARGS, nullptr},
    {"text_shape", shape, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}};
static PyModuleDef definition = {PyModuleDef_HEAD_INIT,
                                 "_text_native",
                                 nullptr,
                                 sizeof(Fonts *),
                                 methods,
                                 nullptr,
                                 nullptr,
                                 nullptr,
                                 cleanup};
PyMODINIT_FUNC PyInit__text_native() { return PyModule_Create(&definition); }
