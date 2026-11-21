# recipe-viewer
Conversion of plain text recipes folders into a searchable web page

The source of the recipes is currently Dropbox. Dropbox is read-only: converted
recipes are written to this repository under `recipes/` as plaintext `.txt`
files.

## Convert recipes

Run the converter with the Dropbox recipe folder as its input. It reads `.txt`
files recursively and writes plaintext recipe cards, preserving the source
folder categories and original wording where possible:

```sh
python3 scripts/convert_recipes.py "$HOME/Dropbox/Recipes"
```

The cards use `INGREDIENTS`, `METHOD`, `NOTES`, and `SOURCE` labels without HTML
tags. Text that cannot be confidently structured remains ordinary plaintext.
Choose another output directory with `--output`. The converter refuses to run
if its output overlaps the input tree. Existing generated files are preserved
unless `--overwrite` is passed.

## View recipes

Open `index.html` in a browser. It contains the 156 converted recipe text files
from this repository's `recipes/` folder inside the page itself. The embedded
recipes use the `INGREDIENTS`, `METHOD`, `NOTES`, and `SOURCE` labels, and can be
searched without a server or external libraries.

The initial view is a compact, searchable recipe list. Search can cover all text
or ingredients only. Select one recipe to open it, then return to the list to
choose another. New plaintext recipes can still be added by dropping them onto
the page or using `Alt+Shift+U`; upload controls are hidden from the page.
