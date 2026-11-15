"""Small editable lyric document used by repository examples and tests."""

from kara_templater import Document, Line, Record, Style
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


def document(
    *, fontname: str = "Sarasa Gothic SC", text: str = "星月风星月风"
) -> Document:
    # Construct directly; no custom ASS fields, roles, or per-character k tags.
    return Document(
        [
            "[Script Info]",
            "PlayResX: 640",
            "PlayResY: 480",
            "[V4+ Styles]",
            "Format: " + STYLE_FORMAT,
            Style(fontname=fontname, fontsize=56, shadow=0, margin_v=180),
            "[Events]",
            "Format: " + EVENT_FORMAT,
            Line(text=r"{\k300}" + text, start_time=0, end_time=4000),
        ],
        Record(res_x=640, res_y=480),
    )
