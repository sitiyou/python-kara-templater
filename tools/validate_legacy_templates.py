"""Compare this frontend to the actual v0.1.0 Python sources with identical metrics.

uv run python -m tools.validate_legacy_templates /tmp/legacy-validation
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

from kara_templater import Document, Line, Style, apply_templates

ROOT = Path(__file__).resolve().parents[1]


def cases() -> dict[str, Document]:
    def build(*lines: Line) -> Document:
        doc = Document.create(
            width=640, height=480, styles=(Style(fontname="DejaVu Sans"),)
        )
        doc.records.extend(lines)
        return doc

    def template(text: str, effect: str = "template syl noblank") -> Line:
        return Line(comment=True, effect=effect, text=text)

    def lyric(text: str = r"{\k20}a{\k30}b") -> Line:
        return Line(text=text, start_time=1000, end_time=2000)

    result = {
        "original_example": Document.load(ROOT / "tests/fixtures/v010-karaoke.ass"),
        "variables": build(
            template(r"{\pos($scenter,$smiddle)}$i:$dur:$lstart:"), lyric()
        ),
        "named_preline": build(
            template(r"{\an5}", "template pre-line joined"),
            template(r"{\k$kdur}", "template line joined"),
            lyric(),
        ),
        "code_loops_groups": build(
            template('count=0; fxgroup["skip"]=False', "code once"),
            template("count+=1", "code syl noblank"),
            template("!count!:!j!", "template syl noblank repeat 2"),
            template("skip", "template syl fxgroup skip"),
            lyric(),
        ),
        "char_multi_inline_fx": build(
            template("!retime('syl')!", "template syl char multi fx spark noblank"),
            lyric(r"{\k20\-spark}ab{\k30}#{\k20\-other}c"),
        ),
        "ruby_continuation": build(
            template("$sleft:!retime('syl')!", "template furi noblank"),
            lyric(r"{\k20}Ka|ka{\k30}#|!ra{\k20}o|<o"),
        ),
        "keep_tags": build(
            template("", "template syl keeptags noblank notext"), lyric(r"{\k20\i1}ab")
        ),
        "memory": build(
            template(
                '!remember_syl("v", syl.i)!!recall("v")!', "template syl noblank notext"
            ),
            lyric(),
        ),
        "loop_controls": build(
            template("!maxloops(2)!!j!", "template syl noblank notext"), lyric()
        ),
        "expression_quotes": build(
            template('!"yes!" if 1 != 2 else "no"!', "template syl noblank notext"),
            lyric(),
        ),
        "no_match": build(template("ignored", "template syl fx absent"), lyric()),
        "seeded_random": build(
            template("random.seed(17)", "code once"),
            template("!random.randint(0,100)!", "template syl noblank notext"),
            lyric(),
        ),
    }
    for mode in (
        "line",
        "preline",
        "postline",
        "syl",
        "presyl",
        "postsyl",
        "start2syl",
        "syl2end",
        "abs",
        "set",
        "sylpct",
    ):
        result[f"retime_{mode}"] = build(
            template(f"!retime('{mode}', -10, 20)!"), lyric()
        )
    return result


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    documents = cases()
    inputs = {name: doc.dumps() for name, doc in documents.items()}
    commit = subprocess.run(
        ["git", "rev-parse", "v0.1.0^{commit}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    spec = importlib.util.find_spec("kara_templater._metrics")
    assert spec is not None and spec.origin is not None
    metrics = Path(spec.origin)
    with tempfile.TemporaryDirectory(prefix="kara-v010-reference-") as directory:
        work = Path(directory)
        package = work / "kara_templater"
        package.mkdir()
        for filename in ("__init__.py", "ass.py", "layout.py", "engine.py"):
            original = subprocess.run(
                ["git", "show", f"{commit}:kara_templater/{filename}"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            ).stdout
            (package / filename).write_bytes(original)
        (package / metrics.name).write_bytes(metrics.read_bytes())
        runner = work / "compare.py"
        runner.write_text(
            "import json,sys\nfrom kara_templater import Document,apply_templates\n"
            "inputs=json.load(sys.stdin)\n"
            "json.dump({name:apply_templates(Document.parse(text)).dumps() for name,text in inputs.items()},sys.stdout)\n"
        )
        completed = subprocess.run(
            [sys.executable, str(runner)],
            cwd=work,
            input=json.dumps(inputs),
            capture_output=True,
            text=True,
            check=True,
        )
        references = json.loads(completed.stdout)
    evidence: dict[str, dict[str, str | bool]] = {}
    for name, document in documents.items():
        current = apply_templates(document)
        # Ownership comments are the only intentional serialization addition.
        current.records = [
            record
            for record in current.records
            if not (
                isinstance(record, Line)
                and record.comment
                and record.text == "kara native event follows"
                and record.effect.startswith("kara:scene:v1:legacy-templates:")
            )
        ]
        expected = references[name]
        actual = current.dumps()
        if actual != expected:
            (output / f"{name}-old.ass").write_text(expected)
            (output / f"{name}-new.ass").write_text(actual)
            raise AssertionError(f"v0.1.0 difference in {name}; artifacts in {output}")
        evidence[name] = {
            "identical_without_ownership_comments": True,
            "sha256": sha256(actual.encode()).hexdigest(),
        }
    report = {
        "baseline_commit": commit,
        "baseline_tag": "v0.1.0",
        "metrics": "same current native extension for both engines; Python semantics comparison",
        "case_count": len(evidence),
        "cases": evidence,
    }
    (output / "legacy-template-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        f"{len(evidence)} cases match v0.1.0 exactly after removing ownership comments"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
