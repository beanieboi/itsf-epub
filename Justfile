set shell := ["zsh", "-cu"]

src := "src"
epub := "Standard Matchplay Rules 2024 - ITSF.epub"

default: epub

check-xhtml:
    xmllint --nonet --noout "{{src}}"/*.xhtml
    python3 scripts/sigil_compat.py --check "{{src}}"

format-xhtml:
    for file in "{{src}}"/*.xhtml; do xmllint --nonet --format "$file" > "$file.tmp" && mv "$file.tmp" "$file"; done
    python3 scripts/sigil_compat.py --fix "{{src}}"

epub output=epub:
    test -f "{{src}}/mimetype"
    rm -f "{{output}}"
    cd "{{src}}" && zip -X0 "../{{output}}" mimetype
    cd "{{src}}" && zip -Xr9D "../{{output}}" . -x mimetype

validate output=epub: check-xhtml (epub output)
    epubcheck "{{output}}"
