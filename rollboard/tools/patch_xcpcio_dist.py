#!/usr/bin/env python3
"""Patch XCPCIO board dist HTML for a subpath deployment."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Optional


BASE_PLACEHOLDER = r"try\{let _=__BASE_URL__;window\.BASE_URL=_\}catch\(_\)\{\}"
DATA_HOST_PLACEHOLDER = (
    r"try\{let _=__DATA_HOST__;_=normalizePath\(_\),window\.DATA_HOST=_\}"
    r"catch\(_\)\{window\.DATA_HOST=\"/data/\"\}"
)


def normalize_base_path(value: str) -> str:
    text = value.strip() or "/"
    if not text.startswith("/"):
        text = "/" + text
    if not text.endswith("/"):
        text += "/"
    return text


def normalize_data_host(value: str) -> str:
    text = value.strip() or "/"
    if text == "/":
        return "/"
    if not text.startswith("/") and not text.startswith("http://") and not text.startswith("https://"):
        text = "/" + text
    if not text.endswith("/"):
        text += "/"
    return text


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def replace_once(pattern: str, replacement: str, text: str, label: str) -> str:
    replaced, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"could not find XCPCIO {label} runtime placeholder")
    return replaced


def patch_html(html: str, base_path: str = "/rollboard/", data_host: str = "/") -> str:
    base_path = normalize_base_path(base_path)
    data_host = normalize_data_host(data_host)

    base_runtime = f"window.BASE_URL={js_string(base_path)};"
    data_host_runtime = f"window.DATA_HOST={js_string(data_host)};"

    if base_runtime in html and data_host_runtime in html:
        return html

    if re.search(r"window\.BASE_URL=\"[^\"]*\";", html):
        html = re.sub(r"window\.BASE_URL=\"[^\"]*\";", base_runtime, html, count=1)
    else:
        html = replace_once(BASE_PLACEHOLDER, base_runtime, html, "base URL")

    if re.search(r"window\.DATA_HOST=\"[^\"]*\";", html):
        html = re.sub(r"window\.DATA_HOST=\"[^\"]*\";", data_host_runtime, html, count=1)
    else:
        html = replace_once(DATA_HOST_PLACEHOLDER, data_host_runtime, html, "data host")

    return html


def patch_file(path: Path, base_path: str, data_host: str) -> bool:
    before = path.read_text(encoding="utf-8")
    after = patch_html(before, base_path=base_path, data_host=data_host)
    if after == before:
        return False
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(after, encoding="utf-8")
    tmp_path.replace(path)
    return True


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Patch XCPCIO board dist HTML for SEU rollboard.")
    parser.add_argument("html", nargs="+", type=Path, help="HTML files to patch, usually index.html and 404.html")
    parser.add_argument("--base-path", default="/rollboard/", help="Vue router base path")
    parser.add_argument("--data-host", default="/", help="XCPCIO data host prefix")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    changed = []
    for path in args.html:
        if patch_file(path, args.base_path, args.data_host):
            changed.append(str(path))
    print(json.dumps({"changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
