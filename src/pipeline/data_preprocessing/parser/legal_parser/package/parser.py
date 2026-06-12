from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from ..body.parser import LegalBodyParser
    from ..common.models import ParserConfig
except Exception:  # pragma: no cover
    LegalBodyParser = None
    ParserConfig = None

from ..attachments.appendix_parser import AppendixParser
from ..attachments.classifier import AttachmentKind, attachment_slug, classify_attachment
from ..attachments.common import ensure_dir, write_json
from ..attachments.form_parser import FormParser
from ..attachments.qcvn_parser import QCVNParser
from ..common.doc_converter import convert_legacy_docs_under, find_legacy_doc_files
from ..common.logging_utils import get_logger
from ..common.utils import strip_vietnamese_accents


@dataclass
class PackageParseResult:
    package_id: str
    output_dir: Path
    main_file: Optional[Path]
    attachment_count: int
    main_node_count: int
    main_table_count: int
    converted_doc_count: int = 0
    failed_doc_conversion_count: int = 0


ATTACHMENT_PREFIXES = ("phu luc", "phụ lục", "mau", "mẫu", "qcvn", "quy chuan", "quy chuẩn", "dkx")


WARN_OUTPUT_BYTES = 50 * 1024 * 1024


class LegalPackageParser:
    """
    Parse one raw folder as a legal package:

      package/
        main docx
        attachments docx...

    Output:
      parsed/<PACKAGE_ID>/
        package_inventory.json
        main/tree.json
        attachments/<attachment_slug>/
    """

    def __init__(
        self,
        output_base_dir: Union[str, Path],
        *,
        logger: Optional[logging.Logger] = None,
        convert_doc: bool = True,
        delete_converted_doc: bool = True,
    ):
        self.output_base_dir = Path(output_base_dir).resolve()
        self.logger = get_logger(logger)
        self.convert_doc = convert_doc
        self.delete_converted_doc = delete_converted_doc

    def parse_dataset(self, dataset_dir: Union[str, Path]) -> List[PackageParseResult]:
        dataset_dir = Path(dataset_dir).resolve()
        results = []
        for package_dir in sorted([p for p in dataset_dir.iterdir() if p.is_dir()]):
            try:
                results.append(self.parse_package(package_dir))
            except Exception as e:
                self.logger.error("❌ Lỗi package %s: %s", package_dir, e)
        return results

    def parse_package(self, package_dir: Union[str, Path]) -> PackageParseResult:
        package_dir = Path(package_dir).resolve()
        package_id = package_dir.name
        out_dir = self.output_base_dir / package_id
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir = ensure_dir(out_dir)

        inventory: Dict[str, Any] = {
            "package_id": package_id,
            "source_dir": str(package_dir),
            "main_document": None,
            "attachments": [],
            "converted_files": [],
            "unsupported_files": [],
        }

        conversion_results = []
        if self.convert_doc:
            conversion_results = convert_legacy_docs_under(
                package_dir,
                recursive=False,
                delete_source=self.delete_converted_doc,
                logger=self.logger,
            )
            for item in conversion_results:
                inventory["converted_files"].append({
                    "source_file": str(item.source_path),
                    "target_file": str(item.target_path),
                    "status": item.status,
                    "converter": item.converter,
                    "message": item.message,
                    "deleted_source": item.deleted_source,
                })

        unsupported_doc_files = find_legacy_doc_files(package_dir, recursive=False)
        for unsupported in unsupported_doc_files:
            inventory["unsupported_files"].append({
                "source_file": str(unsupported),
                "reason": "Legacy .doc files are not parsed by python-docx and conversion did not produce a .docx.",
            })

        docx_files = sorted([p for p in package_dir.glob("*.docx") if not p.name.startswith("~$")])
        main_file, attachments = self._split_main_and_attachments(docx_files)

        self.logger.info(
            "📦 Package %s | main=%s | attachments=%s | unsupported_doc=%s",
            package_id,
            main_file.name if main_file else "null",
            len(attachments),
            len(unsupported_doc_files),
        )

        main_doc_id = None
        main_doc_number = None
        main_node_count = 0
        main_table_count = 0

        if main_file:
            main_info = self._parse_main(main_file, out_dir / "main")
            inventory["main_document"] = main_info
            main_doc_id = main_info.get("document_id")
            main_doc_number = main_info.get("document_number")
            main_node_count = main_info.get("node_count", 0)
            main_table_count = main_info.get("table_count", 0)
            self._warn_if_large_output(main_info.get("tree_path"), "main tree")
            self._warn_if_large_output(main_info.get("units_path"), "main units")

        for att in attachments:
            kind = classify_attachment(att)
            att_slug = attachment_slug(att)
            att_out = out_dir / "attachments" / att_slug
            parser = self._parser_for_kind(kind)
            parsed = parser.parse(
                docx_path=att,
                output_dir=att_out,
                package_id=package_id,
                document_id=main_doc_id,
                document_number=main_doc_number,
                kind=kind,
            )
            inventory["attachments"].append({
                **parsed["attachment"],
                "parsed_dir": str(att_out.relative_to(out_dir)),
                "node_count": parsed.get("node_count"),
                "table_count": parsed.get("table_count"),
                "table_row_count": parsed.get("table_row_count"),
                "form_field_count": parsed.get("form_field_count"),
                "tree_path": parsed.get("tree_path"),
                "units_path": parsed.get("units_path"),
                "unit_count": parsed.get("unit_count"),
                "tree_size_bytes": parsed.get("tree_size_bytes"),
                "units_size_bytes": parsed.get("units_size_bytes"),
            })
            self._warn_if_large_output(parsed.get("tree_path"), f"attachment tree {att.name}")
            self._warn_if_large_output(parsed.get("units_path"), f"attachment units {att.name}")

        write_json(out_dir / "package_inventory.json", inventory)

        return PackageParseResult(
            package_id=package_id,
            output_dir=out_dir,
            main_file=main_file,
            attachment_count=len(attachments),
            main_node_count=main_node_count,
            main_table_count=main_table_count,
            converted_doc_count=sum(1 for item in conversion_results if item.status in {"converted", "already_converted"}),
            failed_doc_conversion_count=sum(1 for item in conversion_results if item.status == "failed"),
        )

    def _split_main_and_attachments(self, files: List[Path]) -> Tuple[Optional[Path], List[Path]]:
        if not files:
            return None, []

        attachments = []
        main_candidates = []
        for f in files:
            name = f.stem.lower().replace("_", " ").replace("-", " ")
            if name.startswith(ATTACHMENT_PREFIXES):
                attachments.append(f)
                continue
            # Do not classify a possible main document by content here. Legal
            # titles often contain "quy chuẩn", which would look like QCVN.
            main_candidates.append(f)

        # Prefer obvious legal main file names.
        if main_candidates:
            priority = []
            for f in main_candidates:
                n = self._normalized_main_candidate_name(f)
                score = 0
                for s in ["luat", "nghi dinh", "thong tu", "quyet dinh", "nghi quyet", "bo luat"]:
                    if s in n:
                        score += 5
                package_tokens = [t for t in re.split(r"[^a-z0-9]+", strip_vietnamese_accents(f.parent.name).lower()) if t]
                name_tokens = set(re.split(r"[^a-z0-9]+", n))
                if package_tokens and all(t in name_tokens for t in package_tokens if t.isdigit()):
                    score += 3
                if f.stat().st_size > 200_000:
                    score += 1
                priority.append((score, len(f.name), f))
            priority.sort(key=lambda x: (-x[0], x[1], str(x[2])))
            main = priority[0][2]
            rest_main = [x[2] for x in priority[1:]]
            # Do not silently discard extra non-attachment files; treat as attachments unknown.
            return main, sorted(attachments + rest_main)

        # If all files are attachments, no main.
        return None, sorted(attachments)

    @staticmethod
    def _normalized_main_candidate_name(path: Path) -> str:
        name = path.stem.lower()
        name = strip_vietnamese_accents(name, keep_dd=False).lower()
        name = re.sub(r"[_\-–—]+", " ", name)
        name = re.sub(r"[^a-z0-9]+", " ", name)
        return re.sub(r"\s+", " ", name).strip()

    def _warn_if_large_output(self, path: Optional[Union[str, Path]], label: str) -> None:
        if not path:
            return
        output_path = Path(path)
        if not output_path.exists():
            return
        size = output_path.stat().st_size
        if size > WARN_OUTPUT_BYTES:
            self.logger.warning(
                "Large parser output detected | %s | size=%.2f MB | path=%s",
                label,
                size / (1024 * 1024),
                output_path,
            )

    def _parse_main(self, main_file: Path, out_dir: Path) -> Dict[str, Any]:
        if LegalBodyParser is None or ParserConfig is None:
            raise RuntimeError("LegalBodyParser/ParserConfig not importable. Keep package_parser inside your legal_parser package.")

        tmp_base = ensure_dir(out_dir / "_tmp")
        parser = LegalBodyParser(ParserConfig(output_base_dir=tmp_base))
        result = parser.parse_file(main_file)

        ensure_dir(out_dir)
        if result.tree_path and Path(result.tree_path).exists():
            shutil.copy2(result.tree_path, out_dir / "tree.json")
        if result.units_path and Path(result.units_path).exists():
            shutil.copy2(result.units_path, out_dir / "units.jsonl")

        # Extract metadata from tree.
        metadata = {}
        tree_path = out_dir / "tree.json"
        units_path = out_dir / "units.jsonl"
        if tree_path.exists():
            with open(tree_path, "r", encoding="utf-8") as f:
                tree = json.load(f)
            metadata = tree.get("metadata", {})

        shutil.rmtree(tmp_base, ignore_errors=True)
        return {
            "document_id": metadata.get("document_id") or result.document_id,
            "document_number": metadata.get("document_number"),
            "document_type": metadata.get("document_type"),
            "document_title": metadata.get("document_title"),
            "source_file": str(main_file),
            "parsed_dir": "main",
            "node_count": result.node_count,
            "unit_count": result.unit_count,
            "table_count": result.table_count,
            "tree_path": str(tree_path),
            "units_path": str(units_path),
            "tree_size_bytes": tree_path.stat().st_size if tree_path.exists() else 0,
            "units_size_bytes": units_path.stat().st_size if units_path.exists() else 0,
        }

    def _parser_for_kind(self, kind: AttachmentKind):
        if kind.kind == "qcvn":
            return QCVNParser()
        if kind.kind in {"form", "appendix_form"}:
            return FormParser()
        return AppendixParser()
