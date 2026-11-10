"""Reject student document files, including files staged with git add -f."""

import argparse
import subprocess
import sys
from pathlib import PurePath


def main() -> int:
    parser = argparse.ArgumentParser(description="Перевірка відсутності документів у Git")
    parser.add_argument("paths", nargs="*", help="Шляхи файлів для перевірки")
    parser.add_argument("--tracked", action="store_true", help="Перевірити індекс Git")
    args = parser.parse_args()
    paths = args.paths
    if args.tracked:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z"], capture_output=True, check=False
        )
        if result.returncode:
            print("Не вдалося прочитати індекс Git для перевірки документів.", file=sys.stderr)
            return 2
        paths = [
            path.decode("utf-8", errors="surrogateescape")
            for path in result.stdout.split(b"\0")
            if path
        ]

    if any(PurePath(path).suffix.lower() in {".docx", ".doc"} for path in paths):
        # Filenames can also contain personal information; do not print them.
        print(
            "Не додавайте .docx або .doc до Git. Зберігайте роботи локально, "
            "а фікстури генеруйте під час тестів.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
