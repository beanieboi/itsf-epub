#!/usr/bin/env python3
"""Normalize/check XHTML serialization patterns that Sigil rewrites."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


XML_DECL = '<?xml version="1.0" encoding="utf-8"?>'
HTML_DOCTYPE = "<!DOCTYPE html>"
CONTENT_TYPE_META_RE = re.compile(
    r'\n\s*<meta http-equiv="Content-Type" content="text/html; charset=utf-8"\s*/>'
)
DOCTYPE_RE = re.compile(r"\n?<!DOCTYPE[^>]*>(?:\n\s*\"[^\"]*\">)?", re.S)
EMPTY_SPAN_RE = re.compile(r"<span([^>]*)/>")


def xhtml_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.glob("*.xhtml"))


def normalize(text: str) -> str:
    text = text.replace("<?xml version='1.0' encoding='utf-8'?>", XML_DECL)
    text = DOCTYPE_RE.sub("", text, count=1)
    if text.startswith(XML_DECL):
        text = text.replace(XML_DECL, XML_DECL + "\n" + HTML_DOCTYPE, 1)
    else:
        text = XML_DECL + "\n" + HTML_DOCTYPE + "\n" + text.lstrip()
    text = CONTENT_TYPE_META_RE.sub("", text)
    text = EMPTY_SPAN_RE.sub(r"<span\1></span>", text)
    text = text.replace("\u00a0", "&#160;")
    return text


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    if not text.startswith(XML_DECL + "\n" + HTML_DOCTYPE):
        problems.append("missing HTML doctype after XML declaration")
    if CONTENT_TYPE_META_RE.search(text):
        problems.append("contains legacy Content-Type meta tag")
    if EMPTY_SPAN_RE.search(text):
        problems.append("contains self-closing span anchor")
    if "\u00a0" in text:
        problems.append("contains literal nonbreaking space")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report files that need Sigil-compatible normalization")
    parser.add_argument("--fix", action="store_true", help="rewrite files with Sigil-compatible normalization")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    if args.check == args.fix:
        parser.error("choose exactly one of --check or --fix")

    failed = False
    for root in args.paths:
        for path in xhtml_files(root):
            if args.fix:
                path.write_text(normalize(path.read_text(encoding="utf-8")), encoding="utf-8")
            else:
                problems = check(path)
                if problems:
                    failed = True
                    for problem in problems:
                        print(f"{path}: {problem}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
