#!/usr/bin/env python3
"""Clean the Calibre-generated ITSF Standard Matchplay Rules EPUB.

This script is intentionally tailored to the Calibre PDF-reflow output we
cleaned manually in this directory. It should be treated as semi-automated:
run it, validate with epubcheck, then inspect in Sigil.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import tempfile
import zipfile
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET


OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
XHTML_DOCTYPE = "<!DOCTYPE html>"
CLASS_RENAMES = {
    "calibre": "book-body",
    "calibre1": "section-title",
    "calibre2": "contents-list-ordered",
    "calibre3": "contents-item",
    "calibre4": "spacer",
    "calibre5": "subsection-title",
    "calibre6": "body-paragraph",
    "calibre7": "list-paragraph",
    "calibre8": "defined-term",
    "calibre9": "strong-text",
    "calibre10": "nested-list-paragraph",
    "calibre11": "subsubsection-title",
    "calibre12": "table-row-artifact",
    "calibre13": "table-header-continuation",
    "calibre14": "continuation-indent",
    "calibre15": "run-in-subheading",
    "calibre16": "nested-bullet-paragraph",
    "calibre17": "wide-indent-artifact",
    "calibre18": "table-cell-continuation",
    "calibre19": "deep-continuation-indent",
    "calibre20": "cover-body",
    "rules-table-narrow-last": "rules-table-duration-last",
    "rules-table-narrow-limit": "rules-table-time-limit-column",
    "toc-level": "toc-level-2",
    "toc-level1": "toc-level-3",
}
SECTION_FILES = {
    "1": "01-introduction.xhtml",
    "2": "02-definitions.xhtml",
    "3": "03-match-structure.xhtml",
    "4": "04-prelude.xhtml",
    "5": "05-putting-ball-into-play.xhtml",
    "6": "06-possession.xhtml",
    "7": "07-breaks-in-play.xhtml",
    "8": "08-time-control.xhtml",
    "9": "09-referee.xhtml",
    "10": "10-spinning.xhtml",
    "11": "11-passing.xhtml",
    "12": "12-wall-contact.xhtml",
    "13": "13-reaching-into-playing-area.xhtml",
    "14": "14-switching-positions.xhtml",
    "15": "15-impairing-play.xhtml",
    "16": "16-changes-to-table.xhtml",
    "17": "17-penalty-shot.xhtml",
    "18": "18-penalties.xhtml",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def slug(text: str, prefix: str = "") -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return prefix + value


def clean_text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", html).split())


def xhtml_shell(title: str, body: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
{XHTML_DOCTYPE}
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
  <head>
    <title>{escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="stylesheet.css" />
    <link rel="stylesheet" type="text/css" href="page_styles.css" />
  </head>
  <body class="calibre">
{body}
  </body>
</html>
'''


def find_main_html(root: Path) -> Path:
    candidates = []
    for path in root.glob("*.html"):
        text = read(path)
        if "TABLE OF CONTENTS" in text and "Introduction" in text and "Penalties" in text:
            candidates.append(path)
    if not candidates:
        raise SystemExit("Could not find Calibre monolithic content HTML.")
    return max(candidates, key=lambda p: p.stat().st_size)


def try_find_main_html(root: Path) -> Path | None:
    try:
        return find_main_html(root)
    except SystemExit:
        return None


def find_logo_image(root: Path) -> str:
    for path in sorted(root.glob("*.html")):
        text = read(path)
        if 'id="page_1"' in text:
            match = re.search(r'<img src="([^"]+)"', text)
            if match:
                return match.group(1)
    return "index-1_1.png"


def remove_page_artifact_images(root: Path, main_html: Path) -> None:
    images = [p for p in root.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    groups: dict[str, list[Path]] = {}
    for image in images:
        groups.setdefault(sha256(image), []).append(image)
    duplicate_groups = [g for g in groups.values() if len(g) > 1 and all(p.suffix.lower() == ".png" for p in g)]
    if not duplicate_groups:
        return
    artifact_names = {p.name for p in max(duplicate_groups, key=len)}
    text = read(main_html)
    for name in artifact_names:
        text = re.sub(
            rf'\s*<p class="calibre10"><img src="{re.escape(name)}" alt="" class="calibre18"\s*/></p>\s*',
            "\n",
            text,
        )
    write(main_html, text)
    for image in artifact_names:
        path = root / image
        if path.exists():
            path.unlink()


def split_sections(root: Path, main_html: Path) -> tuple[list[dict[str, object]], list[tuple[int, str, str, str]]]:
    text = read(main_html)
    body = re.search(r'<body class="calibre">(.*)</body>', text, re.S).group(1)
    lines = body.splitlines()

    top_re = re.compile(
        r'<p([^>]*)class="calibre10"([^>]*)><span class="calibre6"><b class="calibre5">\s*(\d+)\s+([^<]+?)\s*</b></span></p>'
    )
    h2_re = re.compile(
        r'<p([^>]*)class="calibre10"([^>]*)><span class="calibre7">\s*((\d+(?:\.\d+)+)\s+[^<]+?)\s*</span></p>'
    )
    h3_re = re.compile(
        r'<p([^>]*)class="calibre10"([^>]*)><span class="calibre17">\s*((\d+(?:\.\d+){2,})\s+[^<]+?)\s*</span></p>'
    )
    page_num_re = re.compile(r'<p class="calibre1"><span class="calibre17"><b class="calibre5">\d+</b></span></p>')

    chapters: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        match = top_re.search(line)
        if match:
            if current:
                chapters.append(current)
            num = match.group(3)
            current = {"num": num, "title": clean_text(f"{num} {match.group(4)}"), "lines": [line]}
        elif current:
            current["lines"].append(line)  # type: ignore[index]
    if current:
        chapters.append(current)
    if len(chapters) != 18:
        raise SystemExit(f"Expected 18 sections, found {len(chapters)}")

    for chapter in chapters:
        chapter["file"] = SECTION_FILES[str(chapter["num"])]

    page_to_file: dict[str, str] = {}
    for chapter in chapters:
        joined = "\n".join(chapter["lines"])  # type: ignore[arg-type]
        for page in re.findall(r'id="(page_\d+)"', joined):
            page_to_file[page] = str(chapter["file"])

    def rewrite_links(line: str) -> str:
        def repl(match: re.Match[str]) -> str:
            page = match.group(1)
            return f'href="{page_to_file.get(page, "contents.xhtml")}#{page}"'

        return re.sub(r'href="[^"]*#(page_\d+)"', repl, line)

    used_ids: set[str] = set()
    outline: list[tuple[int, str, str, str]] = []

    def unique_id(base_id: str) -> str:
        value = base_id
        index = 2
        while value in used_ids:
            value = f"{base_id}-{index}"
            index += 1
        used_ids.add(value)
        return value

    def transform_heading(line: str, level: int, title: str, filename: str, attrs: str) -> str:
        page_match = re.search(r'id="([^"]+)"', attrs)
        page_id = page_match.group(1) if page_match else None
        clean = clean_text(title)
        section_id = unique_id(slug(clean, "sec-"))
        anchor = f'<span id="{section_id}"></span>'
        tag = f"h{level}"
        target = page_id or section_id
        outline.append((level, clean, filename, target))
        if page_id:
            return f'<{tag} id="{page_id}">{anchor}{escape(clean)}</{tag}>'
        return f'<{tag} id="{section_id}">{escape(clean)}</{tag}>'

    def add_rule_anchor(match: re.Match[str]) -> str:
        label = clean_text(match.group(1))
        prefix = "rule-" if label.startswith("Rule:") else "penalty-"
        ident = unique_id(slug(label.split(":", 1)[1], prefix))
        return f'<span id="{ident}"></span><b class="calibre11">{escape(label)}</b>'

    for chapter in chapters:
        filename = str(chapter["file"])
        out: list[str] = []
        for raw_line in chapter["lines"]:  # type: ignore[union-attr]
            line = rewrite_links(str(raw_line))
            if page_num_re.fullmatch(line.strip()):
                continue
            if match := top_re.search(line):
                out.append(transform_heading(line, 1, f'{match.group(3)} {match.group(4)}', filename, match.group(1) + match.group(2)))
            elif match := h3_re.search(line):
                out.append(transform_heading(line, 3, match.group(3), filename, match.group(1) + match.group(2)))
            elif match := h2_re.search(line):
                out.append(transform_heading(line, 2, match.group(3), filename, match.group(1) + match.group(2)))
            else:
                line = re.sub(r'<b class="calibre11">((?:Rule|Penalty):.*?)</b>', add_rule_anchor, line)
                out.append(line)
        write(root / filename, xhtml_shell("Standard Matchplay Rules 2024", "\n".join(out)))

    main_html.unlink()
    return chapters, outline


def normalize_definitions(root: Path) -> None:
    path = root / "02-definitions.xhtml"
    text = read(path)
    fixes = {
        '<i class="calibre19">match. <b class="calibre11">Between games</b></i>:':
            '<i class="calibre19">match</i>.</p>\n<p class="calibre10"><i class="calibre19"><b class="calibre11">Between games</b></i>:',
        '<i class="calibre19">between games. <b class="calibre11">Paused possession</b></i><b class="calibre11">:</b>':
            '<i class="calibre19">between games</i>.</p>\n<p class="calibre10"><i class="calibre19"><b class="calibre11">Paused possession</b></i><b class="calibre11">:</b>',
        '<i class="calibre19">active possession. <b class="calibre11">Possession clock figure</b></i><b class="calibre11">:</b>':
            '<i class="calibre19">active possession</i>.</p>\n<p class="calibre10"><i class="calibre19"><b class="calibre11">Possession clock figure</b></i><b class="calibre11">:</b>',
        '<i class="calibre19">adjusted. <b class="calibre11">Rocking ball</b></i><b class="calibre11">:</b>':
            '<i class="calibre19">adjusted</i>.</p>\n<p class="calibre10"><i class="calibre19"><b class="calibre11">Rocking ball</b></i><b class="calibre11">:</b>',
        '<i class="calibre19">time-out, between points, between games. <b class="calibre11">Time-out</b></i><b class="calibre11">:</b>':
            '<i class="calibre19">time-out, between points, between games</i>.</p>\n<p class="calibre10"><i class="calibre19"><b class="calibre11">Time-out</b></i><b class="calibre11">:</b>',
    }
    for old, new in fixes.items():
        text = text.replace(old, new)
    text = re.sub(
        r'(?<!<p class="calibre10">)\s+(<i class="calibre19"><b class="calibre11">[^<]+</b></i>(?:<b class="calibre11">:</b>|:))',
        r'</p>\n<p class="calibre10">\1',
        text,
    )
    text = text.replace(
        '<p class="calibre10"><i class="calibre19"><b class="calibre11">Opposing player:</b></i> The player who controls the rod that directly opposes the rod of <i class="calibre19">possession.</i></p>',
        '<p class="calibre10"><span id="def-opposing-player"></span><i class="calibre19"><b class="calibre11">Opposing player</b></i><b class="calibre11">:</b> The player who controls the rod that directly opposes the rod of <i class="calibre19">possession</i>.</p>',
    )
    text = text.replace(
        ' <i class="calibre19"><b class="calibre11">Tournament director:</b></i> The person who plans and manages the administration of tournament play.</p>',
        '</p>\n<p class="calibre10"><span id="def-tournament-director"></span><i class="calibre19"><b class="calibre11">Tournament director</b></i><b class="calibre11">:</b> The person who plans and manages the administration of tournament play.</p>',
    )

    seen: set[str] = set(re.findall(r'id="(def-[^"]+)"', text))

    def repl(match: re.Match[str]) -> str:
        term = clean_text(match.group(1)).rstrip(":")
        ident = slug(term, "def-")
        if ident in seen:
            return match.group(0)
        seen.add(ident)
        return f'<span id="{ident}"></span>{match.group(0)}'

    text = re.sub(r'(<i class="calibre19"><b class="calibre11">[^<]+</b></i>(?:<b class="calibre11">:</b>|:))', repl, text)
    write(path, text)


def normalize_definition_page_breaks(root: Path) -> None:
    path = root / "02-definitions.xhtml"
    if not path.exists():
        return
    text = read(path)
    text = re.sub(
        r'\n<p class="calibre4">\s*</p>\n<p id="(page_\d+)" class="([^"]+)">',
        r'\n<p class="\2"><span id="\1"></span>',
        text,
    )
    text = re.sub(
        r'<p id="(page_\d+)" class="([^"]+)">',
        r'<p class="\2"><span id="\1"></span>',
        text,
    )
    text = re.sub(r'\n<p class="calibre4">\s*</p>\n</body>', "\n</body>", text)
    write(path, text)


def normalize_time_management_table(root: Path) -> None:
    path = root / "05-putting-ball-into-play.xhtml"
    if not path.exists():
        return
    text = read(path)
    table = '''<table class="rules-table rules-table-duration-last">
  <caption>Table: Time management when putting the ball into play</caption>
  <thead>
    <tr>
      <th scope="col">Stage</th>
      <th scope="col">Stage ends when</th>
      <th scope="col">Maximum duration</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Retrieve and position the ball</td>
      <td>Ball positioned at <i class="calibre8">restart</i> location</td>
      <td>3s</td>
    </tr>
    <tr>
      <td>“Ready?” prompt</td>
      <td>“Ready?” prompt offered</td>
      <td>3s</td>
    </tr>
    <tr>
      <td>“Ready!” response</td>
      <td>“Ready!” response given</td>
      <td>3s</td>
    </tr>
    <tr>
      <td>“Ready!” response given</td>
      <td>Make contact with the <i class="calibre8">possession clock figure</i></td>
      <td>3s</td>
    </tr>
  </tbody>
</table>'''
    pattern = re.compile(
        r'<p class="calibre6"><b class="calibre9">Table: Time management when putting the ball into play</b></p>\n'
        r'<p class="calibre4"><b class="calibre9">Stage</b>\s+<b class="calibre9">Stage ends when</b>\s+<b class="calibre9">Maximum</b></p>\n'
        r'<p class="calibre13"><b class="calibre9">duration</b></p>\n'
        r'<p class="calibre12">Retrieve and position the ball\s+Ball positioned at <i class="calibre8">restart</i> location\s+3s</p>\n'
        r'<p class="calibre12">“Ready\?” prompt\s+“Ready\?” prompt offered\s+3s</p>\n'
        r'<p class="calibre12">“Ready!” response\s+“Ready!” response given\s+3s</p>\n'
        r'<p class="calibre12">“Ready!” response given\s+Make contact with the <i class="calibre8">possession clock figure</i>\s+3s</p>'
    )
    text = pattern.sub(table, text, count=1)
    write(path, text)


def normalize_reflowed_tables(root: Path) -> None:
    replacements = {
        "05-putting-ball-into-play.xhtml": [
            (
                '''<p class="calibre12"><b class="calibre9">Preceding Event</b>                       <b class="calibre9">Legal restart location</b></p>
<p class="calibre12"><i class="calibre8">Time-out</i> during <i class="calibre8">active play</i>                 <i class="calibre8">Current location</i> of the ball</p>
<p class="calibre12"><i class="calibre8">Interrupt</i> during <i class="calibre8">active play</i>                   <i class="calibre8">Current location</i> of the ball</p>
<p class="calibre4"> </p>
<p id="page_13" class="calibre12">Start of game or point scored                <i class="calibre8">Kick-off</i></p>
<p class="calibre12"><i class="calibre8">Dead ball</i> between the 5-rods              <i class="calibre8">Kick-off</i></p>
<p class="calibre12"><i class="calibre8">Dead ball</i> behind a 5-rod                   Any <i class="calibre8">figure</i> on the nearest <i class="calibre8">goalie rod</i></p>
<p class="calibre12">Ball off Table                                  Any figure on the relevant <i class="calibre8">goalie rod</i></p>
<p class="calibre12">5-rod Possession Award                  Central 5-rod <i class="calibre8">figure</i> of non-offending team</p>
<p class="calibre12">Goalie rod Possession Award              Any <i class="calibre8">figure</i> on the <i class="calibre8">goalie rod</i> of non-offending team</p>
<p class="calibre12">Team chooses ‘Continue’ penalty option     <i class="calibre8">Current location</i> of the ball</p>
<p class="calibre12">Team chooses ‘Restart’ penalty option      Location of the ball at the point of infraction</p>
<p class="calibre12">Penalty shot                               Any <i class="calibre8">figure</i> on the 3-rod of non-offending team</p>''',
                '''<table class="rules-table">
  <thead>
    <tr>
      <th scope="col">Preceding event</th>
      <th scope="col">Legal restart location</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><i class="calibre8">Time-out</i> during <i class="calibre8">active play</i></td>
      <td><i class="calibre8">Current location</i> of the ball</td>
    </tr>
    <tr>
      <td><i class="calibre8">Interrupt</i> during <i class="calibre8">active play</i></td>
      <td><i class="calibre8">Current location</i> of the ball</td>
    </tr>
    <tr>
      <td><span id="page_13"></span>Start of game or point scored</td>
      <td><i class="calibre8">Kick-off</i></td>
    </tr>
    <tr>
      <td><i class="calibre8">Dead ball</i> between the 5-rods</td>
      <td><i class="calibre8">Kick-off</i></td>
    </tr>
    <tr>
      <td><i class="calibre8">Dead ball</i> behind a 5-rod</td>
      <td>Any <i class="calibre8">figure</i> on the nearest <i class="calibre8">goalie rod</i></td>
    </tr>
    <tr>
      <td>Ball off Table</td>
      <td>Any figure on the relevant <i class="calibre8">goalie rod</i></td>
    </tr>
    <tr>
      <td>5-rod Possession Award</td>
      <td>Central 5-rod <i class="calibre8">figure</i> of non-offending team</td>
    </tr>
    <tr>
      <td>Goalie rod Possession Award</td>
      <td>Any <i class="calibre8">figure</i> on the <i class="calibre8">goalie rod</i> of non-offending team</td>
    </tr>
    <tr>
      <td>Team chooses ‘Continue’ penalty option</td>
      <td><i class="calibre8">Current location</i> of the ball</td>
    </tr>
    <tr>
      <td>Team chooses ‘Restart’ penalty option</td>
      <td>Location of the ball at the point of infraction</td>
    </tr>
    <tr>
      <td>Penalty shot</td>
      <td>Any <i class="calibre8">figure</i> on the 3-rod of non-offending team</td>
    </tr>
  </tbody>
</table>''',
            ),
        ],
        "07-breaks-in-play.xhtml": [
            (
                '''<p class="calibre6"><b class="calibre9">Table: Time management for</b> <i class="calibre8"><b class="calibre9">pauses</b></i></p>
<p class="calibre6"><b class="calibre9">Pause</b>          <b class="calibre9">Pause begins when</b>                   <b class="calibre9">Maximum duration</b></p>
<p class="calibre12"><i class="calibre8">Between points</i>    Goal scored that does not end the <i class="calibre8">game</i>               5 seconds</p>
<p class="calibre12"><i class="calibre8">Between games</i>   Goal scored that ends the <i class="calibre8">game</i>                     90 seconds</p>
<p class="calibre12"><i class="calibre8">Time-out</i>          Player calls a <i class="calibre8">time-out</i>                                30 seconds</p>''',
                '''<table class="rules-table rules-table-duration-last">
  <caption>Table: Time management for <i class="calibre8">pauses</i></caption>
  <thead>
    <tr>
      <th scope="col">Pause</th>
      <th scope="col">Pause begins when</th>
      <th scope="col">Maximum duration</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><i class="calibre8">Between points</i></td>
      <td>Goal scored that does not end the <i class="calibre8">game</i></td>
      <td>5 seconds</td>
    </tr>
    <tr>
      <td><i class="calibre8">Between games</i></td>
      <td>Goal scored that ends the <i class="calibre8">game</i></td>
      <td>90 seconds</td>
    </tr>
    <tr>
      <td><i class="calibre8">Time-out</i></td>
      <td>Player calls a <i class="calibre8">time-out</i></td>
      <td>30 seconds</td>
    </tr>
  </tbody>
</table>''',
            ),
            (
                '''<p class="calibre12"><b class="calibre9">Location of Dead ball</b>     <b class="calibre9">Where to restart</b></p>
<p class="calibre12">Between the 5-rods         <i class="calibre8">Kick-off</i></p>
<p class="calibre12">Behind the 5-rod            Any <i class="calibre8">figure</i> on the nearest <i class="calibre8">goalie rod</i></p>''',
                '''<table class="rules-table">
  <thead>
    <tr>
      <th scope="col">Location of dead ball</th>
      <th scope="col">Where to restart</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Between the 5-rods</td>
      <td><i class="calibre8">Kick-off</i></td>
    </tr>
    <tr>
      <td>Behind the 5-rod</td>
      <td>Any <i class="calibre8">figure</i> on the nearest <i class="calibre8">goalie rod</i></td>
    </tr>
  </tbody>
</table>''',
            ),
        ],
    }
    for filename, pairs in replacements.items():
        path = root / filename
        if not path.exists():
            continue
        text = read(path)
        for old, new in pairs:
            text = text.replace(old, new)
        write(path, text)


def ensure_table_css(root: Path) -> None:
    css_path = root / "stylesheet.css"
    if not css_path.exists():
        return
    css = read(css_path)
    if ".rules-table {" not in css:
        css += """

.rules-table {
  border-collapse: collapse;
  margin: 1em 0;
  width: 100%;
}
.rules-table caption {
  caption-side: top;
  font-weight: bold;
  margin: 0 0 0.5em 0;
  text-align: left;
}
.rules-table th,
.rules-table td {
  border: 1px solid #777;
  padding: 0.35em 0.5em;
  text-align: left;
  vertical-align: top;
}
.rules-table th {
  font-weight: bold;
}
"""
    if ".rules-table-duration-last" not in css:
        css += """
.rules-table-duration-last th:last-child,
.rules-table-duration-last td:last-child {
  text-align: center;
  white-space: nowrap;
  width: 5em;
}
"""
    if ".rules-table-time-limit-column" not in css:
        css += """
.rules-table-time-limit-column th:nth-child(3),
.rules-table-time-limit-column td:nth-child(3) {
  text-align: center;
  white-space: nowrap;
  width: 5em;
}
"""
    write(css_path, css)


def create_cover(root: Path, logo: str) -> None:
    cover = f'''<?xml version="1.0" encoding="utf-8"?>
{XHTML_DOCTYPE}
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
  <title>Standard Matchplay Rules 2024</title>
  <meta name="calibre:cover" content="true" />
  <link rel="stylesheet" type="text/css" href="stylesheet.css" />
  <link rel="stylesheet" type="text/css" href="page_styles.css" />
</head>
<body class="cover-body cover-page">
  <div class="cover-block">
    <img class="cover-logo" src="{escape(logo)}" alt="ITSF Rules of Table Soccer" />
    <h1 id="cover-title">ITSF Rules of Table Soccer</h1>
    <p class="cover-subtitle">Standard Matchplay Rules</p>
    <p class="cover-version">Version 2.0</p>
    <p class="cover-date">December 2023</p>
  </div>
</body>
</html>
'''
    write(root / "titlepage.xhtml", cover)


def create_contents(root: Path, outline: list[tuple[int, str, str, str]]) -> None:
    lines = ['<h1 id="contents">Contents</h1>', '<div class="contents-list">', '<ol>']
    for level, title, filename, anchor in outline:
        cls = f' class="toc-level-{level}"' if level > 1 else ""
        lines.append(f'<li{cls}><a href="{filename}#{anchor}">{escape(title)}</a></li>')
    lines.extend(["</ol>", "</div>"])
    write(root / "contents.xhtml", xhtml_shell("Contents", "\n".join(lines)))


def append_css(root: Path) -> None:
    css = read(root / "stylesheet.css")
    css += """

h1 {
  display: block;
  font-size: 1.5em;
  font-weight: bold;
  line-height: 1.2;
  margin: 1em 0 0.67em 0;
}
h2 {
  display: block;
  font-size: 1.375em;
  font-weight: normal;
  line-height: 1.2;
  margin: 1em 0 0.5em 0;
}
h3 {
  display: block;
  font-size: 1.25em;
  font-weight: normal;
  line-height: 1.2;
  margin: 1em 0 0.5em 0;
}
.toc-level-2 {
  margin-left: 1.5em;
}
.toc-level-3 {
  margin-left: 3em;
}
.cover-page {
  text-align: center;
}
.cover-block {
  display: block;
  margin: 12% auto 0 auto;
  max-width: 32em;
}
.cover-logo {
  display: block;
  height: auto;
  max-width: 18em;
  width: 70%;
  margin: 0 auto 2em auto;
}
.cover-subtitle,
.cover-version,
.cover-date {
  display: block;
  text-align: center;
  margin: 1em 0;
}
.cover-subtitle {
  font-size: 1.5em;
  font-weight: bold;
}
.cover-version {
  font-size: 1.25em;
  font-weight: bold;
}
.cover-date {
  font-size: 1.125em;
  font-weight: bold;
  text-transform: uppercase;
}
"""
    write(root / "stylesheet.css", css)


def rewrite_opf(root: Path, chapters: list[dict[str, object]], logo: str) -> None:
    ET.register_namespace("opf", OPF_NS)
    ET.register_namespace("dc", DC_NS)
    opf_path = root / "content.opf"
    tree = ET.parse(opf_path)
    package = tree.getroot()
    metadata = package.find(f"{{{OPF_NS}}}metadata")
    manifest = package.find(f"{{{OPF_NS}}}manifest")
    spine = package.find(f"{{{OPF_NS}}}spine")
    guide = package.find(f"{{{OPF_NS}}}guide")
    if manifest is None or spine is None:
        raise SystemExit("Invalid OPF: missing manifest or spine")
    if metadata is not None:
        for meta in list(metadata):
            if meta.tag == f"{{{OPF_NS}}}meta" and meta.get("name") == "cover":
                metadata.remove(meta)
        ET.SubElement(metadata, f"{{{OPF_NS}}}meta", {"name": "cover", "content": "cover"})
    manifest.clear()
    spine.clear()
    spine.set("toc", "ncx")
    items = [
        ("titlepage", "titlepage.xhtml", "application/xhtml+xml"),
        ("contents", "contents.xhtml", "application/xhtml+xml"),
    ]
    items += [(f'section-{c["num"]}', str(c["file"]), "application/xhtml+xml") for c in chapters]
    items += [
        ("page_css", "page_styles.css", "text/css"),
        ("css", "stylesheet.css", "text/css"),
        ("ncx", "toc.ncx", "application/x-dtbncx+xml"),
        ("cover", logo, "image/png"),
    ]
    for item_id, href, media_type in items:
        attrs = {"id": item_id, "href": href, "media-type": media_type}
        if item_id == "cover":
            attrs["properties"] = "cover-image"
        ET.SubElement(manifest, f"{{{OPF_NS}}}item", attrs)
    for item_id in ["titlepage", "contents"] + [f'section-{c["num"]}' for c in chapters]:
        ET.SubElement(spine, f"{{{OPF_NS}}}itemref", {"idref": item_id})
    if guide is not None:
        guide.clear()
        ET.SubElement(guide, f"{{{OPF_NS}}}reference", {"type": "cover", "title": "Cover", "href": "titlepage.xhtml"})
    tree.write(opf_path, encoding="utf-8", xml_declaration=True)


def write_ncx(root: Path, outline: list[tuple[int, str, str, str]]) -> None:
    ncx = ET.Element("ncx", {"xmlns": "http://www.daisy.org/z3986/2005/ncx/", "version": "2005-1", "{http://www.w3.org/XML/1998/namespace}lang": "eng"})
    head = ET.SubElement(ncx, "head")
    for name, content in [
        ("dtb:uid", "b6afe5d3-8519-498f-8206-7583056261dc"),
        ("dtb:depth", "3"),
        ("dtb:generator", "cleanup_itsf_epub.py"),
        ("dtb:totalPageCount", "0"),
        ("dtb:maxPageNumber", "0"),
    ]:
        ET.SubElement(head, "meta", {"name": name, "content": content})
    doc_title = ET.SubElement(ncx, "docTitle")
    ET.SubElement(doc_title, "text").text = "Standard Matchplay Rules 2024"
    nav = ET.SubElement(ncx, "navMap")
    parents: dict[int, ET.Element] = {0: nav}
    play = 1
    np = ET.SubElement(nav, "navPoint", {"id": "contents", "playOrder": str(play)})
    ET.SubElement(ET.SubElement(np, "navLabel"), "text").text = "Contents"
    ET.SubElement(np, "content", {"src": "contents.xhtml#contents"})
    play += 1
    for level, title, filename, anchor in outline:
        parent = nav if level == 1 else parents.get(level - 1, nav)
        point = ET.SubElement(parent, "navPoint", {"id": "nav-" + slug(title), "playOrder": str(play)})
        ET.SubElement(ET.SubElement(point, "navLabel"), "text").text = title
        ET.SubElement(point, "content", {"src": f"{filename}#{anchor}"})
        parents[level] = point
        for key in list(parents):
            if key > level:
                del parents[key]
        play += 1
    ET.ElementTree(ncx).write(root / "toc.ncx", encoding="utf-8", xml_declaration=True)


def remove_unmanifested(root: Path) -> None:
    keep = {"mimetype", "content.opf", "toc.ncx", "stylesheet.css", "page_styles.css", "index-1_1.png", "titlepage.xhtml", "contents.xhtml", "META-INF"}
    keep.update(SECTION_FILES.values())
    for path in root.iterdir():
        if path.name not in keep:
            if path.is_dir() and path.name != "META-INF":
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()


def normalize_xhtml_validity(root: Path) -> None:
    """Make existing XHTML files friendlier to Sigil/EPUBCheck."""
    for path in sorted(root.glob("*.xhtml")):
        text = read(path)
        text = text.replace("<?xml version='1.0' encoding='utf-8'?>", '<?xml version="1.0" encoding="utf-8"?>')
        text = re.sub(r"\n?<!DOCTYPE[^>]*>(?:\n\s*\"[^\"]*\">)?", "", text, count=1)
        if "<!DOCTYPE" not in text[:300]:
            text = text.replace('<?xml version="1.0" encoding="utf-8"?>', '<?xml version="1.0" encoding="utf-8"?>\n' + XHTML_DOCTYPE, 1)
        text = re.sub(r'\n\s*<meta http-equiv="Content-Type" content="text/html; charset=utf-8"\s*/>', "", text)
        text = re.sub(r'<span([^>]*)/>', r'<span\1></span>', text)
        text = re.sub(
            r'<html xmlns="http://www\.w3\.org/1999/xhtml">',
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">',
            text,
            count=1,
        )
        text = re.sub(
            r'<(h[1-3]) id="([^"]+)">([^<]*)</\1><span id="([^"]+)"></span>',
            r'<\1 id="\2"><span id="\4"></span>\3</\1>',
            text,
        )
        text = text.replace('\n    <p class="cover-translation-update">Translation last updated: 1 August 2024</p>', "")
        write(path, text)
    css_path = root / "stylesheet.css"
    if css_path.exists():
        css = read(css_path)
        css = re.sub(
            r"\.cover-translation-update \{\n  display: block;\n  font-size: 0\.95em;\n  text-align: center;\n  margin: 2em 0 0 0;\n\}\n",
            "",
            css,
        )
        write(css_path, css)


def apply_semantic_class_names(root: Path) -> None:
    """Replace Calibre-generated class tokens with document-oriented names."""

    def repl(match: re.Match[str]) -> str:
        tokens = match.group(1).split()
        renamed = [CLASS_RENAMES.get(token, token) for token in tokens]
        return 'class="' + " ".join(renamed) + '"'

    for path in sorted(root.glob("*.xhtml")):
        text = read(path)
        text = re.sub(r'class="([^"]+)"', repl, text)
        write(path, text)

    css_path = root / "stylesheet.css"
    if css_path.exists():
        css = read(css_path)
        for old, new in sorted(CLASS_RENAMES.items(), key=lambda item: len(item[0]), reverse=True):
            css = re.sub(rf"(?<=\.){re.escape(old)}\b", new, css)
        write(css_path, css)


def package_epub(root: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w") as zf:
        zf.write(root / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(root.rglob("*")):
            if path.name == "mimetype" or path.is_dir():
                continue
            zf.write(path, path.relative_to(root).as_posix(), compress_type=zipfile.ZIP_DEFLATED)


def clean(input_epub: Path, output_epub: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="itsf-epub-clean-") as tmp:
        root = Path(tmp) / "epub"
        root.mkdir()
        with zipfile.ZipFile(input_epub) as zf:
            zf.extractall(root)
        main_html = try_find_main_html(root)
        if main_html is None:
            normalize_xhtml_validity(root)
            normalize_definitions(root)
            normalize_definition_page_breaks(root)
            normalize_reflowed_tables(root)
            normalize_time_management_table(root)
            ensure_table_css(root)
            apply_semantic_class_names(root)
        else:
            logo = find_logo_image(root)
            remove_page_artifact_images(root, main_html)
            chapters, outline = split_sections(root, main_html)
            normalize_definitions(root)
            normalize_definition_page_breaks(root)
            normalize_reflowed_tables(root)
            normalize_time_management_table(root)
            create_cover(root, logo)
            create_contents(root, outline)
            append_css(root)
            ensure_table_css(root)
            rewrite_opf(root, chapters, logo)
            write_ncx(root, outline)
            remove_unmanifested(root)
            normalize_xhtml_validity(root)
            apply_semantic_class_names(root)
        package_epub(root, output_epub)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_epub", type=Path)
    parser.add_argument("output_epub", type=Path)
    args = parser.parse_args()
    clean(args.input_epub, args.output_epub)


if __name__ == "__main__":
    main()
