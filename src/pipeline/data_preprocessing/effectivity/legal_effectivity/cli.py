
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Tuple
from .extractor import EffectivityExtractor
from .models import EffectivityConfig
from .utils import find_units_files, units_file_output_name

def main() -> None:
    ap = argparse.ArgumentParser(description="Extract minimal general/unit effectivity from parsed units.jsonl.")
    ap.add_argument("--input", "-i", required=True, help="Path to parsed folder or one units.jsonl")
    ap.add_argument("--output", "-o", default="./data/preprocessed/effectivity", help="Output base folder")
    ap.add_argument("--scan-all-units", action="store_true", help="Scan all units, not only likely final provisions")
    ap.add_argument("--min-confidence", type=float, default=0.35)
    args = ap.parse_args()

    config = EffectivityConfig(
        output_base_dir=Path(args.output),
        prefer_final_provisions=not args.scan_all_units,
        min_confidence=args.min_confidence,
    )
    extractor = EffectivityExtractor(config)
    units_files = find_units_files(args.input)
    if not units_files:
        print(f"No units.jsonl found in: {args.input}")
        return

    print(f"Found {len(units_files)} units.jsonl file(s)")
    print("-" * 60)
    success = 0
    all_general = []
    all_unit_effectivity = []
    errors: List[Tuple[str, str]] = []
    for units_path in units_files:
        try:
            effectivity = extractor.extract_from_units_file(units_path)
            success += 1
            all_general.extend(effectivity.get("general") or [])
            all_unit_effectivity.extend(effectivity.get("units") or [])
            print(
                f"OK {units_file_output_name(units_path)}: "
                f"general={len(effectivity.get('general') or [])} | units={len(effectivity.get('units') or [])}"
            )
        except Exception as e:
            errors.append((str(units_path), str(e)))
            print(f"ERROR {units_path}: {e}")

    if success:
        output_root = Path(args.output)
        output_root.mkdir(parents=True, exist_ok=True)
        general_path = output_root / "effectivity_general.json"
        units_path = output_root / "effectivity_units.json"
        general = extractor.merge_general_effectivity(all_general)
        with open(general_path, "w", encoding="utf-8") as f:
            json.dump(general, f, ensure_ascii=False, indent=2)
        with open(units_path, "w", encoding="utf-8") as f:
            json.dump(all_unit_effectivity, f, ensure_ascii=False, indent=2)
        print(f"General effectivity: {general_path}")
        print(f"Unit effectivity: {units_path}")

    print("\n" + "=" * 60)
    print(f"Done: {success}/{len(units_files)} | general={len(all_general)} | units={len(all_unit_effectivity)}")
    if errors:
        print(f"Failed: {len(errors)}")
        for path, msg in errors:
            print(f"   - {path}: {msg}")

if __name__ == "__main__":
    main()
