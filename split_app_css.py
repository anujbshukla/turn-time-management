from __future__ import annotations

from pathlib import Path
import shutil

PROJECT_ROOT = Path(r"C:\turn-time-management")
APP_CSS = PROJECT_ROOT / "frontend" / "src" / "App.css"
STYLES_DIR = PROJECT_ROOT / "frontend" / "src" / "styles"
BACKUP = PROJECT_ROOT / "frontend" / "src" / "App.pre-split.css"

OUTPUT_FILES = [
    "01-foundation.css",
    "02-operations.css",
    "03-appointments.css",
    "04-intelligence.css",
    "05-workflows.css",
    "06-overrides-responsive.css",
]

def split_top_level_css(text: str) -> list[str]:
    """
    Split CSS only at top-level boundaries.

    This preserves complete selectors, @media blocks, @keyframes blocks,
    comments, and nested declarations. Nothing is reordered.
    """
    chunks: list[str] = []
    start = 0
    depth = 0
    in_string: str | None = None
    in_comment = False
    escaped = False
    i = 0

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_comment:
            if ch == "*" and nxt == "/":
                in_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue

        if ch == "/" and nxt == "*":
            in_comment = True
            i += 2
            continue

        if ch in ("'", '"'):
            in_string = ch
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
            if depth == 0:
                # Include trailing whitespace so formatting stays intact.
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1
                chunks.append(text[start:j])
                start = j
                i = j
                continue
        elif ch == ";" and depth == 0:
            # Preserve top-level statements such as @import if present.
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            chunks.append(text[start:j])
            start = j
            i = j
            continue

        i += 1

    if start < len(text):
        chunks.append(text[start:])

    return [chunk for chunk in chunks if chunk]

def distribute_preserving_order(blocks: list[str], count: int) -> list[str]:
    """
    Divide blocks into approximately equal-size contiguous files.
    Order is never changed.
    """
    total_chars = sum(len(block) for block in blocks)
    target = max(1, total_chars // count)

    groups: list[list[str]] = [[]]
    current_size = 0

    for index, block in enumerate(blocks):
        remaining_blocks = len(blocks) - index
        remaining_groups = count - len(groups)

        if (
            len(groups) < count
            and current_size >= target
            and remaining_blocks > remaining_groups
        ):
            groups.append([])
            current_size = 0

        groups[-1].append(block)
        current_size += len(block)

    while len(groups) < count:
        groups.append([])

    return ["".join(group) for group in groups]

def main() -> None:
    if not APP_CSS.exists():
        raise SystemExit(f"App.css not found: {APP_CSS}")

    original = APP_CSS.read_text(encoding="utf-8-sig")

    if not original.strip():
        raise SystemExit("App.css is empty; stopping.")

    STYLES_DIR.mkdir(parents=True, exist_ok=True)

    # Keep a local backup that Git can show as untracked.
    shutil.copy2(APP_CSS, BACKUP)

    blocks = split_top_level_css(original)

    if len(blocks) < len(OUTPUT_FILES):
        raise SystemExit(
            f"Only found {len(blocks)} top-level CSS blocks; "
            "refusing to split automatically."
        )

    groups = distribute_preserving_order(
        blocks,
        len(OUTPUT_FILES),
    )

    for filename, content in zip(OUTPUT_FILES, groups):
        path = STYLES_DIR / filename
        path.write_text(
            content.rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )

    imports = "\n".join(
        f'@import "./styles/{filename}";'
        for filename in OUTPUT_FILES
    )

    app_css = (
        "/*\n"
        " * App.css is intentionally an import manifest.\n"
        " * The numbered files preserve the original CSS cascade order.\n"
        " * Do not reorder imports without regression testing the UI.\n"
        " */\n\n"
        f"{imports}\n"
    )

    APP_CSS.write_text(
        app_css,
        encoding="utf-8",
        newline="\n",
    )

    rebuilt = "".join(groups)

    # Whitespace at file boundaries can normalize slightly because each
    # generated file ends with a newline. Compare semantic source text
    # after trimming only the outer file whitespace.
    if rebuilt.strip() != original.strip():
        raise SystemExit(
            "Safety check failed: generated CSS does not match original."
        )

    print("App.css split successfully.")
    print(f"Backup: {BACKUP}")
    print("Generated:")
    for filename in OUTPUT_FILES:
        print(f"  {STYLES_DIR / filename}")
    print(f"Manifest: {APP_CSS}")

if __name__ == "__main__":
    main()
