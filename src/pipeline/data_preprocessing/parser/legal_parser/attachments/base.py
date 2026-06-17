from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import docx

from .classifier import AttachmentKind, attachment_slug, classify_attachment
from .common import (
    collapse_ws,
    ensure_dir,
    extract_attachment_header,
    get_docx_texts,
    get_docx_block_texts,
    get_mammoth_html_tables,
    normalize_html_table,
    slugify,
    write_json,
    write_jsonl,
)


class AttachmentParserBase:
    parser_name = "base"

    def parse(
        self,
        *,
        docx_path: Union[str, Path],
        output_dir: Union[str, Path],
        package_id: str,
        document_id: Optional[str] = None,
        document_number: Optional[str] = None,
        kind: Optional[AttachmentKind] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def build_metadata(
        self,
        *,
        docx_path: Union[str, Path],
        package_id: str,
        document_id: Optional[str],
        document_number: Optional[str],
        kind: Optional[AttachmentKind],
    ) -> Dict[str, Any]:
        docx_path = Path(docx_path)
        kind = kind or classify_attachment(docx_path)
        if kind.kind == "qcvn":
            texts = get_docx_block_texts(docx_path, limit=100)
        else:
            texts = get_docx_texts(docx_path, limit=80)
        header = extract_attachment_header(texts, docx_path)

        att_slug = attachment_slug(docx_path)
        attachment_id = f"{document_id or slugify(package_id)}.{slugify(att_slug)}"

        return {
            "package_id": package_id,
            "document_id": document_id,
            "document_number": document_number,
            "attachment_id": attachment_id,
            "attachment_slug": att_slug,
            "attachment_kind": kind.kind,
            "classifier_confidence": kind.confidence,
            "classifier_reason": kind.reason,
            "label": header.get("label"),
            "title": header.get("title"),
            "issued_with": header.get("issued_with"),
            "source_file": str(docx_path),
            "parser": self.parser_name,
        }

    def make_unit(
        self,
        *,
        metadata: Dict[str, Any],
        unit_type: str,
        local_id: str,
        path_parts: List[str],
        content: str,
        label: Optional[str] = None,
        parent_id: Optional[str] = None,
        order: int = 0,
        structured_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        unit_id = f"{metadata['attachment_id']}.{local_id}"
        path_text = " > ".join([p for p in path_parts if p])
        row = {
            "unit_id": unit_id,
            "id": unit_id,
            "unit_type": unit_type,
            "type": unit_type,
            "parent_id": parent_id,
            "order": order,
            "path_text": path_text,
            "content": content,
            "structured_fields": structured_fields or {},
        }
        if label:
            row["label"] = label
        return row

    def extract_tables(self, metadata: Dict[str, Any], docx_path: Union[str, Path]) -> List[Dict[str, Any]]:
        tables = []
        html_tables = get_mammoth_html_tables(docx_path)
        for idx, html in enumerate(html_tables, start=1):
            rows = normalize_html_table(html)
            table_id = f"{metadata['attachment_id']}.table_{idx}"
            tables.append({
                "table_id": table_id,
                "package_id": metadata.get("package_id"),
                "document_id": metadata.get("document_id"),
                "attachment_id": metadata.get("attachment_id"),
                "attachment_type": metadata.get("attachment_kind"),
                "order": idx,
                "normalized_rows": rows,
                "row_count": len(rows),
                "col_count": max([len(r) for r in rows], default=0),
                "source_file": metadata.get("source_file"),
            })
        return tables

    def write_outputs(
        self,
        *,
        output_dir: Union[str, Path],
        metadata: Dict[str, Any],
        units: List[Dict[str, Any]],
        tables: Optional[List[Dict[str, Any]]] = None,
        table_rows: Optional[List[Dict[str, Any]]] = None,
        form_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        out = ensure_dir(output_dir)
        tables = tables or []
        table_rows = table_rows or []
        form_fields = form_fields or []
        tree_path = out / "tree.json"
        units_path = out / "units.jsonl"
        tree = {
            "metadata": metadata,
            "body": self.units_to_tree(units, tables=tables),
        }
        flattened_units = list(self.flatten_units(tree))

        write_json(out / "attachment.json", metadata)
        write_json(tree_path, tree)
        write_jsonl(units_path, flattened_units)

        return {
            "attachment": metadata,
            "node_count": len(flattened_units),
            "unit_count": len(flattened_units),
            "table_count": len(tables),
            "table_row_count": len(table_rows),
            "form_field_count": len(form_fields),
            "tree_path": str(tree_path),
            "units_path": str(units_path),
            "tree_size_bytes": tree_path.stat().st_size if tree_path.exists() else 0,
            "units_size_bytes": units_path.stat().st_size if units_path.exists() else 0,
            "output_dir": str(out),
        }

    @staticmethod
    def units_to_tree(units: List[Dict[str, Any]], *, tables: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        table_by_id = {table.get("table_id"): table for table in tables or []}
        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        roots: List[Dict[str, Any]] = []

        for unit in sorted(units, key=lambda item: item.get("order", 0)):
            node_id = unit.get("id") or unit.get("unit_id")
            if not node_id:
                continue
            unit_type = unit.get("type") or unit.get("unit_type")
            node = {
                "id": node_id,
                "type": unit_type,
                "label": unit.get("label") or "",
                "content": unit.get("content") or "",
                "order": unit.get("order", 0),
                "path_text": unit.get("path_text") or "",
                "children": [],
            }
            structured_fields = dict(unit.get("structured_fields") or {})
            if unit_type == "table_row":
                structured_fields = {}
            table_id = structured_fields.get("table_id")
            if table_id and table_id in table_by_id:
                table = table_by_id[table_id]
                node["table"] = {
                    "table_id": table.get("table_id"),
                    "order": table.get("order"),
                    "row_count": table.get("row_count"),
                    "col_count": table.get("col_count"),
                }
            if structured_fields:
                node["structured_fields"] = structured_fields
            nodes_by_id[node_id] = node

        for unit in sorted(units, key=lambda item: item.get("order", 0)):
            node_id = unit.get("id") or unit.get("unit_id")
            node = nodes_by_id.get(node_id)
            if not node:
                continue
            parent_id = unit.get("parent_id")
            parent = nodes_by_id.get(parent_id)
            if parent:
                parent.setdefault("children", []).append(node)
            else:
                roots.append(node)

        return roots

    @staticmethod
    def flatten_units(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        metadata = tree.get("metadata", {})
        rows: List[Dict[str, Any]] = []

        def walk(node: Dict[str, Any]) -> None:
            content = collapse_ws(node.get("content") or "")
            if content:
                rows.append({
                    "id": node.get("id"),
                    "document_id": metadata.get("document_id"),
                    "document_number": metadata.get("document_number"),
                    "issue_date": metadata.get("issue_date"),
                    "type": node.get("type"),
                    "path_text": node.get("path_text"),
                    "content": content,
                })
            for child in node.get("children", []) or []:
                walk(child)

        for top in tree.get("body", []) or []:
            walk(top)
        return rows

    def table_rows_to_units(
        self,
        *,
        metadata: Dict[str, Any],
        tables: List[Dict[str, Any]],
        path_prefix: List[str],
        start_order: int = 100000,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        units = []
        table_rows = []
        order = start_order

        for table in tables:
            rows = table.get("normalized_rows") or []
            if not rows:
                continue

            for ridx, row in enumerate(rows, start=1):
                if not any(c.strip() for c in row):
                    continue
                content = " | ".join([c for c in row if c.strip()])
                if len(content) < 3:
                    continue

                local_id = f"{table['table_id'].split('.')[-1]}.row_{ridx}"
                fields = {"table_id": table["table_id"], "row_index": ridx}

                unit = self.make_unit(
                    metadata=metadata,
                    unit_type="table_row",
                    local_id=local_id,
                    path_parts=path_prefix + [f"Bảng {table.get('order')}", f"Dòng {ridx}"],
                    content=content,
                    parent_id=table["table_id"],
                    order=order,
                    structured_fields=fields,
                )
                order += 1
                units.append(unit)
                table_rows.append({
                    "row_id": unit["unit_id"],
                    "table_id": table["table_id"],
                    "row_index": ridx,
                    "cells": row,
                    "content": content,
                })

        return units, table_rows
