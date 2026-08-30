#!/usr/bin/env python3
"""Attach shape-level file hyperlinks to module buttons in a generated PPTX."""

from __future__ import annotations

import html
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
HYPERLINK_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
R_NS_DECL = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def discover_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for folder in (ROOT / "dashagent", ROOT / "scripts"):
        if not folder.exists():
            continue
        for file in sorted(folder.glob("*.py")):
            modules.setdefault(file.name, file)
    return modules


MODULES = discover_modules()
MODULE_RE = re.compile("|".join(re.escape(name) for name in sorted(MODULES, key=len, reverse=True))) if MODULES else re.compile(r"a^")
A_NS_DECL = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
SHAPE_RE = re.compile(r"<p:sp\b.*?</p:sp>", re.DOTALL)
TEXT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.DOTALL)


def file_uri(path: Path) -> str:
    return "file://" + quote(str(path.resolve()))


def next_rel_id(rels_xml: str, counter: int) -> str:
    rel_id = f"rIdModuleLink{counter}"
    while f'Id="{rel_id}"' in rels_xml:
        counter += 1
        rel_id = f"rIdModuleLink{counter}"
    return rel_id


def ensure_rels(rels_xml: str | None) -> str:
    if rels_xml:
        return rels_xml
    return f'<?xml version="1.0" encoding="utf-8"?><Relationships xmlns="{REL_NS}"></Relationships>'


def add_relationship(rels_xml: str, rel_id: str, target: str) -> str:
    relationship = (
        f'<Relationship Type="{HYPERLINK_REL}" Target="{html.escape(target, quote=True)}" '
        f'Id="{rel_id}" TargetMode="External" />'
    )
    return rels_xml.replace("</Relationships>", f"{relationship}</Relationships>")


def shape_text(shape_xml: str) -> str:
    return " ".join(html.unescape(match.group(1)) for match in TEXT_RE.finditer(shape_xml))


def module_from_button(shape_xml: str) -> str | None:
    text = shape_text(shape_xml)
    if "Open " not in text:
        return None
    for module in sorted(MODULES, key=len, reverse=True):
        if re.search(rf"\bOpen\s+{re.escape(module)}\b", text):
            return module
    return None


def add_shape_hyperlink(shape_xml: str, rel_id: str, tooltip: str) -> str:
    c_nv_match = re.search(r"<p:cNvPr\b[^>]*>.*?</p:cNvPr>", shape_xml, re.DOTALL)
    if not c_nv_match:
        c_nv_match = re.search(r"<p:cNvPr\b[^>]*/>", shape_xml, re.DOTALL)
    if not c_nv_match:
        return shape_xml
    c_nv_xml = c_nv_match.group(0)
    if "<a:hlinkClick" in c_nv_xml:
        return shape_xml
    hlink = (
        f'<a:hlinkClick {A_NS_DECL} r:id="{rel_id}" '
        f'tooltip="{html.escape(tooltip, quote=True)}"/>'
    )
    if c_nv_xml.endswith("/>"):
        linked_c_nv = c_nv_xml[:-2] + f">{hlink}</p:cNvPr>"
    else:
        linked_c_nv = re.sub(r"(<p:cNvPr\b[^>]*>)", rf"\1{hlink}", c_nv_xml, count=1)
    return shape_xml[: c_nv_match.start()] + linked_c_nv + shape_xml[c_nv_match.end() :]


def process_slide(slide_xml: str, rels_xml: str | None) -> tuple[str, str, int]:
    rels_xml = ensure_rels(rels_xml)
    link_count = 0
    rel_counter = len(re.findall(r'\bId="[^"]+"', rels_xml)) + 1

    if "xmlns:r=" not in slide_xml:
        slide_xml = slide_xml.replace("<p:sld ", f"<p:sld {R_NS_DECL} ", 1)

    def replace_shape(match: re.Match[str]) -> str:
        nonlocal rels_xml, rel_counter, link_count
        shape_xml = match.group(0)
        module = module_from_button(shape_xml)
        if not module:
            return shape_xml
        rel_id = next_rel_id(rels_xml, rel_counter)
        rel_counter += 1
        target = file_uri(MODULES[module])
        rels_xml = add_relationship(rels_xml, rel_id, target)
        link_count += 1
        return add_shape_hyperlink(shape_xml, rel_id, f"Open {MODULES[module].resolve()}")

    return SHAPE_RE.sub(replace_shape, slide_xml), rels_xml, link_count


def rels_path_for(slide_name: str) -> str:
    filename = Path(slide_name).name
    return f"ppt/slides/_rels/{filename}.rels"


def rewrite_pptx(pptx: Path) -> int:
    total_links = 0
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    with zipfile.ZipFile(pptx, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        names = zin.namelist()
        replacements: dict[str, bytes] = {}
        for name in names:
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            slide_xml = zin.read(name).decode("utf-8")
            rel_name = rels_path_for(name)
            rels_xml = zin.read(rel_name).decode("utf-8-sig") if rel_name in names else None
            new_slide, new_rels, count = process_slide(slide_xml, rels_xml)
            if count:
                replacements[name] = new_slide.encode("utf-8")
                replacements[rel_name] = new_rels.encode("utf-8")
                total_links += count

        for name in names:
            if name in replacements:
                zout.writestr(name, replacements[name])
            else:
                zout.writestr(name, zin.read(name))
        for name, data in replacements.items():
            if name not in names:
                zout.writestr(name, data)

    shutil.move(str(tmp_path), pptx)
    return total_links


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: add_ppt_module_hyperlinks.py <deck.pptx>")
    pptx = Path(sys.argv[1]).resolve()
    if not pptx.exists():
        raise SystemExit(f"PPTX not found: {pptx}")
    count = rewrite_pptx(pptx)
    print(f"module_hyperlinks={count}")


if __name__ == "__main__":
    main()
