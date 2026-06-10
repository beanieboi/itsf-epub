set shell := ["zsh", "-cu"]

src := "src"
pdf := "Standard Matchplay Rules 2024 - ITSF.pdf"
epub := "Standard Matchplay Rules 2024 - ITSF.epub"
calibre_epub := "build/Standard Matchplay Rules 2024 - ITSF.calibre.epub"
cleaned_epub := "build/Standard Matchplay Rules 2024 - ITSF.cleaned.epub"
cover_font := "/Library/Fonts/Arial Unicode.ttf"

default: epub

check-xhtml:
    xmllint --nonet --noout "{{src}}"/*.xhtml
    uv run --no-cache python scripts/sigil_compat.py --check "{{src}}"

format-xhtml:
    for file in "{{src}}"/*.xhtml; do xmllint --nonet --format "$file" > "$file.tmp" && mv "$file.tmp" "$file"; done
    uv run --no-cache python scripts/sigil_compat.py --fix "{{src}}"

calibre-epub output=calibre_epub:
    mkdir -p build
    ebook-convert "{{pdf}}" "{{output}}" --epub-version 3

clean-calibre-epub input=calibre_epub output=cleaned_epub: (calibre-epub input)
    mkdir -p build
    uv run --no-cache python cleanup_itsf_epub.py "{{input}}" "{{output}}"

validate-cleaned-epub output=cleaned_epub: (clean-calibre-epub calibre_epub output)
    epubcheck "{{output}}"

cover-image:
    magick -size 1600x2560 canvas:'#f5f5f2' -stroke '#111111' -strokewidth 16 -fill none -draw 'rectangle 96,96 1504,2464' -stroke '#111111' -strokewidth 10 -draw 'line 360,520 1240,520' -strokewidth 8 -draw 'line 460,2090 1140,2090' -fill '#111111' -stroke none -font "{{cover_font}}" -gravity north -pointsize 180 -annotate +0+300 'ITSF' -pointsize 128 -annotate +0+790 'Rules of' -annotate +0+950 'Table Soccer' -pointsize 84 -annotate +0+1346 'Standard Matchplay Rules' -pointsize 74 -annotate +0+1586 'Version 2.0' -pointsize 64 -annotate +0+1776 'December 2023' "{{src}}/cover.png"
    magick "{{src}}/cover.png" -alpha off -depth 8 -strip "{{src}}/cover.png"

epub output=epub: cover-image
    test -f "{{src}}/mimetype"
    rm -f "{{output}}"
    cd "{{src}}" && zip -X0 "../{{output}}" mimetype
    cd "{{src}}" && zip -Xr9D "../{{output}}" . -x mimetype

validate output=epub: check-xhtml (epub output)
    epubcheck "{{output}}"

mail-to-kindle output=epub: (epub output)
    : "${KINDLE_EMAIL:?Set KINDLE_EMAIL before running just mail-to-kindle}"
    osascript -e 'set kindleAddress to system attribute "KINDLE_EMAIL"' -e 'set epubPath to POSIX file "{{justfile_directory()}}/{{output}}"' -e 'tell application "Mail"' -e 'set draft to make new outgoing message with properties {subject:"Standard Matchplay Rules 2024", visible:true}' -e 'tell draft' -e 'make new to recipient at end of to recipients with properties {address:kindleAddress}' -e 'tell content' -e 'make new attachment with properties {file name:epubPath} at after the last paragraph' -e 'end tell' -e 'end tell' -e 'activate' -e 'end tell'
