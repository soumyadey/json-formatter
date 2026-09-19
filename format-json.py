#!/usr/bin/env python3
"""
format-json.py — compact-friendly JSON formatter.

Rules:
  - Objects/arrays where the one-line form fits within --max-line → one line
  - --array-items controls consistency within arrays:
      uniform  (default) all items expand if any item doesn't fit
      smart    each item decides independently
      expand   always expand array items
      inline   always try to inline array items
  - --always-inline / --always-expand accept JSONPath patterns (subset):
      $, .key, [*]  e.g. "$.content.rules", "$.entities[*].ruleIds"

Usage:
  python3 format-json.py file.json                  # format in place
  python3 format-json.py file.json -o out.json      # write to new file
  cat file.json | python3 format-json.py            # stdin → stdout
  python3 format-json.py *.json                     # multiple files in place
"""

import json
import re
import sys
import argparse
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


def parse_jsonpath(pattern):
    """Parse a simple JSONPath into a list of segments: str key or '[*]'."""
    p = pattern.lstrip("$")
    segments = []
    for part in re.split(r'(?=\.|\[)', p):
        part = part.lstrip(".")
        if not part:
            continue
        if part == "[*]":
            segments.append("[*]")
        else:
            segments.append(part)
    return segments


def path_matches(path, pattern_segments):
    if len(path) != len(pattern_segments):
        return False
    for p, s in zip(path, pattern_segments):
        if s == "[*]":
            if not isinstance(p, int):
                return False
        else:
            if p != s:
                return False
    return True


def any_path_matches(path, patterns):
    return any(path_matches(path, p) for p in patterns)


def jdumps(v):
    return json.dumps(v, ensure_ascii=False)


def fits(s, max_line):
    return len(s) <= max_line and "\n" not in s


def format_value(v, indent, level, max_line, array_items, inline_patterns, expand_patterns, path):
    pad = " " * (indent * level)
    inner_pad = " " * (indent * (level + 1))

    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return jdumps(v)
    if isinstance(v, str):
        return jdumps(v)

    def fv(val, key=None, idx=None):
        child_path = path + ([key] if key is not None else [idx] if idx is not None else [])
        return format_value(val, indent, level + 1, max_line, array_items,
                            inline_patterns, expand_patterns, child_path)

    if isinstance(v, list):
        if len(v) == 0:
            return "[]"

        force_inline = any_path_matches(path, inline_patterns)
        force_expand = any_path_matches(path, expand_patterns)

        rendered = [fv(item, idx=i) for i, item in enumerate(v)]

        # Try full array on one line first (unless forced expand)
        if not force_expand:
            one = "[" + ", ".join(rendered) + "]"
            if fits(one, max_line) or force_inline:
                return one

        # uniform: if any item is multi-line, re-render all items forcing expansion
        if array_items == "uniform" and not force_expand:
            if any("\n" in r for r in rendered):
                def fv_expand(val, idx):
                    child_path = path + [idx]
                    return format_value(val, indent, level + 1, 0,
                                       array_items, inline_patterns, expand_patterns, child_path)
                rendered = [fv_expand(item, i) for i, item in enumerate(v)]

        # inline: try one line regardless
        if array_items == "inline" and not force_expand:
            return "[" + ", ".join(rendered) + "]"

        lines = ["["]
        for i, r in enumerate(rendered):
            lines.append(inner_pad + r + ("," if i < len(rendered) - 1 else ""))
        lines.append(pad + "]")
        return "\n".join(lines)

    if isinstance(v, dict):
        if len(v) == 0:
            return "{}"

        force_expand_obj = any_path_matches(path, expand_patterns)

        pairs = []
        for k, val in v.items():
            pairs.append(jdumps(k) + ": " + fv(val, key=k))

        one = "{ " + ", ".join(pairs) + " }"
        if fits(one, max_line) and not force_expand_obj:
            return one

        lines = ["{"]
        for i, pair in enumerate(pairs):
            lines.append(inner_pad + pair + ("," if i < len(pairs) - 1 else ""))
        lines.append(pad + "}")
        return "\n".join(lines)

    return jdumps(v)


def format_json(text, indent=2, max_line=120, array_items="uniform",
                always_inline=None, always_expand=None):
    data = json.loads(text)
    inline_patterns = [parse_jsonpath(p) for p in (always_inline or [])]
    expand_patterns = [parse_jsonpath(p) for p in (always_expand or [])]
    return format_value(data, indent, 0, max_line, array_items,
                        inline_patterns, expand_patterns, path=[]) + "\n"


def load_config_file(path):
    """Load a .toml or .json config file; return dict of options."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Config file not found: {path}")
    text = p.read_text()
    if p.suffix == ".json":
        return json.loads(text)
    if p.suffix == ".toml":
        if tomllib is None:
            raise SystemExit("TOML config requires Python 3.11+ or: pip install tomli")
        return tomllib.loads(text)
    raise SystemExit(f"Unsupported config format: {p.suffix} (use .json or .toml)")


def main():
    parser = argparse.ArgumentParser(description="Compact-friendly JSON formatter")
    parser.add_argument("files", nargs="*", help="JSON files to format (omit for stdin→stdout)")
    parser.add_argument("-o", "--output", help="Output file (single input only)")
    parser.add_argument("-c", "--config", metavar="FILE",
                        help="Config file (.json or .toml); CLI args override it")
    parser.add_argument("--indent", type=int)
    parser.add_argument("--max-line", type=int)
    parser.add_argument("--array-items",
                        choices=["uniform", "smart", "expand", "inline"],
                        help="uniform: all expand if any item does (default); "
                             "smart: each item decides independently; "
                             "expand: always expand; inline: always try one line")
    parser.add_argument("--always-inline", action="append", default=[],
                        metavar="JSONPATH",
                        help="JSONPath pattern to always inline (repeat for multiple)")
    parser.add_argument("--always-expand", action="append", default=[],
                        metavar="JSONPATH",
                        help="JSONPath pattern to always expand (repeat for multiple)")
    args = parser.parse_args()

    # Defaults
    cfg = {"indent": 2, "max_line": 120, "array_items": "uniform",
           "always_inline": [], "always_expand": []}

    # Config file layer (keys use underscore or hyphen)
    if args.config:
        file_cfg = load_config_file(args.config)
        for k, v in file_cfg.items():
            cfg[k.replace("-", "_")] = v

    # CLI layer — explicit CLI args override config file
    if args.indent is not None:
        cfg["indent"] = args.indent
    if args.max_line is not None:
        cfg["max_line"] = args.max_line
    if args.array_items is not None:
        cfg["array_items"] = args.array_items
    if args.always_inline:
        cfg["always_inline"] = args.always_inline
    if args.always_expand:
        cfg["always_expand"] = args.always_expand

    kwargs = dict(indent=cfg["indent"], max_line=cfg["max_line"],
                  array_items=cfg["array_items"],
                  always_inline=cfg["always_inline"],
                  always_expand=cfg["always_expand"])

    if not args.files:
        sys.stdout.write(format_json(sys.stdin.read(), **kwargs))
        return

    for path_str in args.files:
        p = Path(path_str)
        result = format_json(p.read_text(), **kwargs)
        out = Path(args.output) if args.output and len(args.files) == 1 else p
        out.write_text(result)
        if len(args.files) > 1:
            print(f"formatted {p}")


if __name__ == "__main__":
    main()
