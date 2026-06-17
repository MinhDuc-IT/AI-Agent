from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import docx

from .base import AttachmentParserBase
from .classifier import AttachmentKind, classify_attachment
from .common import collapse_ws, iter_docx_blocks, normalize_qcvn_code, slugify, strip_vietnamese_accents


class AppendixParser(AttachmentParserBase):
    parser_name = "appendix_parser"

    # Structured appendix headings.
    pat_part = re.compile(r"^(?:PHẦN|PHAN)\s+([0-9IVXLCDM]+)\s*[:.\-–]?\s*(.*)$", re.I | re.U)
    pat_chapter = re.compile(r"^(?:CHƯƠNG|CHUONG)\s+([0-9IVXLCDM]+)\s*[:.\-–]?\s*(.*)$", re.I | re.U)
    pat_article = re.compile(r"^Điều\s+(\d+[A-Za-zĐđ]?)\.\s*(.*)$", re.I | re.U)
    pat_internal_appendix = re.compile(r"^(?:Phụ lục|Phu luc)\s+([A-ZĐ0-9]+)\s*[:.\-–]?\s*(.*)$", re.I | re.U)
    pat_alpha = re.compile(r"^([A-ZĐ])\.\s+(.+)")
    pat_roman = re.compile(r"^([IVXLCDM]+)\.\s+(.+)", re.I)
    pat_decimal = re.compile(r"^(\d+(?:\.\d+)*)\.\s+(.+)")
    pat_point = re.compile(r"^([a-zđ])\)\s*(.+)", re.I)
    pat_bullet = re.compile(r"^[-–•]\s+(.+)")

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
        docx_path = Path(docx_path)
        kind = kind or classify_attachment(docx_path)
        metadata = self.build_metadata(
            docx_path=docx_path,
            package_id=package_id,
            document_id=document_id,
            document_number=document_number,
            kind=kind,
        )

        doc = docx.Document(str(docx_path))
        tables, table_by_source_order = self._prepare_tables_for_parse(
            metadata,
            self.extract_tables(metadata, docx_path),
        )

        units: List[Dict[str, Any]] = []
        order = 0
        stack: Dict[int, Dict[str, Any]] = {}
        path_stack: Dict[int, str] = {}
        decimal_units_by_no: Dict[str, Dict[str, Any]] = {}
        prefix = [metadata.get("label") or "Phụ lục"]
        if metadata.get("title") and not self._is_structural_heading(metadata["title"]):
            prefix.append(metadata["title"])
        in_qcvn_toc = False
        qcvn_toc_entry_seen = False
        qcvn_english_title_tail_lines = 0

        # Add top summary unit.
        units.append(self.make_unit(
            metadata=metadata,
            unit_type="attachment_summary",
            local_id="summary",
            path_parts=prefix,
            content=f"{metadata.get('label') or ''}. {metadata.get('title') or ''}".strip(),
            order=order,
        ))
        order += 1

        table_counter = 0
        for block in iter_docx_blocks(doc):
            if isinstance(block, docx.text.paragraph.Paragraph):
                text = collapse_ws(block.text)
                if not text:
                    continue

                if kind.kind == "qcvn":
                    if qcvn_english_title_tail_lines:
                        if self._is_qcvn_english_title_tail(text):
                            qcvn_english_title_tail_lines -= 1
                            continue
                        qcvn_english_title_tail_lines = 0

                    if self._is_qcvn_toc_heading(text):
                        in_qcvn_toc = True
                        qcvn_toc_entry_seen = False
                        continue
                    if in_qcvn_toc:
                        if self._is_qcvn_toc_end(text, metadata, toc_entry_seen=qcvn_toc_entry_seen):
                            in_qcvn_toc = False
                        else:
                            if self._looks_like_qcvn_toc_entry(text):
                                qcvn_toc_entry_seen = True
                            continue

                # Skip boilerplate header already represented in metadata.
                if self._is_header_boilerplate(text, metadata):
                    if kind.kind == "qcvn" and self._is_qcvn_english_title_head(text):
                        qcvn_english_title_tail_lines = 2
                    continue

                level, no, title, unit_type = self._classify_line(text, qcvn_mode=(kind.kind == "qcvn"))
                if level is None:
                    if self._attach_heading_title_if_pending(text, stack, path_stack, prefix):
                        continue

                    # Continuation text: attach as raw paragraph under current deepest path.
                    parent = self._deepest_parent(stack)
                    local_id = f"p_{order}"
                    path_parts = prefix + self._current_path_parts(path_stack) + [f"Đoạn {order}"]
                    units.append(self.make_unit(
                        metadata=metadata,
                        unit_type="appendix_paragraph",
                        local_id=local_id,
                        path_parts=path_parts,
                        content=text,
                        parent_id=parent.get("unit_id") if parent else None,
                        order=order,
                    ))
                    order += 1
                    continue

                if unit_type != "appendix_item_decimal":
                    decimal_units_by_no.clear()

                self._reset_stack_for_new_unit(stack, path_stack, level, unit_type, no)

                parent = None
                if unit_type == "appendix_item_decimal":
                    parent = self._parent_for_decimal_no(decimal_units_by_no, no)
                parent = parent or self._parent_for_level(stack, level)
                slug = slugify(no)
                local_id = f"{unit_type}_{slug}"
                if any(u["unit_id"].endswith("." + local_id) for u in units):
                    local_id = f"{local_id}_{order}"

                path_label = self._label_for(unit_type, no, title)
                if unit_type == "appendix_item_decimal" and parent and parent.get("path_text"):
                    path_parts = [parent["path_text"], path_label]
                else:
                    path_parts = prefix + self._path_parts_before(path_stack, level) + [path_label]
                unit = self.make_unit(
                    metadata=metadata,
                    unit_type=unit_type,
                    local_id=local_id,
                    path_parts=path_parts,
                    content=title,
                    label=path_label,
                    parent_id=parent.get("unit_id") if parent else None,
                    order=order,
                    structured_fields={"no": no},
                )
                units.append(unit)
                stack[level] = unit
                path_stack[level] = path_label
                if unit_type == "appendix_item_decimal":
                    decimal_units_by_no[no] = unit
                order += 1

            elif isinstance(block, docx.table.Table):
                table_counter += 1
                # Table content already extracted globally; create a table placeholder unit
                table = table_by_source_order.get(table_counter)
                if table:
                    units.append(self._make_table_unit(
                        metadata=metadata,
                        table=table,
                        table_counter=table.get("order") or table_counter,
                        prefix=prefix,
                        path_parts=prefix + self._current_path_parts(path_stack) + [f"Bảng {table.get('order') or table_counter}"],
                        parent_id=(self._deepest_parent(stack) or {}).get("unit_id"),
                        order=order,
                    ))
                    order += 1

        emitted_source_orders = set(range(1, table_counter + 1))
        for table in tables:
            if table.get("source_order") in emitted_source_orders:
                continue
            units.append(self._make_table_unit(
                metadata=metadata,
                table=table,
                table_counter=table.get("order") or table.get("source_order") or 0,
                prefix=prefix,
                path_parts=prefix + [f"Bảng {table.get('order')}"],
                parent_id=None,
                order=order,
                generated_placeholder=True,
            ))
            order += 1

        row_units, table_rows = self.table_rows_to_units(
            metadata=metadata,
            tables=tables,
            path_prefix=prefix,
            start_order=order,
        )
        units.extend(row_units)

        return self.write_outputs(
            output_dir=output_dir,
            metadata=metadata,
            units=units,
            tables=tables,
            table_rows=table_rows,
            form_fields=[],
        )

    def _make_table_unit(
        self,
        *,
        metadata: Dict[str, Any],
        table: Dict[str, Any],
        table_counter: int,
        prefix: List[str],
        path_parts: List[str],
        parent_id: Optional[str],
        order: int,
        generated_placeholder: bool = False,
    ) -> Dict[str, Any]:
        preview_rows = table.get("normalized_rows") or []
        preview = "\n".join([" | ".join([c for c in r if c.strip()]) for r in preview_rows[:6]])
        fields = {"table_id": table.get("table_id")}
        if generated_placeholder:
            fields["generated_placeholder"] = True
        return self.make_unit(
            metadata=metadata,
            unit_type="appendix_table",
            local_id=f"table_{table_counter}",
            path_parts=path_parts or prefix + [f"Bảng {table_counter}"],
            content=preview,
            label=f"Bảng {table_counter}",
            parent_id=parent_id,
            order=order,
            structured_fields=fields,
        )

    def _prepare_tables_for_parse(
        self,
        metadata: Dict[str, Any],
        raw_tables: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
        tables: List[Dict[str, Any]] = []
        table_by_source_order: Dict[int, Dict[str, Any]] = {}

        for fallback_order, raw_table in enumerate(raw_tables, start=1):
            source_order = int(raw_table.get("order") or fallback_order)
            if self._is_qcvn_cover_or_toc_table(raw_table, metadata):
                continue

            table = dict(raw_table)
            table["source_order"] = source_order
            table["order"] = len(tables) + 1
            table["table_id"] = f"{metadata['attachment_id']}.table_{table['order']}"
            tables.append(table)
            table_by_source_order[source_order] = table

        return tables, table_by_source_order

    def _is_qcvn_cover_or_toc_table(self, table: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
        if metadata.get("attachment_kind") != "qcvn":
            return False

        source_order = int(table.get("order") or 0)
        if source_order > 3:
            return False

        rows = table.get("normalized_rows") or []
        text = collapse_ws(" ".join(cell for row in rows for cell in row if cell))
        if not text:
            return False

        ascii_text = strip_vietnamese_accents(text, keep_dd=False).lower()
        compact_layout = table.get("row_count", 0) <= 4 and table.get("col_count", 0) <= 4
        has_qcvn_label = bool(normalize_qcvn_code(text) or re.search(r"\bqcvn\b", ascii_text, re.I))
        has_qcvn_title = "quy chuan ky thuat quoc gia" in ascii_text
        has_cover_signal = any(
            signal in ascii_text
            for signal in ["cong hoa xa hoi", "national technical", "ha noi", "hanoi"]
        )
        if compact_layout and has_qcvn_label and has_qcvn_title and has_cover_signal:
            return True

        if source_order <= 2 and "muc luc" in ascii_text:
            return True

        return False

    def _is_header_boilerplate(self, text: str, metadata: Dict[str, Any]) -> bool:
        if self._is_structural_heading(text):
            return False

        low = text.lower()
        if (
            metadata.get("attachment_kind") == "qcvn"
            and normalize_qcvn_code(text) == metadata.get("label")
            and self._is_qcvn_code_only(text)
        ):
            return True
        if metadata.get("label") and low.startswith(metadata["label"].lower()):
            if metadata.get("attachment_kind") == "qcvn":
                return self._is_qcvn_code_only(text)
            return True
        title = (metadata.get("title") or "").lower()
        if title and (low == title or (len(low) >= 8 and low in title)):
            return True
        if re.match(r"^ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}", low, re.U):
            return True
        if low.startswith("của "):
            return True
        if "cộng hòa xã hội" in low or "độc lập" in low:
            return True
        if metadata.get("attachment_kind") == "qcvn":
            ascii_low = strip_vietnamese_accents(low, keep_dd=False)
            if re.match(r"^(ha\s+noi|hanoi)\s*[-–]\s*\d{4}$", ascii_low, re.I):
                return True
            if re.match(r"^national\s+technical\s+regulations?\b", ascii_low, re.I):
                return True
            return "___" in low
        return any(s in low for s in ["ban hành kèm theo", "kèm theo", "của bộ trưởng", "___"])

    def _is_structural_heading(self, text: str) -> bool:
        return bool(
            self.pat_part.match(text)
            or self.pat_chapter.match(text)
            or self.pat_article.match(text)
        )

    def _attach_heading_title_if_pending(
        self,
        text: str,
        stack: Dict[int, Dict[str, Any]],
        path_stack: Dict[int, str],
        prefix: List[str],
    ) -> bool:
        if not self._is_heading_title_continuation(text):
            return False

        for level in sorted(stack, reverse=True):
            unit = stack[level]
            if unit.get("unit_type") not in {"appendix_internal_appendix", "appendix_part", "appendix_chapter"}:
                continue
            if collapse_ws(unit.get("content") or ""):
                continue

            no = (unit.get("structured_fields") or {}).get("no") or ""
            path_label = self._label_for(unit["unit_type"], no, text)
            unit["content"] = text
            unit["label"] = path_label
            unit["path_text"] = " > ".join(prefix + self._path_parts_before(path_stack, level) + [path_label])
            path_stack[level] = path_label
            return True
        return False

    def _is_heading_title_continuation(self, text: str) -> bool:
        if self._is_structural_heading(text):
            return False
        if self._classify_line(text)[0] is not None:
            return False

        ascii_text = strip_vietnamese_accents(text, keep_dd=False).lower()
        if re.fullmatch(r"(muc luc|loi noi dau|trang)\b.*", ascii_text):
            return False

        letters = [ch for ch in text if ch.isalpha()]
        if len(letters) < 4:
            return False
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        return upper_ratio >= 0.70 and len(text) <= 180

    def _classify_line(self, text: str, *, qcvn_mode: bool = False):
        m = self.pat_part.match(text)
        if m:
            return 1, m.group(1).upper(), collapse_ws(m.group(2)), "appendix_part"

        m = self.pat_chapter.match(text)
        if m:
            return 2, m.group(1).upper(), collapse_ws(m.group(2)), "appendix_chapter"

        m = self.pat_article.match(text)
        if m:
            return 3, m.group(1), collapse_ws(m.group(2)), "appendix_article"

        m = self.pat_internal_appendix.match(text)
        if m:
            return 1, m.group(1).upper(), collapse_ws(m.group(2)), "appendix_internal_appendix"

        m = self.pat_alpha.match(text)
        if m and not self._looks_like_roman_heading(m.group(1)):
            return 1, m.group(1), collapse_ws(m.group(2)), "appendix_section_alpha"

        m = self.pat_roman.match(text)
        if m and len(m.group(1)) <= 8 and self._looks_like_roman_heading(m.group(1)):
            if qcvn_mode:
                return 3, str(self._roman_to_int(m.group(1))), collapse_ws(m.group(2)), "appendix_item_decimal"
            return 2, m.group(1).upper(), collapse_ws(m.group(2)), "appendix_section_roman"

        m = self.pat_decimal.match(text)
        if m:
            no = m.group(1)
            depth = no.count(".")
            return 3 + depth, no, collapse_ws(m.group(2)), "appendix_item_decimal"

        m = self.pat_point.match(text)
        if m:
            return 8, m.group(1), collapse_ws(m.group(2)), "appendix_point"

        m = self.pat_bullet.match(text)
        if m:
            return 9, "-", collapse_ws(m.group(1)), "appendix_bullet"

        return None, None, None, None

    def _reset_stack_for_new_unit(
        self,
        stack: Dict[int, Dict[str, Any]],
        path_stack: Dict[int, str],
        level: int,
        unit_type: str,
        no: str,
    ) -> None:
        for k in list(stack):
            if k >= level:
                stack.pop(k, None)
                path_stack.pop(k, None)

        if unit_type != "appendix_item_decimal":
            return

        # Decimal headings must only inherit from headings with matching
        # numeric prefixes. Without this, "5.1.1" can be attached under a
        # stale "4.1" node because both have the same depth.
        for k in sorted(list(stack)):
            if k >= level:
                continue
            node = stack.get(k) or {}
            if node.get("type") != "appendix_item_decimal":
                continue
            ancestor_no = str((node.get("structured_fields") or {}).get("no") or "")
            if self._is_decimal_ancestor(ancestor_no, no):
                continue
            for stale in [x for x in list(stack) if x >= k]:
                stack.pop(stale, None)
                path_stack.pop(stale, None)
            break

    @staticmethod
    def _is_decimal_ancestor(ancestor_no: str, current_no: str) -> bool:
        ancestor_no = collapse_ws(ancestor_no)
        current_no = collapse_ws(current_no)
        return bool(ancestor_no and current_no.startswith(ancestor_no + "."))

    @staticmethod
    def _parent_for_decimal_no(
        decimal_units_by_no: Dict[str, Dict[str, Any]],
        no: str,
    ) -> Optional[Dict[str, Any]]:
        parts = collapse_ws(no).split(".")
        for size in range(len(parts) - 1, 0, -1):
            parent = decimal_units_by_no.get(".".join(parts[:size]))
            if parent:
                return parent
        return None

    @staticmethod
    def _looks_like_roman_heading(value: str) -> bool:
        token = (value or "").upper()
        if not re.fullmatch(r"[IVXLCDM]+", token):
            return False
        # Single C/D/L/M headings in appendices are usually alphabetic sections.
        return len(token) > 1 or token in {"I", "V", "X"}

    @staticmethod
    def _roman_to_int(value: str) -> int:
        total = 0
        previous = 0
        values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        for char in reversed((value or "").upper()):
            current = values.get(char, 0)
            if current < previous:
                total -= current
            else:
                total += current
                previous = current
        return total

    @staticmethod
    def _is_qcvn_code_only(text: str) -> bool:
        return bool(re.fullmatch(
            r"\s*QCVN\s*\d+[A-Z]?\s*:\s*\d{4}\s*/\s*[A-ZĐ]+\s*",
            text or "",
            re.I | re.U,
        ))

    @staticmethod
    def _is_qcvn_english_title_head(text: str) -> bool:
        ascii_text = strip_vietnamese_accents(text or "", keep_dd=False).lower().strip()
        return bool(re.match(r"^national\s+technical\s+regulations?\b", ascii_text, re.I))

    @staticmethod
    def _is_qcvn_english_title_tail(text: str) -> bool:
        raw = collapse_ws(text or "")
        if not raw or len(raw) > 120:
            return False
        if any(ord(ch) > 127 for ch in raw):
            return False
        if re.search(r"[:;]", raw):
            return False
        if re.match(r"^\d+(?:\.\d+)*\.\s+", raw):
            return False
        letters = re.findall(r"[A-Za-z]", raw)
        if len(letters) < 4:
            return False
        words = re.findall(r"[A-Za-z][A-Za-z-]*", raw)
        return 1 <= len(words) <= 12

    @staticmethod
    def _is_qcvn_toc_heading(text: str) -> bool:
        ascii_text = strip_vietnamese_accents(text, keep_dd=False).lower()
        return bool(re.fullmatch(r"muc\s+luc", ascii_text.strip()))

    @staticmethod
    def _is_qcvn_toc_end(text: str, metadata: Dict[str, Any], *, toc_entry_seen: bool = False) -> bool:
        ascii_text = strip_vietnamese_accents(text, keep_dd=False).lower()
        if toc_entry_seen and "quy chuan ky thuat quoc gia" in ascii_text:
            return True
        label = metadata.get("label")
        if toc_entry_seen and label and normalize_qcvn_code(text) == label:
            return True
        if toc_entry_seen and ascii_text == "loi noi dau":
            return True
        return False

    def _looks_like_qcvn_toc_entry(self, text: str) -> bool:
        ascii_text = strip_vietnamese_accents(text, keep_dd=False).lower().strip()
        if ascii_text in {"trang", "page"}:
            return False
        if ascii_text == "loi noi dau":
            return True
        if re.match(r"^(phu\s+luc)\b", ascii_text, re.I):
            return True
        return self._classify_line(text, qcvn_mode=True)[0] is not None

    @staticmethod
    def _label_for(unit_type: str, no: str, title: str) -> str:
        if unit_type == "appendix_internal_appendix":
            return f"Phụ lục {no}: {title}" if title else f"Phụ lục {no}"
        if unit_type == "appendix_part":
            return f"PHẦN {no}: {title}" if title else f"PHẦN {no}"
        if unit_type == "appendix_chapter":
            return f"CHƯƠNG {no}. {title}" if title else f"CHƯƠNG {no}"
        if unit_type == "appendix_article":
            return f"Điều {no}. {title}" if title else f"Điều {no}"
        if unit_type == "appendix_section_alpha":
            return f"{no}. {title}"
        if unit_type == "appendix_section_roman":
            return f"{no}. {title}"
        if unit_type == "appendix_item_decimal":
            return f"{no}. {title}"
        if unit_type == "appendix_point":
            return f"{no}) {title}"
        if unit_type == "appendix_bullet":
            return f"- {title}"
        return title

    @staticmethod
    def _parent_for_level(stack: Dict[int, Dict[str, Any]], level: int) -> Optional[Dict[str, Any]]:
        lower = [k for k in stack if k < level]
        if not lower:
            return None
        return stack[max(lower)]

    @staticmethod
    def _deepest_parent(stack: Dict[int, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not stack:
            return None
        return stack[max(stack)]

    @staticmethod
    def _path_parts_before(path_stack: Dict[int, str], level: int) -> List[str]:
        return [path_stack[k] for k in sorted(path_stack) if k < level]

    @staticmethod
    def _current_path_parts(path_stack: Dict[int, str]) -> List[str]:
        return [path_stack[k] for k in sorted(path_stack)]
