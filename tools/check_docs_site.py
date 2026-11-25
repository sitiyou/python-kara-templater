"""Check the built documentation site's local links, bilingual routes, and previews."""

import hashlib
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from tools.build_docs_site import BUILD, DOCS, document_path

BODY_BLOCKS = {"blockquote", "dd", "li", "p", "pre", "td"}


class Page(HTMLParser):
    def __init__(self, file: Path) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: set[str] = set()
        self.has_body = False
        self.markdown_depth = 0
        self.body_depth = 0
        self.feed(file.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div":
            classes = (dict(attrs).get("class") or "").split()
            if self.markdown_depth or "sl-markdown-content" in classes:
                self.markdown_depth += 1
        if self.markdown_depth and tag in BODY_BLOCKS:
            self.body_depth += 1
        for name, value in attrs:
            if not value:
                continue
            if name == "id":
                self.ids.add(value)
            if (tag in {"a", "link"} and name == "href") or name == "src":
                self.links.add(value)

    def handle_endtag(self, tag: str) -> None:
        if self.markdown_depth and tag in BODY_BLOCKS:
            self.body_depth -= 1
        if tag == "div" and self.markdown_depth:
            self.markdown_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.markdown_depth and self.body_depth and data.strip():
            self.has_body = True


def check_links(dist: Path, prefix: str) -> tuple[int, list[str]]:
    pages = {path: Page(path) for path in sorted(dist.rglob("*.html"))}
    errors: list[str] = []
    for source in sorted(DOCS.rglob("*.md")):
        relative = document_path(source)
        route = relative.parent if relative.name == "index.md" else relative.with_suffix("")
        destination = dist / route / "index.html"
        if destination not in pages:
            errors.append(f"{source.relative_to(DOCS)}: missing rendered page")
        elif not pages[destination].has_body:
            errors.append(f"{source.relative_to(DOCS)}: no rendered Markdown body")

    for required in (
        dist / "index.html",
        dist / "zh-cn" / "index.html",
        dist / "gallery" / "index.html",
        dist / "zh-cn" / "gallery" / "index.html",
    ):
        if required not in pages:
            errors.append(f"{required.relative_to(dist)}: missing required site page")

    for path, page in pages.items():
        relative = path.relative_to(dist)
        page_url = f"{prefix}/{relative.as_posix().removesuffix('index.html')}"
        for target in sorted(page.links):
            href = urlsplit(urljoin(page_url, target))
            if href.scheme or href.netloc:
                continue
            if not href.path.startswith(f"{prefix}/"):
                errors.append(f"{relative}: outside of site base {target}")
                continue
            destination = dist / unquote(href.path.removeprefix(f"{prefix}/"))
            if destination.is_dir():
                destination /= "index.html"
            if not destination.is_file():
                errors.append(f"{relative}: missing {target}")
            elif (
                href.fragment
                and destination in pages
                and unquote(href.fragment) not in pages[destination].ids
            ):
                errors.append(f"{relative}: missing anchor {target}")
    return len(pages), errors


def check_previews(dist: Path) -> int:
    entries = json.loads((BUILD / "gallery.json").read_text(encoding="utf-8"))
    if not entries:
        raise ValueError("The effect gallery has no examples")
    for entry in entries:
        slug = entry["id"]
        folder = dist / "previews" / slug
        source = folder / entry["source"]
        if source.read_text(encoding="utf-8") != entry["code"]:
            raise ValueError(f"{slug}: downloadable script differs from displayed code")
        if not (dist / "gallery" / slug / "index.html").is_file():
            raise ValueError(f"{slug}: missing English example page")
        if not (dist / "zh-cn" / "gallery" / slug / "index.html").is_file():
            raise ValueError(f"{slug}: missing Chinese example page")
        if not (folder / "scene.frag").stat().st_size:
            raise ValueError(f"{slug}: empty preview shader")
        metadata = json.loads((folder / "textures.json").read_text(encoding="utf-8"))
        for key, pixel_bytes in (("KARAMASK", 1), ("KARADATA", 16)):
            width, height = metadata[key]
            raw = (folder / f"{key}.bin").read_bytes()
            if len(raw) != width * height * pixel_bytes:
                raise ValueError(f"{slug}: incomplete {key} texture")
            if hashlib.sha256(raw).hexdigest() != metadata["hashes"][key]:
                raise ValueError(f"{slug}: invalid {key} texture checksum")
        for name in entry.get("labels", {}):
            if name not in metadata.get("parameters", {}):
                raise ValueError(f"{slug}: missing live parameter {name}")
        zh_entry = entry.get("zh-cn")
        if not isinstance(zh_entry, dict) or not zh_entry.get("title"):
            raise ValueError(f"{slug}: missing [demo.zh-cn] gallery translation")
        for name in zh_entry.get("labels", {}):
            if name not in metadata.get("parameters", {}):
                raise ValueError(f"{slug}: missing zh-cn live parameter {name}")
    return len(entries)


def main() -> None:
    path = os.environ.get("DOCS_BASE", "").strip("/")
    prefix = f"/{path}" if path else ""
    dist = BUILD / "dist"
    pages, errors = check_links(dist, prefix)
    previews = check_previews(dist)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"{pages} pages and {previews} bilingual browser previews checked")


if __name__ == "__main__":
    main()
