from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import ChunkBuildResult, ChunkerConfig
from .utils import (
    collapse_ws,
    compact_path_text,
    common_path_text,
    ensure_dir,
    md5_text,
    normalize_id,
    prefixed_path_text,
    read_json,
    strip_vietnamese_accents,
    write_json,
    write_jsonl,
)

logger = logging.getLogger(__name__)

LEGAL_CONTAINER_TYPES = {"phan", "chuong", "muc", "tieu_muc"}
ARTICLE_TYPE = "dieu"
CLAUSE_TYPE = "khoan"
POINT_TYPE = "diem"
TABLE_TYPES = {"table", "appendix_table", "form_table", "table_row"}
ATTACHMENT_BOUNDARY_TYPES = {
    "appendix_internal_appendix",
    "appendix_part",
    "appendix_chapter",
    "appendix_article",
    "appendix_section_alpha",
    "appendix_section_roman",
}
ATTACHMENT_CONTAINER_TYPES = ATTACHMENT_BOUNDARY_TYPES | {"appendix_item_decimal"}


class EffectivityResolver:
    """Resolves legal effectivity dates for document units based on pre-extracted effectivity data."""

    def __init__(self, effectivity_dir: Optional[Path]) -> None:
        self.general_by_doc_id: Dict[str, Dict[str, Any]] = {}
        self.rules_by_doc_id: Dict[str, List[Dict[str, Any]]] = {}
        if effectivity_dir:
            self._load(effectivity_dir)

    def _load(self, effectivity_dir: Path) -> None:
        general_path = effectivity_dir / "effectivity_general.json"
        units_path = effectivity_dir / "effectivity_units.json"
        if general_path.exists():
            try:
                for row in read_json(general_path):
                    doc_id = row.get("document_id")
                    if doc_id and row.get("in_corpus", True):
                        self.general_by_doc_id[doc_id] = row
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping malformed effectivity_general.json: %s", exc)
        if units_path.exists():
            try:
                for row in read_json(units_path):
                    doc_id = row.get("document_id")
                    if not doc_id:
                        continue
                    rule = self._rule_from_unit_row(row)
                    if rule:
                        self.rules_by_doc_id.setdefault(doc_id, []).append(rule)
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping malformed effectivity_units.json: %s", exc)

    @staticmethod
    def _rule_from_unit_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        doc_id = row.get("document_id")
        selector = row.get("target_unit_selector") or {}
        if not doc_id or not selector:
            return None
        if selector.get("appendix"):
            return {
                "kind": "appendix",
                "appendix": str(selector["appendix"]).upper(),
                "effective_from": row.get("effective_from"),
                "specificity": 1,
            }
        article = selector.get("article")
        if not article:
            return None
        prefix = f"{doc_id}.dieu_{normalize_id(str(article))}"
        specificity = 1
        if selector.get("clause"):
            prefix += f".khoan_{normalize_id(str(selector['clause']))}"
            specificity += 1
        if selector.get("point"):
            prefix += f".diem_{normalize_id(str(selector['point']))}"
            specificity += 1
        return {
            "kind": "unit",
            "prefix": prefix,
            "effective_from": row.get("effective_from"),
            "specificity": specificity,
        }

    def has_target_below(self, document_id: str, node_id: str) -> bool:
        for rule in self.rules_by_doc_id.get(document_id, []):
            prefix = rule.get("prefix")
            if prefix and prefix.startswith(node_id + "."):
                return True
        return False

    def resolve(self, document_id: str, source_unit_ids: List[str], path_text: str) -> Tuple[Optional[str], Optional[str]]:
        general = self.general_by_doc_id.get(document_id) or {}
        effective_from = general.get("effective_from")
        effective_to = general.get("effective_to")

        matched_rules = []
        for rule in self.rules_by_doc_id.get(document_id, []):
            if self._matches_rule(rule, source_unit_ids, path_text):
                matched_rules.append(rule)
        if matched_rules:
            matched_rules.sort(key=lambda item: item.get("specificity", 0), reverse=True)
            effective_from = matched_rules[0].get("effective_from") or effective_from
        return effective_from, effective_to

    @staticmethod
    def _matches_rule(rule: Dict[str, Any], source_unit_ids: List[str], path_text: str) -> bool:
        if rule.get("kind") == "unit":
            prefix = rule.get("prefix")
            return bool(prefix and any(unit_id == prefix or unit_id.startswith(prefix + ".") for unit_id in source_unit_ids))
        if rule.get("kind") == "appendix":
            appendix = rule.get("appendix") or ""
            ascii_path = strip_vietnamese_accents(path_text, keep_dd=False).lower()
            appendix_text = strip_vietnamese_accents(f"Phụ lục {appendix}", keep_dd=False).lower()
            appendix_id = f"phu_luc_{appendix.lower()}"
            return appendix_text in ascii_path or any(appendix_id in unit_id.lower() for unit_id in source_unit_ids)
        return False


class LegalChunkBuilder:
    """Builds RAG-ready text chunks from parsed Vietnamese legal document trees.

    Supports hierarchical chunking by điều (article) → khoản (clause) → điểm (point),
    with configurable size limits, effectivity date resolution, and table handling.
    """

    def __init__(self, config: Optional[ChunkerConfig] = None) -> None:
        self.config = config or ChunkerConfig()
        self.effectivity = EffectivityResolver(self.config.effectivity_dir)
        self._chunk_counter = 0

    def build_dataset(self, input_dir: Optional[Path] = None, output_dir: Optional[Path] = None) -> ChunkBuildResult:
        """Build chunks from all packages under *input_dir* and write results to *output_dir*."""
        self._chunk_counter = 0
        input_dir = Path(input_dir or self.config.parsed_input_dir)
        output_dir = ensure_dir(output_dir or self.config.output_dir)
        package_dirs = self._find_package_dirs(input_dir)
        logger.info("Found %d package(s) in %s", len(package_dirs), input_dir)

        all_chunks: List[Dict[str, Any]] = []
        package_counts: Dict[str, int] = {}
        for package_dir in package_dirs:
            package_chunks = self.build_package(package_dir)
            package_id = package_dir.name
            package_counts[package_id] = len(package_chunks)
            all_chunks.extend(package_chunks)
            if self.config.write_package_chunks:
                package_out = ensure_dir(output_dir / package_id)
                write_jsonl(package_out / "chunks.jsonl", package_chunks)

        chunks_path = output_dir / "chunks.jsonl"
        manifest_path = output_dir / "manifest.json"
        write_jsonl(chunks_path, all_chunks)
        write_json(manifest_path, {
            "input_dir": str(input_dir),
            "effectivity_dir": str(self.config.effectivity_dir),
            "output_dir": str(output_dir),
            "mode": self.config.mode,
            "max_chars_per_chunk": self.config.max_chars_per_chunk,
            "package_count": len(package_dirs),
            "chunk_count": len(all_chunks),
            "schema": [
                "chunk_id",
                "source_unit_ids",
                "document_number",
                "document_title",
                "document_type",
                "path_text",
                "content",
                "effective_from",
                "effective_to",
                "source_file",
                "source_url",
            ],
            "package_chunk_counts": package_counts,
        })
        return ChunkBuildResult(
            output_dir=output_dir,
            chunks_path=chunks_path,
            manifest_path=manifest_path,
            package_count=len(package_dirs),
            chunk_count=len(all_chunks),
            package_chunk_counts=package_counts,
        )

    def build_package(self, package_dir: Path) -> List[Dict[str, Any]]:
        """Build chunks for a single package directory."""
        inventory_path = package_dir / "package_inventory.json"
        if not inventory_path.exists():
            return []
        try:
            inventory = read_json(inventory_path)
        except (ValueError, OSError) as exc:
            logger.warning("Skipping package %s – cannot read inventory: %s", package_dir.name, exc)
            return []
        main_doc = inventory.get("main_document") or {}
        base_context = {
            "package_id": inventory.get("package_id") or package_dir.name,
            "document_id": main_doc.get("document_id"),
            "document_number": main_doc.get("document_number"),
            "document_title": main_doc.get("document_title"),
            "document_type": main_doc.get("document_type"),
            "source_file": main_doc.get("source_file"),
            "source_url": main_doc.get("source_url"),
        }

        chunks: List[Dict[str, Any]] = []
        main_tree_path = package_dir / "main" / "tree.json"
        if main_tree_path.exists():
            try:
                main_tree = read_json(main_tree_path)
            except (ValueError, OSError) as exc:
                logger.warning("Skipping main tree in %s: %s", package_dir.name, exc)
                main_tree = None
            if main_tree:
                context = self._context_from_tree(base_context, main_tree.get("metadata") or {}, source_file=base_context.get("source_file"))
                chunks.extend(self._chunk_main_tree(main_tree, context))

        for attachment in inventory.get("attachments") or []:
            tree_path = self._attachment_tree_path(package_dir, attachment)
            if not tree_path or not tree_path.exists():
                continue
            try:
                tree = read_json(tree_path)
            except (ValueError, OSError) as exc:
                logger.warning("Skipping attachment tree %s: %s", tree_path, exc)
                continue
            metadata = tree.get("metadata") or {}
            context = self._context_from_tree(
                base_context,
                metadata,
                source_file=metadata.get("source_file") or attachment.get("source_file"),
            )
            chunks.extend(self._chunk_attachment_tree(tree, context))

        logger.info("Package %s: %d chunk(s)", package_dir.name, len(chunks))
        return chunks

    @staticmethod
    def _find_package_dirs(input_dir: Path) -> List[Path]:
        if (input_dir / "package_inventory.json").exists():
            return [input_dir]
        if not input_dir.exists():
            return []
        return sorted([p for p in input_dir.iterdir() if p.is_dir() and (p / "package_inventory.json").exists()])

    @staticmethod
    def _attachment_tree_path(package_dir: Path, attachment: Dict[str, Any]) -> Optional[Path]:
        """Resolve the tree.json path for an attachment, guarding against path traversal."""
        raw_tree_path = attachment.get("tree_path")
        if raw_tree_path:
            path = Path(raw_tree_path)
            # Only accept absolute paths that actually sit under package_dir
            if path.is_absolute():
                try:
                    path.resolve().relative_to(package_dir.resolve())
                except ValueError:
                    logger.warning("Ignoring out-of-scope tree_path: %s", raw_tree_path)
                    path = None
            else:
                path = package_dir / path
            if path and path.exists():
                return path
        parsed_dir = attachment.get("parsed_dir")
        if parsed_dir:
            return package_dir / parsed_dir / "tree.json"
        return None

    @staticmethod
    def _context_from_tree(base: Dict[str, Any], metadata: Dict[str, Any], *, source_file: Optional[str]) -> Dict[str, Any]:
        context = dict(base)
        context["document_id"] = context.get("document_id") or metadata.get("document_id")
        context["document_number"] = context.get("document_number") or metadata.get("document_number")
        context["document_title"] = context.get("document_title") or metadata.get("document_title") or metadata.get("title")
        context["document_type"] = context.get("document_type") or metadata.get("document_type")
        context["source_file"] = source_file or metadata.get("source_file") or context.get("source_file")
        context["source_url"] = metadata.get("source_url") or context.get("source_url")
        context["attachment_label"] = metadata.get("label")
        context["attachment_title"] = metadata.get("title")
        return context

    def _chunk_main_tree(self, tree: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        roots = tree.get("body") or []
        articles = list(self._iter_nodes_by_type(roots, ARTICLE_TYPE))
        if not articles:
            return self._chunk_node_sequence(roots, context)

        chunks: List[Dict[str, Any]] = []
        for article in articles:
            chunks.extend(self._chunk_article(article, context))
        return chunks

    def _chunk_article(self, article: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        document_id = context.get("document_id") or article.get("document_id") or ""
        article_text = self._render_subtree(article, skip_nested_articles=True)
        article_ids = self._collect_source_ids(article, skip_nested_articles=True)
        split_for_effectivity = self.effectivity.has_target_below(document_id, article.get("id") or "")
        if self.config.mode == "article" and self._fits(context, article.get("path_text") or "", article_ids, article_text):
            split_for_effectivity = False
        if (
            self._fits(context, article.get("path_text") or "", article_ids, article_text)
            and not split_for_effectivity
        ):
            return [self._make_chunk(context, article.get("path_text") or "", article_ids, article_text)]

        chunks: List[Dict[str, Any]] = []
        intro_nodes = []
        clause_nodes = []
        other_nodes = []
        for child in article.get("children") or []:
            if child.get("type") == CLAUSE_TYPE:
                clause_nodes.append(child)
            elif self._is_table_node(child):
                other_nodes.append(child)
            elif child.get("type") == ARTICLE_TYPE:
                continue
            elif not clause_nodes and child.get("type") in {"text", "quote"}:
                intro_nodes.append(child)
            else:
                other_nodes.append(child)

        if clause_nodes:
            for clause in clause_nodes:
                chunks.extend(self._chunk_clause(article, clause, intro_nodes, context))
            if other_nodes:
                chunks.extend(self._chunk_node_sequence(other_nodes, context, prefix_nodes=[self._shallow_node(article)] + intro_nodes))
            return chunks

        point_nodes = [child for child in article.get("children") or [] if child.get("type") == POINT_TYPE]
        if point_nodes:
            for point in point_nodes:
                body = self._join_lines([self._node_line(article), self._render_subtree(point)])
                ids = self._dedupe_ids([article.get("id")] + self._collect_source_ids(point))
                chunks.append(self._make_chunk(context, point.get("path_text") or article.get("path_text") or "", ids, body))
            return chunks

        return self._chunk_node_sequence(article.get("children") or [], context, prefix_nodes=[self._shallow_node(article)])

    def _chunk_clause(
        self,
        article: Dict[str, Any],
        clause: Dict[str, Any],
        intro_nodes: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        document_id = context.get("document_id") or clause.get("document_id") or ""
        prefix_nodes = [self._shallow_node(article)] + intro_nodes
        prefix_text = self._render_nodes(prefix_nodes, skip_nested_articles=True)
        clause_text = self._join_lines([prefix_text, self._render_subtree(clause, skip_nested_articles=True)])
        clause_ids = self._dedupe_ids(
            self._collect_source_ids_from_nodes(prefix_nodes, skip_nested_articles=True)
            + self._collect_source_ids(clause, skip_nested_articles=True)
        )
        split_for_effectivity = self.effectivity.has_target_below(document_id, clause.get("id") or "")
        if self._fits(context, clause.get("path_text") or article.get("path_text") or "", clause_ids, clause_text) and not split_for_effectivity:
            return [self._make_chunk(context, clause.get("path_text") or article.get("path_text") or "", clause_ids, clause_text)]

        point_nodes = [child for child in clause.get("children") or [] if child.get("type") == POINT_TYPE]
        if not point_nodes:
            return self._chunk_node_sequence(clause.get("children") or [], context, prefix_nodes=prefix_nodes + [clause])

        chunks = []
        lead_nodes = [child for child in clause.get("children") or [] if child.get("type") != POINT_TYPE and not self._is_table_node(child)]
        lead_text = self._render_nodes(lead_nodes, skip_nested_articles=True)
        base_nodes = prefix_nodes + [self._shallow_node(clause)] + lead_nodes
        base_text = self._join_lines([self._render_nodes(prefix_nodes, skip_nested_articles=True), self._node_line(clause), lead_text])
        base_ids = self._collect_source_ids_from_nodes(base_nodes, skip_nested_articles=True)
        for point in point_nodes:
            point_text = self._join_lines([base_text, self._render_subtree(point, skip_nested_articles=True)])
            point_ids = self._dedupe_ids(base_ids + self._collect_source_ids(point, skip_nested_articles=True))
            if self._fits(context, point.get("path_text") or clause.get("path_text") or "", point_ids, point_text):
                chunks.append(self._make_chunk(context, point.get("path_text") or clause.get("path_text") or "", point_ids, point_text))
            else:
                chunks.extend(self._split_text_chunk(context, point.get("path_text") or clause.get("path_text") or "", point_ids, point_text))
        return chunks

    def _chunk_attachment_tree(self, tree: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        roots = tree.get("body") or []
        return self._chunk_node_sequence(roots, context, attachment_mode=True)

    def _chunk_node_sequence(
        self,
        nodes: List[Dict[str, Any]],
        context: Dict[str, Any],
        *,
        prefix_nodes: Optional[List[Dict[str, Any]]] = None,
        attachment_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        pending: List[Dict[str, Any]] = []
        prefix_nodes = prefix_nodes or []

        def flush_pending() -> None:
            if not pending:
                return
            body = self._join_lines([self._render_nodes(prefix_nodes, skip_nested_articles=True), self._render_nodes(pending, skip_nested_articles=True)])
            ids = self._dedupe_ids(
                self._collect_source_ids_from_nodes(prefix_nodes, skip_nested_articles=True)
                + self._collect_source_ids_from_nodes(pending, skip_nested_articles=True)
            )
            path_text = common_path_text([n.get("path_text") or "" for n in pending]) or (prefix_nodes[-1].get("path_text") if prefix_nodes else "")
            if self._fits(context, path_text, ids, body):
                chunks.append(self._make_chunk(context, path_text, ids, body))
            else:
                chunks.extend(self._split_text_chunk(context, path_text, ids, body))
            pending.clear()

        for node in nodes:
            if pending and attachment_mode and (
                self._is_attachment_boundary_node(node)
                or self._starts_new_decimal_family(pending, node)
            ):
                flush_pending()
            if self._is_table_node(node):
                flush_pending()
                chunks.extend(self._chunk_table_node(node, context, prefix_nodes=prefix_nodes))
                continue
            if attachment_mode and self._should_descend_attachment_container(node):
                flush_pending()
                child_prefix = prefix_nodes + [self._shallow_node(node)]
                chunks.extend(self._chunk_node_sequence(node.get("children") or [], context, prefix_nodes=child_prefix, attachment_mode=attachment_mode))
                continue
            node_text = self._render_subtree(node, skip_nested_articles=True)
            projected = self._join_lines([
                self._render_nodes(prefix_nodes, skip_nested_articles=True),
                self._render_nodes(pending, skip_nested_articles=True),
                node_text,
            ])
            if node.get("children") and len(node_text) > self.config.max_chars_per_chunk:
                flush_pending()
                child_prefix = prefix_nodes + [self._shallow_node(node)]
                chunks.extend(self._chunk_node_sequence(node.get("children") or [], context, prefix_nodes=child_prefix, attachment_mode=attachment_mode))
                continue
            projected_nodes = pending + [node]
            projected_path = common_path_text([n.get("path_text") or "" for n in projected_nodes]) or (prefix_nodes[-1].get("path_text") if prefix_nodes else "")
            projected_ids = self._dedupe_ids(
                self._collect_source_ids_from_nodes(prefix_nodes, skip_nested_articles=True)
                + self._collect_source_ids_from_nodes(projected_nodes, skip_nested_articles=True)
            )
            if pending and not self._fits(context, projected_path, projected_ids, projected):
                flush_pending()
            pending.append(node)
        flush_pending()
        return chunks

    def _chunk_table_node(
        self,
        node: Dict[str, Any],
        context: Dict[str, Any],
        *,
        prefix_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._table_rows(node)
        if not rows:
            body = self._join_lines([self._render_nodes(prefix_nodes or []), self._node_line(node)])
            ids = self._dedupe_ids(self._collect_source_ids_from_nodes(prefix_nodes or []) + self._collect_source_ids(node))
            return [self._make_chunk(context, node.get("path_text") or "", ids, body)]

        header_idx, header = self._first_nonempty_row(rows)
        data_rows = [(idx, row) for idx, row in enumerate(rows, start=1) if idx != header_idx and any(c.strip() for c in row)]
        if not data_rows and header:
            data_rows = [(header_idx, header)]

        chunks: List[Dict[str, Any]] = []
        current_rows: List[Tuple[int, List[str]]] = []
        for row_idx, row in data_rows:
            candidate = current_rows + [(row_idx, row)]
            if current_rows and not self._fits(
                context,
                self._table_chunk_path(node, candidate),
                self._table_chunk_ids(node, candidate, prefix_nodes=prefix_nodes),
                self._format_table_body(node, header, candidate, prefix_nodes=prefix_nodes),
            ):
                chunks.extend(self._make_table_chunks(node, context, header, current_rows, prefix_nodes=prefix_nodes))
                current_rows = [(row_idx, row)]
            else:
                current_rows = candidate
        if current_rows:
            chunks.extend(self._make_table_chunks(node, context, header, current_rows, prefix_nodes=prefix_nodes))
        return chunks

    def _make_table_chunks(
        self,
        node: Dict[str, Any],
        context: Dict[str, Any],
        header: List[str],
        rows: List[Tuple[int, List[str]]],
        *,
        prefix_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        body = self._format_table_body(node, header, rows, prefix_nodes=prefix_nodes)
        source_ids = self._table_chunk_ids(node, rows, prefix_nodes=prefix_nodes)
        path_text = self._table_chunk_path(node, rows)
        if self._fits(context, path_text, source_ids, body):
            return [self._make_chunk(context, path_text, source_ids, body)]
        return self._split_text_chunk(context, path_text, source_ids, body)

    def _format_table_body(
        self,
        node: Dict[str, Any],
        header: List[str],
        rows: List[Tuple[int, List[str]]],
        *,
        prefix_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        lines = [self._render_nodes(prefix_nodes or []), self._node_line(node)]
        header_text = self._row_text(header)
        if header_text:
            lines.append(f"Header: {header_text}")
        for row_idx, row in rows:
            row_text = self._row_text(row)
            if row_text:
                lines.append(f"Dòng {row_idx}: {row_text}")
        return self._join_lines(lines)

    def _split_text_chunk(self, context: Dict[str, Any], path_text: str, source_ids: List[str], body: str) -> List[Dict[str, Any]]:
        lines = [line for line in body.splitlines() if collapse_ws(line)]
        chunks: List[Dict[str, Any]] = []
        current: List[str] = []
        for line in lines:
            for part in self._split_line_if_needed(context, path_text, source_ids, line):
                projected = "\n".join(current + [part])
                if current and not self._fits(context, path_text, source_ids, projected):
                    chunks.append(self._make_chunk(context, path_text, source_ids, "\n".join(current)))
                    current = [part]
                else:
                    current.append(part)
        if current:
            chunks.append(self._make_chunk(context, path_text, source_ids, "\n".join(current)))
        return chunks

    def _split_line_if_needed(
        self,
        context: Dict[str, Any],
        path_text: str,
        source_ids: List[str],
        line: str,
    ) -> List[str]:
        line = line.strip()
        if self._fits(context, path_text, source_ids, line):
            return [line]
        limit = self._body_char_limit(context, path_text, source_ids)
        parts: List[str] = []
        rest = line
        while rest:
            if len(rest) <= limit and self._fits(context, path_text, source_ids, rest):
                parts.append(rest)
                break
            window = rest[:limit]
            cut = self._best_split_index(window)
            part = rest[:cut].strip()
            if not part:
                part = rest[:limit].strip()
                cut = limit
            parts.append(part)
            rest = rest[cut:].strip()
        return parts

    def _body_char_limit(self, context: Dict[str, Any], path_text: str, source_ids: List[str]) -> int:
        path_text = compact_path_text(prefixed_path_text(context.get("document_number"), path_text))
        effective_from, effective_to = self.effectivity.resolve(context.get("document_id") or "", source_ids, path_text)
        header = self._format_chunk_content(context, path_text, "", effective_from, effective_to)
        return max(500, self.config.max_chars_per_chunk - len(header) - 8)

    @staticmethod
    def _best_split_index(text: str) -> int:
        if not text:
            return 0
        preferred = [
            ". ",
            "; ",
            ": ",
            " ♦ ",
            " - ",
            " | ",
            ", ",
            " ",
        ]
        minimum = max(1, int(len(text) * 0.55))
        for marker in preferred:
            idx = text.rfind(marker)
            if idx >= minimum:
                return idx + len(marker)
        return len(text)

    def _fits(self, context: Dict[str, Any], path_text: str, source_unit_ids: List[str], body_text: str) -> bool:
        path_text = compact_path_text(prefixed_path_text(context.get("document_number"), path_text))
        effective_from, effective_to = self.effectivity.resolve(context.get("document_id") or "", source_unit_ids, path_text)
        content = self._format_chunk_content(context, path_text, body_text, effective_from, effective_to)
        return len(content) <= self.config.max_chars_per_chunk

    def _table_chunk_ids(
        self,
        node: Dict[str, Any],
        rows: List[Tuple[int, List[str]]],
        *,
        prefix_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        return self._dedupe_ids(
            self._collect_source_ids_from_nodes(prefix_nodes or [])
            + [node.get("id")]
            + self._table_row_ids(node, [idx for idx, _ in rows])
        )

    @staticmethod
    def _table_chunk_path(node: Dict[str, Any], rows: List[Tuple[int, List[str]]]) -> str:
        if rows:
            start, end = rows[0][0], rows[-1][0]
            return f"{node.get('path_text') or ''} > Dòng {start}-{end}"
        return node.get("path_text") or ""

    def _make_chunk(self, context: Dict[str, Any], path_text: str, source_unit_ids: List[str], body_text: str) -> Dict[str, Any]:
        source_unit_ids = [unit_id for unit_id in self._dedupe_ids(source_unit_ids) if unit_id]
        path_text = compact_path_text(prefixed_path_text(context.get("document_number"), path_text))
        effective_from, effective_to = self.effectivity.resolve(context.get("document_id") or "", source_unit_ids, path_text)
        content = self._format_chunk_content(context, path_text, body_text, effective_from, effective_to)
        hash_key = "|".join(source_unit_ids) + "\n" + path_text + "\n" + content
        base = source_unit_ids[0] if source_unit_ids else (context.get("document_id") or "chunk")
        self._chunk_counter += 1
        chunk_id = f"{base}.chunk_{self._chunk_counter:08d}_{md5_text(hash_key)[:10]}"
        return {
            "chunk_id": chunk_id,
            "source_unit_ids": source_unit_ids,
            "document_number": context.get("document_number"),
            "document_title": context.get("document_title"),
            "document_type": context.get("document_type"),
            "path_text": path_text,
            "content": content,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "source_file": context.get("source_file"),
            "source_url": context.get("source_url"),
        }

    @staticmethod
    def _format_chunk_content(
        context: Dict[str, Any],
        path_text: str,
        body_text: str,
        effective_from: Optional[str],
        effective_to: Optional[str],
    ) -> str:
        doc_line = collapse_ws(" - ".join([x for x in [context.get("document_number"), context.get("document_title")] if x]))
        lines = []
        if doc_line:
            lines.append(f"Văn bản: {doc_line}")
        if effective_from or effective_to:
            lines.append(f"Hiệu lực: từ {effective_from or 'không rõ'} đến {effective_to or 'còn hiệu lực/không rõ'}")
        if path_text:
            lines.append(f"Đường dẫn: {path_text}")
        lines.append("")
        lines.append(body_text.strip())
        return "\n".join([line for line in lines if line is not None]).strip()

    def _render_subtree(self, node: Dict[str, Any], *, skip_nested_articles: bool = False, is_root: bool = True) -> str:
        if skip_nested_articles and not is_root and node.get("type") == ARTICLE_TYPE:
            return self._node_line(node)
        if self._is_table_node(node):
            return self._render_table_preview(node)
        lines = [self._node_line(node)]
        for child in node.get("children") or []:
            child_text = self._render_subtree(child, skip_nested_articles=skip_nested_articles, is_root=False)
            if child_text:
                lines.append(child_text)
        return self._join_lines(lines)

    def _render_nodes(self, nodes: Iterable[Dict[str, Any]], *, skip_nested_articles: bool = False) -> str:
        return self._join_lines([self._render_subtree(node, skip_nested_articles=skip_nested_articles) for node in nodes])

    @staticmethod
    def _node_line(node: Dict[str, Any]) -> str:
        node_type = node.get("type")
        label = collapse_ws(node.get("label") or "")
        content = collapse_ws(node.get("content") or "")
        if not label:
            label = LegalChunkBuilder._label_from_structured_fields(node_type, node, content)
        if node_type in {"text", "appendix_paragraph", "form_text"}:
            return content
        if label and content and content.casefold() in label.casefold():
            return label
        if label and content and label.casefold() not in content.casefold():
            if node_type in {"quote"}:
                return f"{label}:\n{content}"
            return label
        return label or content

    @staticmethod
    def _label_from_structured_fields(node_type: str, node: Dict[str, Any], content: str) -> str:
        fields = node.get("structured_fields") or {}
        no = collapse_ws(str(fields.get("no") or ""))
        if not no or not content:
            return ""
        if node_type == "appendix_internal_appendix":
            return f"Phụ lục {no}: {content}"
        if node_type == "appendix_part":
            return f"PHẦN {no}: {content}"
        if node_type == "appendix_chapter":
            return f"CHƯƠNG {no}. {content}"
        if node_type == "appendix_article":
            return f"Điều {no}. {content}"
        if node_type in {"appendix_section_alpha", "appendix_section_roman", "appendix_item_decimal"}:
            return f"{no}. {content}"
        if node_type == "appendix_point":
            return f"{no}) {content}"
        if node_type == "appendix_bullet":
            return f"- {content}"
        return ""

    def _render_table_preview(self, node: Dict[str, Any]) -> str:
        rows = self._table_rows(node)
        lines = [self._node_line(node)]
        for row in rows[:12]:
            row_text = self._row_text(row)
            if row_text:
                lines.append(row_text)
        if len(rows) > 12:
            lines.append(f"... ({len(rows) - 12} dòng còn lại)")
        return self._join_lines(lines)

    @staticmethod
    def _join_lines(lines: Iterable[str]) -> str:
        out = []
        for line in lines:
            if not line:
                continue
            text = str(line).strip()
            if text:
                out.append(text)
        return "\n".join(out)

    def _collect_source_ids(self, node: Dict[str, Any], *, skip_nested_articles: bool = False, is_root: bool = True) -> List[str]:
        if skip_nested_articles and not is_root and node.get("type") == ARTICLE_TYPE:
            return [node.get("id")]
        ids = [node.get("id")]
        for child in node.get("children") or []:
            ids.extend(self._collect_source_ids(child, skip_nested_articles=skip_nested_articles, is_root=False))
        return self._dedupe_ids(ids)

    def _collect_source_ids_from_nodes(self, nodes: Iterable[Dict[str, Any]], *, skip_nested_articles: bool = False) -> List[str]:
        ids: List[str] = []
        for node in nodes:
            ids.extend(self._collect_source_ids(node, skip_nested_articles=skip_nested_articles))
        return self._dedupe_ids(ids)

    @staticmethod
    def _dedupe_ids(ids: Iterable[Optional[str]]) -> List[str]:
        out: List[str] = []
        seen = set()
        for unit_id in ids:
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            out.append(unit_id)
        return out

    @staticmethod
    def _iter_nodes_by_type(nodes: Iterable[Dict[str, Any]], node_type: str) -> Iterable[Dict[str, Any]]:
        for node in nodes:
            if node.get("type") == node_type:
                yield node
            yield from LegalChunkBuilder._iter_nodes_by_type(node.get("children") or [], node_type)

    @staticmethod
    def _is_table_node(node: Dict[str, Any]) -> bool:
        node_type = node.get("type")
        return node_type in TABLE_TYPES or "normalized_rows" in node or bool((node.get("table") or {}).get("normalized_rows"))

    @staticmethod
    def _is_attachment_boundary_node(node: Dict[str, Any]) -> bool:
        node_type = node.get("type")
        if node_type in ATTACHMENT_BOUNDARY_TYPES:
            return True
        if node_type != "appendix_item_decimal":
            return False
        no = collapse_ws(str((node.get("structured_fields") or {}).get("no") or ""))
        return bool(no and "." not in no)

    @staticmethod
    def _should_descend_attachment_container(node: Dict[str, Any]) -> bool:
        return bool(node.get("children")) and node.get("type") in ATTACHMENT_CONTAINER_TYPES

    @staticmethod
    def _starts_new_decimal_family(pending: List[Dict[str, Any]], node: Dict[str, Any]) -> bool:
        current_no = LegalChunkBuilder._decimal_no(node)
        if not current_no or "." not in current_no:
            return False

        previous_no = ""
        for item in reversed(pending):
            previous_no = LegalChunkBuilder._decimal_no(item)
            if previous_no:
                break
        if not previous_no:
            return False

        if current_no.startswith(previous_no + ".") or previous_no.startswith(current_no + "."):
            return False

        current_parent = LegalChunkBuilder._decimal_parent_no(current_no)
        previous_parent = LegalChunkBuilder._decimal_parent_no(previous_no)
        if current_parent and current_parent == previous_parent:
            return False
        if current_parent == previous_no or previous_parent == current_no:
            return False
        return True

    @staticmethod
    def _decimal_no(node: Dict[str, Any]) -> str:
        if node.get("type") != "appendix_item_decimal":
            return ""
        return collapse_ws(str((node.get("structured_fields") or {}).get("no") or ""))

    @staticmethod
    def _decimal_parent_no(no: str) -> str:
        return no.rsplit(".", 1)[0] if "." in no else ""

    @staticmethod
    def _table_rows(node: Dict[str, Any]) -> List[List[str]]:
        rows = node.get("normalized_rows")
        if rows:
            return rows
        table = node.get("table") or {}
        rows = table.get("normalized_rows")
        if rows:
            return rows
        child_rows = []
        for child in node.get("children") or []:
            if child.get("type") == "table_row":
                fields = child.get("structured_fields") or {}
                cells = fields.get("cells")
                if cells:
                    child_rows.append(cells)
                elif child.get("content"):
                    child_rows.append([child.get("content")])
        return child_rows

    @staticmethod
    def _first_nonempty_row(rows: List[List[str]]) -> Tuple[int, List[str]]:
        for idx, row in enumerate(rows, start=1):
            if any(collapse_ws(cell) for cell in row):
                return idx, row
        return 0, []

    @staticmethod
    def _row_text(row: List[str]) -> str:
        return " | ".join([collapse_ws(str(cell)) for cell in row if collapse_ws(str(cell))])

    @staticmethod
    def _table_row_ids(node: Dict[str, Any], row_indexes: List[int]) -> List[str]:
        wanted = set(row_indexes)
        ids = []
        fallback_index = 0
        for child in node.get("children") or []:
            if child.get("type") != "table_row":
                continue
            fallback_index += 1
            row_index = (child.get("structured_fields") or {}).get("row_index") or fallback_index
            if row_index in wanted:
                ids.append(child.get("id"))
        return ids

    @staticmethod
    def _shallow_node(node: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of *node* with children cleared (safe against mutation)."""
        out = {k: v for k, v in node.items() if k != "children"}
        out["children"] = []
        return out
