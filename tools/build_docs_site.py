"""Stage the Markdown, runnable examples, and GPU resources used by Starlight."""

import importlib
import json
import os
import re
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NotRequired, TypedDict, cast
from urllib.parse import quote, unquote, urlsplit

from kara_templater import Scene, load_font

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BUILD = ROOT / "build" / "docs-site"
SOURCE = "https://github.com/sitiyou/python-kara-templater"
FPS = 30
LINK = re.compile(r"\]\((<[^>]+>|[^\s)]+)(?=[\s)])")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ALERT_HEADER = re.compile(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$")
ALERT_LABELS = {
    "NOTE": ("note", "Note", "说明"),
    "TIP": ("tip", "Tip", "提示"),
    "IMPORTANT": ("important", "Important", "重要"),
    "WARNING": ("warning", "Warning", "注意"),
    "CAUTION": ("caution", "Caution", "警告"),
}
NON_PROSE_PREFIX = ("#", "-", "*", ">", "|", "`", "~", "!", "<", ":::")
ORDERED_LIST = re.compile(r"^\d+\.\s")


class DemoTranslation(TypedDict, total=False):
    title: str
    short: str
    category: str
    summary: str
    details: str
    labels: dict[str, str]


class Demo(TypedDict):
    id: str
    title: str
    short: NotRequired[str]
    category: str
    summary: str
    details: str
    source: str
    guide: str
    accent: str
    duration: float
    still: float
    command: NotRequired[str]
    labels: NotRequired[dict[str, str]]
    zh_cn: NotRequired[DemoTranslation]


def document_path(source: Path) -> Path:
    relative = source.relative_to(DOCS)
    if relative == Path("README.md"):
        return Path("guide/index.md")
    if relative == Path("zh-cn/README.md"):
        return Path("zh-cn/guide/index.md")
    if relative.name == "README.md":
        return relative.with_name("index.md")
    return relative


def extract_lead(body: str) -> tuple[str | None, str]:
    """Lift a plain-text opening paragraph into frontmatter.description."""
    lines = body.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines):
        return None, body

    end = start
    while end < len(lines) and lines[end].strip():
        end += 1

    paragraph_lines = lines[start:end]
    first = paragraph_lines[0].lstrip()
    if first.startswith(NON_PROSE_PREFIX) or ORDERED_LIST.match(first):
        return None, body

    text = " ".join(line.strip() for line in paragraph_lines)
    if (
        len(text) > 420
        or "](" in text
        or "`" in text
        or "**" in text
        or "__" in text
    ):
        return None, body

    remaining = "\n".join(lines[end:]).lstrip("\n")
    return text, remaining + ("\n" if remaining else "")


def convert_github_alerts(body: str, *, in_zh: bool = False) -> str:
    """Convert GitHub alert blockquotes (> [!NOTE]) to styled callout asides."""
    lines = body.splitlines(keepends=True)
    result: list[str] = []
    fence = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        delimiter = FENCE.match(line)
        if delimiter:
            marker = delimiter[1]
            if not fence:
                fence = marker
            elif marker.startswith(fence):
                fence = ""
            result.append(line)
            index += 1
            continue
        if fence:
            result.append(line)
            index += 1
            continue

        header = ALERT_HEADER.match(line.rstrip("\r\n"))
        if not header:
            result.append(line)
            index += 1
            continue

        kind, en_label, zh_label = ALERT_LABELS[header[1]]
        label = zh_label if in_zh else en_label
        index += 1
        inner: list[str] = []
        while index < len(lines) and lines[index].startswith(">"):
            content = lines[index][1:]
            if content.startswith(" "):
                content = content[1:]
            inner.append(content)
            index += 1
        result.append(
            f'<aside class="kara-callout kara-callout-{kind}" aria-label="{label}">\n'
            f'<p class="kara-callout-title">{label}</p>\n\n'
        )
        result.extend(inner)
        if inner and not inner[-1].endswith("\n"):
            result.append("\n")
        result.append("\n</aside>\n")
    return "".join(result)


def rewrite_links(body: str, source: Path, base: str, source_ref: str) -> str:
    in_zh = source.relative_to(DOCS).parts[0] == "zh-cn"

    def resolve(match: re.Match[str]) -> str:
        target = urlsplit(match[1].strip("<>"))
        if target.scheme or target.netloc or not target.path:
            return match[0]
        path = (source.parent / unquote(target.path)).resolve()
        if path.is_relative_to(DOCS) and path.suffix == ".md":
            relative = document_path(path).with_suffix("")
            route = relative.parent if relative.name == "index" else relative
            route_str = route.as_posix().rstrip("/")
            if in_zh and path.is_relative_to(DOCS / "reference"):
                route_str = f"zh-cn/{route_str}"
            href = f"{base}/{route_str}/"
        elif path.is_relative_to(DOCS / "examples" / "assets"):
            media = quote(path.relative_to(DOCS).as_posix())
            href = f"{base}/docs-media/{media}"
        else:
            relative = quote(path.relative_to(ROOT).as_posix())
            href = f"{SOURCE}/blob/{source_ref}/{relative}"
        query = f"?{target.query}" if target.query else ""
        fragment = f"#{target.fragment}" if target.fragment else ""
        return f"]({href}{query}{fragment}"

    result: list[str] = []
    fence = ""
    for line in body.splitlines(keepends=True):
        delimiter = FENCE.match(line)
        if delimiter:
            marker = delimiter[1]
            if not fence:
                fence = marker
            elif marker.startswith(fence):
                fence = ""
            result.append(line)
        else:
            result.append(line if fence else LINK.sub(resolve, line))
    return "".join(result)


def stage_docs(stage: Path, base: str, source_ref: str) -> None:
    for source in sorted(DOCS.rglob("*.md")):
        destination = stage / "content" / document_path(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        title, _, raw_body = source.read_text(encoding="utf-8").partition("\n")
        if not title.startswith("# "):
            raise ValueError(f"{source.relative_to(ROOT)} must start with a title")
        lead, body = extract_lead(raw_body)
        frontmatter_lines = [
            "---",
            f"title: {json.dumps(title[2:].strip(), ensure_ascii=False)}",
        ]
        if lead:
            frontmatter_lines.append(
                f"description: {json.dumps(lead, ensure_ascii=False)}"
            )
        frontmatter_lines.append("---\n")
        in_zh = source.relative_to(DOCS).parts[0] == "zh-cn"
        staged_body = convert_github_alerts(
            rewrite_links(body, source, base, source_ref), in_zh=in_zh
        )
        destination.write_text(
            "\n".join(frontmatter_lines) + staged_body, encoding="utf-8"
        )
    shutil.copytree(
        DOCS / "examples" / "assets", stage / "public/docs-media/examples/assets"
    )
    shutil.copyfile(ROOT / "site" / "favicon.png", stage / "public/favicon.png")


def stage_gallery(stage: Path) -> None:
    with (DOCS / "examples" / "gallery.toml").open("rb") as stream:
        raw_demos = cast("list[dict[str, object]]", tomllib.load(stream)["demo"])
    load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    entries: list[dict[str, object]] = []
    for raw in raw_demos:
        demo = cast("Demo", raw)
        slug = demo["id"]
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", slug):
            raise ValueError(f"Invalid gallery slug {slug!r}")
        source = ROOT / "examples" / demo["source"]
        if not source.is_file() or source.parent != ROOT / "examples":
            raise ValueError(f"Invalid gallery source {source}")
        module = importlib.import_module(f"examples.{source.stem}")
        build = cast("Callable[[], Scene]", module.build)
        scene = build()
        folder = stage / "public" / "previews" / slug
        folder.parent.mkdir(parents=True, exist_ok=True)
        count = round(demo["duration"] * FPS)
        if count < 1 or not 0 <= demo["still"] < count / FPS:
            raise ValueError(f"Invalid gallery sample time for {slug}")
        scene.export_resources(folder, fps=FPS, duration=count / FPS)
        shutil.copyfile(source, folder / source.name)
        entry: dict[str, object] = {
            **{key: value for key, value in raw.items() if key != "zh-cn"},
            "width": scene.document.meta.res_x,
            "height": scene.document.meta.res_y,
            "code": source.read_text(encoding="utf-8"),
            "command": demo.get("command", f"python {source.name} {slug}.hook"),
        }
        if "zh-cn" in raw:
            entry["zh-cn"] = raw["zh-cn"]
        entries.append(entry)
        size = sum(path.stat().st_size for path in folder.iterdir())
        print(f"{slug}: {count} frames, {size / 1024:.0f} KiB")
    (stage / "gallery.json").write_text(
        json.dumps(entries, ensure_ascii=False), encoding="utf-8"
    )


def main() -> None:
    base = os.environ.get("DOCS_BASE", "").strip("/")
    prefix = f"/{base}" if base else ""
    source_ref = quote(os.environ.get("DOCS_SOURCE_REF", "main"), safe="")
    BUILD.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=BUILD.parent) as directory:
        stage = Path(directory) / "docs-site"
        stage_docs(stage, prefix, source_ref)
        stage_gallery(stage)
        if BUILD.exists():
            shutil.rmtree(BUILD)
        stage.rename(BUILD)


if __name__ == "__main__":
    main()
