set shell := ["zsh", "-cu"]

src := "src"
epub := "Standard Matchplay Rules 2024 - ITSF.epub"
cover_font := "/Library/Fonts/Arial Unicode.ttf"

default: epub

check-xhtml:
    xmllint --nonet --noout "{{src}}"/*.xhtml
    uv run --no-cache python scripts/sigil_compat.py --check "{{src}}"

format-xhtml:
    for file in "{{src}}"/*.xhtml; do xmllint --nonet --format "$file" > "$file.tmp" && mv "$file.tmp" "$file"; done
    uv run --no-cache python scripts/sigil_compat.py --fix "{{src}}"

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
