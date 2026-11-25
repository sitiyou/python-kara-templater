"""Check user-document links, bilingual parity, snippet syntax, and API reference.

python -m tools.check_docs
Works in a checkout or the installed-package verification directory.
"""

import ast
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools.generate_reference import PACKAGE, ROOT, generate


def anchors(path: Path) -> set[str]:
    """Approximate GitHub/Starlight heading IDs for Markdown including CJK."""
    counts: Counter[str] = Counter()
    result: set[str] = set()
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if heading is None:
            continue
        slug = re.sub(r"[^\w\- ]", "", heading[1].lower()).replace(" ", "-")
        suffix = counts[slug]
        counts[slug] += 1
        result.add(slug + (f"-{suffix}" if suffix else ""))
    return result


def check_bilingual_parity(docs_root: Path) -> list[str]:
    zh_root = docs_root / "zh-cn"
    if not zh_root.is_dir():
        return ["docs/zh-cn: missing Chinese documentation directory"]
    en_pages = {
        path.relative_to(docs_root)
        for path in docs_root.rglob("*.md")
        if path.relative_to(docs_root).parts[0] not in {"zh-cn", "reference"}
    }
    zh_pages = {path.relative_to(zh_root) for path in zh_root.rglob("*.md")}
    errors: list[str] = []
    for missing in sorted(en_pages - zh_pages):
        errors.append(f"docs/zh-cn/{missing.as_posix()}: missing Chinese translation")
    for extra in sorted(zh_pages - en_pages):
        errors.append(
            f"docs/zh-cn/{extra.as_posix()}: no matching English page at docs/{extra.as_posix()}"
        )
    return errors


def check() -> tuple[int, list[str]]:
    docs_root = ROOT / "docs"
    pages = [
        ROOT / "README.md",
        ROOT / "skills/kara-templater/SKILL.md",
        *sorted(docs_root.rglob("*.md")),
    ]
    errors: list[str] = check_bilingual_parity(docs_root)
    for page in pages:
        content = page.read_text(encoding="utf-8")
        if content.count("```") % 2:
            errors.append(f"{page.relative_to(ROOT)}: unclosed code fence")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            url = urlsplit(target.strip("<>"))
            if url.scheme or url.netloc:
                continue
            resolved = (page.parent / unquote(url.path)).resolve() if url.path else page
            if not resolved.exists():
                relative = resolved.relative_to(ROOT)
                if relative.parts[0] == "kara_templater":
                    resolved = PACKAGE.joinpath(*relative.parts[1:])
            if not resolved.is_file():
                errors.append(f"{page.relative_to(ROOT)}: missing {target}")
            elif url.fragment and resolved.suffix == ".md":
                if unquote(url.fragment) not in anchors(resolved):
                    errors.append(f"{page.relative_to(ROOT)}: missing heading {target}")
            elif (
                url.fragment
                and re.fullmatch(r"L\d+", url.fragment)
                and int(url.fragment[1:])
                > len(resolved.read_text(encoding="utf-8").splitlines())
            ):
                errors.append(f"{page.relative_to(ROOT)}: invalid source line {target}")
        # Reference fences intentionally show signatures, not runnable scripts.
        if page.parent.name != "reference":
            for index, snippet in enumerate(
                re.findall(r"```python\n(.*?)\n```", content, re.S)
            ):
                try:
                    ast.parse(snippet)
                except SyntaxError as error:
                    errors.append(
                        f"{page.relative_to(ROOT)}: Python block {index}: {error}"
                    )
    for path, expected in generate().items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            errors.append(f"{path.relative_to(ROOT)}: regenerate API reference")
    return len(pages), errors


def main() -> None:
    count, errors = check()
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        f"{count} Markdown pages: bilingual parity, links, headings, snippets, and API reference checked"
    )


if __name__ == "__main__":
    main()
