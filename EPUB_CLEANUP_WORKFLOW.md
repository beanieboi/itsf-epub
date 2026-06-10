# ITSF EPUB Cleanup Workflow

This documents the cleanup we applied to the Calibre-generated EPUB for
`Standard Matchplay Rules 2024 - ITSF.epub`, so the process can be repeated
after regenerating an EPUB from a newer PDF.

The maintained source of truth is the unpacked EPUB tree in `src/`. Generated
EPUB files are ignored by Git.

The normal generated output is:

`Standard Matchplay Rules 2024 - ITSF.epub`

It passes `epubcheck` with zero errors and zero warnings.

## Tools

Required:

- Calibre, to convert the source PDF to EPUB.
- `zip` / `unzip`.
- `uv`, to run Python scripts.
- `epubcheck`.

Useful manual check:

- Sigil.

## Current Justfile Workflow

Build the curated EPUB from `src/`:

```sh
just epub
```

Validate the curated EPUB:

```sh
just validate
```

Open a Mail draft to the Kindle address with the generated EPUB attached:

```sh
just mail-to-kindle
```

Regenerate the intermediate Calibre EPUB from the checked-in PDF:

```sh
just calibre-epub
```

Run the full PDF-to-cleaned-EPUB path and validate the result:

```sh
just validate-cleaned-epub
```

That command performs:

```text
Standard Matchplay Rules 2024 - ITSF.pdf
  -> build/Standard Matchplay Rules 2024 - ITSF.calibre.epub
  -> build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub
  -> epubcheck
```

The `build/` directory is generated and ignored by Git.

## Manual Cleanup Command

After creating a fresh EPUB from the PDF, run:

```sh
uv run --no-cache python cleanup_itsf_epub.py \
  "build/Standard Matchplay Rules 2024 - ITSF.calibre.epub" \
  "build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub"
```

Then validate:

```sh
epubcheck "build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub"
unzip -t "build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub"
ebook-convert "build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub" /private/tmp/itsf-cleaned.txt
```

The script is intentionally specific to the current Calibre/PDF reflow output
shape. If Calibre changes the generated class names or file names, inspect the
new EPUB in Sigil and update the regexes in the script.

## Changes Applied

### Image Cleanup

The original EPUB contained many byte-identical page-end PNGs:

- `index-2_1.png` through `index-41_1.png` were identical.
- They were repeated at the end of every source PDF page.
- The image was decorative/page-artifact content and was removed entirely.

The first-page logo image was kept:

- `index-1_1.png`

The bitmap cover was removed:

- `cover.jpeg`

The cover page now uses XHTML text plus the retained logo PNG.

### File Structure

The original conversion had nearly all content in:

- `index_split_002.html`

We split that monolithic file into one XHTML file per top-level numbered
section:

- `01-introduction.xhtml`
- `02-definitions.xhtml`
- `03-match-structure.xhtml`
- `04-prelude.xhtml`
- `05-putting-ball-into-play.xhtml`
- `06-possession.xhtml`
- `07-breaks-in-play.xhtml`
- `08-time-control.xhtml`
- `09-referee.xhtml`
- `10-spinning.xhtml`
- `11-passing.xhtml`
- `12-wall-contact.xhtml`
- `13-reaching-into-playing-area.xhtml`
- `14-switching-positions.xhtml`
- `15-impairing-play.xhtml`
- `16-changes-to-table.xhtml`
- `17-penalty-shot.xhtml`
- `18-penalties.xhtml`

The generated hardcoded table of contents was removed and replaced with:

- `contents.xhtml`

The OPF spine now contains:

1. `titlepage.xhtml`
2. `contents.xhtml`
3. the 18 section files

### Navigation

The NCX was regenerated.

Navigation includes:

- top-level sections `1` through `18`
- subsections such as `1.1`, `5.1`, `7.4`, `15.5`
- selected third-level subsections such as `5.1.1`, `5.1.2`, `7.1.1`, `7.4.3`

Rule and penalty labels were not added to the main TOC because that makes the
TOC too noisy, but they receive stable anchors.

### Semantic Headings

Generated paragraph/span headings like:

```html
<p class="calibre10"><span class="calibre6"><b>5 Putting the Ball into Play</b></span></p>
```

were converted to semantic headings:

```html
<h1 id="page_12"><span id="sec-5-putting-the-ball-into-play"></span>5 Putting the Ball into Play</h1>
```

Subsections become `h2` or `h3`.

The original `page_N` anchors are preserved because existing internal links
refer to them.

### Definitions Cleanup

The PDF reflow put several definitions into the same paragraph, for example:

```text
Dead ball: ... Defensive team: ...
```

In `02-definitions.xhtml`, each definition term now starts its own paragraph.

Every definition also receives a stable `def-*` anchor, for example:

```html
<p class="calibre10">
  <span id="def-dead-ball"></span>
  <i class="calibre19"><b class="calibre11">Dead ball</b></i><b class="calibre11">:</b>
  ...
</p>
```

Known malformed PDF-reflow cases handled by the script include:

- `Ball supply` / `Between games`
- `Pause` / `Paused possession`
- `Possession clock` / `Possession clock figure`
- `Restricted ball` / `Rocking ball`
- `Time-limited` / `Time-out`
- `Opposing player`
- `Tournament desk` / `Tournament director`

### Cover Cleanup

The original `cover.jpeg` was mostly text. It was replaced with real XHTML:

- retained logo image: `index-1_1.png`
- title text: `ITSF Rules of Table Soccer`
- subtitle: `Standard Matchplay Rules`
- version: `Version 2.0`
- date: `December 2023`

We briefly added `Translation last updated: 1 August 2024`, then removed it.
The final cover does not include that line.

### EPUBCheck / Sigil Fix

Sigil complained about missing or malformed `DOCTYPE`, `html`, `head`, or
`body` elements. The actual EPUBCheck errors were invalid standalone anchor
spans directly under `body`:

```html
<h1 id="page_4">1 Introduction</h1><span id="sec-1-introduction"></span>
```

In XHTML 1.1, inline `span` elements are not allowed directly under `body`.
The fix was:

```html
<h1 id="page_4"><span id="sec-1-introduction"></span>1 Introduction</h1>
```

We also added XHTML 1.1 DOCTYPEs and `xml:lang="en"` to all XHTML files.

Final validation command:

```sh
epubcheck "Standard Matchplay Rules 2024 - ITSF.structured-v5.epub"
```

Expected result:

```text
No errors or warnings detected.
```

## Manual Sigil Checklist

After running the script and validation:

1. Open the cleaned EPUB in Sigil.
2. Run Sigil validation.
3. Check the book browser:
   - no `cover.jpeg`
   - no `index_split_002.html`
   - no repeated `index-*_1.png` page artifacts
   - one title page, one contents page, 18 section files
4. Check the NCX/TOC tree.
5. Check `02-definitions.xhtml` for one definition per paragraph.
6. Check the cover visually.

## Send To Kindle Variant

Amazon Send to Kindle can fail with an opaque `E999` internal error even when an
EPUB is valid. In this session, the hand-cleaned EPUB2 file passed `epubcheck`,
but Send to Kindle still rejected one upload.

For Kindle, create a conservative EPUB3 variant by reserializing the cleaned
EPUB through Calibre:

```sh
ebook-convert \
  "Standard Matchplay Rules 2024 - ITSF.structured-v5.epub" \
  "Standard Matchplay Rules 2024 - ITSF.kindle.epub" \
  --output-profile kindle \
  --epub-version 3
```

Validate it:

```sh
epubcheck "Standard Matchplay Rules 2024 - ITSF.kindle.epub"
ebook-convert "Standard Matchplay Rules 2024 - ITSF.kindle.epub" /private/tmp/itsf-kindle-check.azw3
```

The Kindle variant should have:

- EPUB 3 package metadata
- `nav.xhtml`
- no `toc.ncx` requirement
- zero `epubcheck` errors or warnings

This is the file to try first with Send to Kindle.

If Send to Kindle still returns `E999`, create a more aggressively sanitized
EPUB3:

1. Unpack `Standard Matchplay Rules 2024 - ITSF.kindle.epub`.
2. In `content.opf`, replace the impossible Calibre date
   `0101-01-01T00:00:00+00:00` with a normal date such as `2023-12-01`.
3. Remove Calibre-only metadata/properties such as `calibre:title-page`,
   `calibre:timestamp`, and the `cover-image` property on the logo PNG.
4. Repackage as EPUB with `mimetype` first and uncompressed.
5. Validate with `epubcheck`.

In this session that produced:

`Standard Matchplay Rules 2024 - ITSF.kindle-sanitized.epub`

Also create a DOCX fallback:

```sh
ebook-convert \
  "Standard Matchplay Rules 2024 - ITSF.structured-v5.epub" \
  "Standard Matchplay Rules 2024 - ITSF.send-to-kindle.docx"
```

The DOCX route avoids Amazon's EPUB parser entirely and is often the most
practical workaround for opaque Send to Kindle `E999` failures.

If EPUB upload still fails, make an even simpler no-cover EPUB3:

- remove `titlepage.xhtml` from the OPF manifest and spine
- remove the cover image item
- remove `index-1_1.png`
- keep `contents.xhtml` as the first spine item

In this session that produced:

`Standard Matchplay Rules 2024 - ITSF.kindle-nocover.epub`

This variant is text-only and removes the cover-rendering path as a possible
Amazon converter failure point.

Another compromise is a text-cover EPUB3:

- keep `titlepage.xhtml`
- replace the logo image with plain text: `ITSF`
- remove `index-1_1.png` from the package
- remove the image item and cover-image metadata from `content.opf`

In this session that produced:

`Standard Matchplay Rules 2024 - ITSF.kindle-textcover.epub`

For Amazon upload, also keep a short filename copy:

`itsf-rules-text.epub`

If Send to Kindle still returns `E999`, create a diagnostic flat EPUB:

- one `content.xhtml`
- one `nav.xhtml`
- no CSS
- no images
- no cover
- plain metadata
- short filename

In this session that produced:

`itsf-rules-flat.epub`

Also keep a plain-text fallback:

`itsf-rules-flat.txt`

If Amazon rejects `itsf-rules-flat.epub`, the remaining likely causes are
Amazon/account-side processing or a content-specific parser bug rather than
normal EPUB packaging. Use the DOCX or TXT fallback at that point.
