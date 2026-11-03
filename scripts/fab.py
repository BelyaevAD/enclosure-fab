#!/usr/bin/env python3
"""Enclosure wrapper CLI. Use the zone venv: py -3.12, not bare `py`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ZONE = Path(__file__).resolve().parents[1]
if str(ZONE) not in sys.path:
    sys.path.insert(0, str(ZONE))

from fabkit.runtime import require_cpython_312  # noqa: E402

require_cpython_312()

from fabkit.confirm import confirm_field  # noqa: E402
from fabkit.freshness import freshness_report  # noqa: E402
from fabkit.generate import generate  # noqa: E402
from fabkit.last_gate import read as read_gate, record  # noqa: E402
from fabkit.primitives import list_primitives  # noqa: E402
from fabkit.protocol import list_boards, list_templates, protocol, resolve_spec_path  # noqa: E402
from fabkit.validate import GateError, load_spec, validate_spec  # noqa: E402


def _print(data: object) -> int:
    print(json.dumps(data, indent=2, ensure_ascii=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fab")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-templates")
    sub.add_parser("list-boards")
    sub.add_parser("list-primitives")
    p_proto = sub.add_parser("protocol")
    p_proto.add_argument("--family")

    p_val = sub.add_parser("validate")
    p_val.add_argument("spec", type=Path)

    p_prev = sub.add_parser("preview")
    p_prev.add_argument("spec", type=Path)
    p_prev.add_argument("-o", "--out", type=Path)

    p_print = sub.add_parser("print")
    p_print.add_argument("spec", type=Path)
    p_print.add_argument("-o", "--out", type=Path)

    p_conf = sub.add_parser("confirm")
    p_conf.add_argument("spec", type=Path)
    p_conf.add_argument("field")
    p_conf.add_argument("--i-measured", action="store_true")

    sub.add_parser("explain-last-gate")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "list-templates":
            return _print({"templates": list_templates()})
        if args.cmd == "list-boards":
            return _print({"boards": list_boards()})
        if args.cmd == "list-primitives":
            return _print(list_primitives())
        if args.cmd == "protocol":
            return _print(protocol(args.family))
        if args.cmd == "validate":
            spec_path = resolve_spec_path(args.spec)
            gate = validate_spec(load_spec(spec_path), "validate")
            record("validate", str(spec_path), gate)
            return _print(
                {
                    "ok": gate.ok,
                    "errors": gate.errors,
                    "warnings": gate.warnings,
                    "unconfirmed": gate.unconfirmed,
                }
            )
        if args.cmd == "preview":
            result = generate(resolve_spec_path(args.spec), "preview", args.out)
            if result.get("banner"):
                print(result["banner"])
            print(freshness_report(result))
            return _print(result)
        if args.cmd == "print":
            return _print(generate(resolve_spec_path(args.spec), "print", args.out))
        if args.cmd == "confirm":
            return _print(confirm_field(resolve_spec_path(args.spec), args.field, i_measured=args.i_measured))
        if args.cmd == "explain-last-gate":
            return _print(read_gate())
    except (GateError, FileNotFoundError, KeyError, OSError, PermissionError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
