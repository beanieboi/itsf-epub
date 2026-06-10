set shell := ["zsh", "-cu"]

src := "src"
epub := "Standard Matchplay Rules 2024 - ITSF.epub"

default: epub

epub output=epub:
    test -f "{{src}}/mimetype"
    rm -f "{{output}}"
    cd "{{src}}" && zip -X0 "../{{output}}" mimetype
    cd "{{src}}" && zip -Xr9D "../{{output}}" . -x mimetype

validate output=epub: (epub output)
    epubcheck "{{output}}"
