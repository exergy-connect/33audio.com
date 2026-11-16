"""python -m academy build [--check] [--out DIR] [--real-dir DIR]"""

import sys

from academy.build import main


def run(argv: list[str]) -> int:
    if argv and argv[0] == "build":
        argv = argv[1:]
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
