#!/usr/bin/env python3
"""Convert recipe text files into a consistent, readable plaintext format.

The input tree is read only. Output is written beneath --output, which defaults
to this repository's recipes/ directory.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DETAIL = re.compile(
    r"^(?:(\d+(?:[.,]\d+)?)\s*)?(serves?|servings?|prep(?:aration)?\s*time|"
    r"cook(?:ing)?\s*time|total\s*time|takes?|yield|calories?|kcal)\s*:?\s*(.*)$",
    re.IGNORECASE,
)
SECTION = {
    "ingredients": "INGREDIENTS",
    "ingredient": "INGREDIENTS",
    "method": "METHOD",
    "directions": "METHOD",
    "instructions": "METHOD",
    "preparation": "METHOD",
    "notes": "NOTES",
    "comments": "NOTES",
    "source": "SOURCE",
}
STEP = re.compile(r"^(?:(?:step\s*)?\d+[.)]|[-*•])\s+", re.IGNORECASE)
SENTENCE_START = re.compile(
    r"^(?:add|bake|beat|boil|bring|chop|combine|cook|cover|drain|fold|fry|heat|"
    r"let|mix|place|preheat|pour|remove|roast|rub|serve|set|simmer|sprinkle|stir|tip:|whisk)\b",
    re.IGNORECASE,
)


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def detail_line(line: str) -> str | None:
    match = DETAIL.match(line.strip())
    if not match:
        return None
    amount, label, value = match.groups()
    canonical = re.sub(r"\s+", " ", label.strip()).title()
    aliases = {
        "Serving": "Serves", "Servings": "Serves", "Preparation Time": "Prep time",
        "Cooking Time": "Cook time", "Total Time": "Total time", "Kcal": "Calories",
    }
    canonical = aliases.get(canonical, canonical)
    if amount:
        value = f"{amount} {value}".strip()
    value = re.sub(r"\s*/\s*serving\b", " per serving", value.strip(), flags=re.IGNORECASE)
    value = value.rstrip(":").strip()
    if canonical == "Kcal":
        canonical = "Calories"
    return f"{canonical}: {value}" if value else line.strip()


def title_and_body(text: str, fallback: str) -> tuple[str, list[str]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return fallback, []
    title = lines[first].strip()
    return title, lines[:first] + lines[first + 1:]


def section_heading(line: str) -> str | None:
    return SECTION.get(line.strip().rstrip(":").casefold())


def is_step(line: str) -> bool:
    return bool(re.match(r"^(?:(?:step\s*)?\d+[.)])\s+", line.strip(), re.IGNORECASE))


def looks_like_method(line: str) -> bool:
    clean = line.strip()
    return bool(SENTENCE_START.match(clean) or (len(clean) >= 90 and re.search(r"[.!?]", clean)))


def normalize_method(lines: list[str]) -> list[str]:
    numbered_steps = any(is_step(line) for line in lines)
    if not numbered_steps:
        paragraphs: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            clean = line.strip()
            if clean:
                current.append(clean)
            elif current:
                paragraphs.append(current)
                current = []
        if current:
            paragraphs.append(current)
        return [f"{index}. {' '.join(paragraph)}" for index, paragraph in enumerate(paragraphs, 1)]

    result: list[str] = []
    preamble: list[str] = []
    step_lines: list[str] = []

    def flush_preamble() -> None:
        if preamble:
            result.append(" ".join(preamble))
            preamble.clear()

    def flush_step() -> None:
        if step_lines:
            result.append(" ".join(step_lines))
            step_lines.clear()

    for line in lines:
        clean = line.strip()
        if is_step(clean):
            flush_preamble()
            flush_step()
            step_lines.append(clean)
        elif clean:
            (step_lines if step_lines else preamble).append(clean)
    flush_preamble()
    flush_step()
    return result


def normalize_ingredients(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        clean = line.strip()
        if not clean:
            if result and result[-1] != "":
                result.append("")
        elif (clean.endswith(":") or re.match(r"^(?:alternative|for|garnish|to serve)\b", clean, re.I)) and not clean.startswith(("- ", "* ", "• ")):
            if not clean.endswith(":"):
                clean += ":"
            result.append(clean)
        elif clean.startswith(("- ", "* ", "• ")):
            result.append(f"- {clean[2:].strip()}")
        else:
            result.append(f"- {clean}")
    return result


def convert(path: Path) -> str:
    original = read_text(path).replace("\r\n", "\n").replace("\r", "\n")
    title, body = title_and_body(original, path.stem)

    details: list[str] = []
    groups: list[tuple[str, list[str]]] = []
    current_section = "INGREDIENTS"
    current_lines: list[str] = []
    has_recipe_shape = False
    method_started = False

    def flush() -> None:
        nonlocal current_lines
        if any(line.strip() for line in current_lines):
            groups.append((current_section, current_lines))
        current_lines = []

    for line in body:
        heading = section_heading(line)
        detail = detail_line(line)
        if heading:
            flush()
            current_section = heading
            has_recipe_shape = has_recipe_shape or heading in {"INGREDIENTS", "METHOD"}
            method_started = method_started or heading == "METHOD"
            continue
        if detail:
            details.append(detail)
            has_recipe_shape = True
            continue
        stripped = line.strip()
        if current_section == "INGREDIENTS" and (is_step(stripped) or (not method_started and looks_like_method(stripped))):
            flush()
            current_section = "METHOD"
            method_started = True
        elif re.match(r"^(?:source|comments?|notes?|tip)\s*:", stripped, re.IGNORECASE):
            flush()
            is_source = stripped.lower().startswith("source:")
            current_section = "SOURCE" if is_source else "NOTES"
            if not stripped.lower().startswith("tip:"):
                stripped = re.sub(r"^(?:source|comments?|notes?)\s*:\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"<(https?://[^>]+)>", r"\1", stripped, flags=re.IGNORECASE)
        line = stripped
        if stripped and looks_like_method(stripped) and current_section == "METHOD":
            has_recipe_shape = True
        current_lines.append(line)
    flush()

    ingredient_lines = [line.strip() for name, group in groups if name == "INGREDIENTS"
                        for line in group if line.strip() and not line.strip().endswith(":")]
    has_recipe_shape = has_recipe_shape or (
        path.stem.casefold() != "pan weights"
        and len(ingredient_lines) >= 2
        and not any(re.match(r"^https?://", line, re.IGNORECASE) for line in ingredient_lines)
    )

    # Text-only items such as links and household notes stay ordinary plaintext.
    if not has_recipe_shape:
        return original.rstrip("\n") + "\n"

    rendered = [title]
    rendered.extend(["", *details] if details else [])
    for name in ("INGREDIENTS", "METHOD", "NOTES", "SOURCE"):
        matching = [lines for section, lines in groups if section == name]
        if not matching:
            continue
        content: list[str] = []
        for group in matching:
            content.extend(group)
            if content and content[-1] != "":
                content.append("")
        while content and not content[-1]:
            content.pop()
        if name == "INGREDIENTS":
            content = normalize_ingredients(content)
        elif name == "METHOD":
            content = normalize_method(content)
        rendered.extend(["", name, *content])

    return "\n".join(rendered).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Recipe folder to read (for example, ~/Dropbox/Recipes)")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "recipes",
                        help="Repository directory for generated plaintext recipes (default: ./recipes)")
    parser.add_argument("--extensions", nargs="+", default=[".txt"],
                        help="Input file extensions to convert (default: .txt)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace generated files already present in the output tree")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_dir():
        parser.error(f"source directory does not exist: {source}")
    if source == output or source in output.parents or output in source.parents:
        parser.error("source and output trees must be separate; output cannot overlap the input tree")

    extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in args.extensions}
    inputs = sorted((path for path in source.rglob("*")
                     if path.is_file() and path.suffix.lower() in extensions),
                    key=lambda path: path.relative_to(source).as_posix().casefold())
    if not inputs:
        print(f"No input files with extensions {', '.join(sorted(extensions))} found in {source}")
        return 0

    destinations = [(path, output / path.relative_to(source).with_suffix(".txt")) for path in inputs]
    seen: set[Path] = set()
    for _, destination in destinations:
        if destination in seen:
            raise SystemExit(f"Multiple source files map to the same output: {destination}")
        seen.add(destination)
        if destination.exists() and not args.overwrite:
            raise SystemExit(f"Refusing to overwrite existing output: {destination} (use --overwrite)")

    for path, destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(convert(path))
    print(f"Converted {len(inputs)} text files from {source} into plaintext recipes in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
