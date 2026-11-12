"""Activate maintained project design skill/config without replacing user files."""

import argparse
import os
from pathlib import Path


def activate(root: Path) -> list[str]:
    root = root.resolve()
    pairs = (
        (
            root / "tools/ai/skills/oformleno-figma-design",
            root / ".agents/skills/oformleno-figma-design",
        ),
        (root / "tools/ai/figma-mcp.toml", root / ".codex/config.toml"),
    )
    pending = []
    for source, destination in pairs:
        if not source.exists():
            raise ValueError(f"Missing maintained source: {source.relative_to(root)}")
        if destination.is_symlink() and destination.resolve() == source:
            continue
        if destination.exists() or destination.is_symlink():
            raise ValueError(
                f"Preserving existing {destination.relative_to(root)}; "
                "inspect it and merge the maintained setup manually."
            )
        pending.append((source, destination))
    # Inspect every destination before creating any link.
    for source, destination in pending:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.path.relpath(source, destination.parent))
    return [str(destination.relative_to(root)) for _, destination in pairs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        paths = activate(args.root)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Design setup: {error}\n")
    for path in paths:
        print(f"Ready: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
