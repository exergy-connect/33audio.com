"""python -m catalog parse|ebay|stock|build|refresh"""

import sys

from catalog.build import main as build_main
from catalog.ebay import main as ebay_main
from catalog.parse import main as parse_main
from catalog.stock import main as stock_main


def refresh() -> int:
    if parse_main([]) not in (0, None):
        return 1
    if ebay_main([]) not in (0, None):
        return 1
    if stock_main([]) not in (0, None):
        return 1
    return build_main([]) or 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "build"
    rest = argv[1:]
    if cmd == "parse":
        return parse_main(rest) or 0
    if cmd == "ebay":
        return ebay_main(rest) or 0
    if cmd == "stock":
        return stock_main(rest) or 0
    if cmd == "build":
        return build_main(rest) or 0
    if cmd == "refresh":
        return refresh()
    print("Usage: python -m catalog parse|ebay|stock|build|refresh", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
