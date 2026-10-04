import argparse
from pathlib import Path

from . import Document, apply_templates


def main():
    parser = argparse.ArgumentParser(
        description="Apply trusted Python karaoke templates to ASS subtitles"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--video-size", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"))
    args = parser.parse_args()
    try:
        result = apply_templates(Document.load(args.input), video_size=args.video_size)
        result.save(args.output)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"kara-templater: {error}\n")


if __name__ == "__main__":
    main()
