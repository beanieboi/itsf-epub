# ITSF EPUB Workflow

This file documents how the project is maintained. The executable source of
truth is the `Justfile`; this document explains when to use each path and why
the cleanup script exists.

## Source Of Truth

The maintained book source is the unpacked EPUB tree in `src/`.

Generated files are ignored by Git:

- `Standard Matchplay Rules 2024 - ITSF.epub`
- everything under `build/`

Normal editing should happen in `src/`, followed by validation and a commit.

## Normal Edit Workflow

After editing XHTML/CSS/metadata in `src/`:

```sh
just format-xhtml
just validate
```

`just validate` performs:

1. XHTML well-formedness checks with `xmllint`
2. Sigil compatibility checks with `sigil_compat.py`
3. cover image regeneration
4. EPUB packaging from `src/`
5. EPUBCheck validation

The generated EPUB is:

```text
Standard Matchplay Rules 2024 - ITSF.epub
```

## Kindle Delivery

To build the latest EPUB and open an Apple Mail draft addressed to the Kindle:

```sh
just mail-to-kindle
```

The recipe attaches the generated EPUB and leaves the draft open so it can be
reviewed before sending.

## PDF Regeneration Workflow

The checked-in PDF can be converted with Calibre and then cleaned by the
project-specific cleanup script:

```sh
just validate-cleaned-epub
```

That performs:

```text
Standard Matchplay Rules 2024 - ITSF.pdf
  -> build/Standard Matchplay Rules 2024 - ITSF.calibre.epub
  -> build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub
  -> epubcheck
```

Use this path when the upstream PDF changes or when auditing whether the cleanup
script can still reproduce a valid structured EPUB from Calibre output.

The PDF regeneration path does not automatically replace `src/`. Treat
`build/...cleaned.epub` as an intermediate artifact to inspect and compare
before deciding whether to update `src/`.

## Cleanup Script Role

`cleanup_itsf_epub.py` is intentionally tailored to Calibre's current reflow of
the ITSF PDF. It performs structural cleanup that is hard to express as generic
EPUB tooling:

- removes repeated PDF page-artifact images
- splits Calibre's monolithic HTML into section files
- creates semantic headings and stable anchors
- fixes definition paragraph splits
- converts reflowed table paragraphs into real tables
- rewrites OPF/spine/navigation metadata
- applies semantic CSS class names
- normalizes Sigil-compatible XHTML serialization

If Calibre changes its generated HTML shape, the script may need updates.

## Current Generated Structure

The curated EPUB contains:

- `titlepage.xhtml`
- `contents.xhtml`
- `01-introduction.xhtml` through `18-penalties.xhtml`
- `nav.xhtml`
- `content.opf`
- `stylesheet.css`
- `page_styles.css`
- `cover.png`

`content.opf` declares `cover.png` as the cover image and points the Kindle
start location at `titlepage.xhtml`.

## External Dependencies

Required for normal editing and validation:

- `just` - runs the project recipes in `Justfile`
- `uv`
- `xmllint` - provided by libxml2; used for XHTML formatting and checks
- `zip` / `unzip`
- ImageMagick `magick`
- `epubcheck`
- Arial Unicode font at `/Library/Fonts/Arial Unicode.ttf`, used when
  regenerating `src/cover.png`

Optional workflow tools:

- Calibre's `ebook-convert` - required only for `just validate-cleaned-epub`
  and other PDF regeneration work
- Apple Mail and macOS `osascript` - required only for `just mail-to-kindle`
- Sigil - useful for manual EPUB inspection

On macOS with Homebrew, the command-line dependencies can be installed with:

```sh
brew install just uv imagemagick epubcheck
```

`xmllint`, `zip`, `unzip` and `osascript` are normally present on macOS. If
`xmllint` is missing, install libxml2:

```sh
brew install libxml2
```

For PDF regeneration, install Calibre and ensure `ebook-convert` is on `PATH`.

## Commit Policy

Commit maintained sources and workflow files:

- `src/`
- `Justfile`
- `cleanup_itsf_epub.py`
- `sigil_compat.py`
- documentation

Do not commit generated EPUB files or `build/` outputs.
