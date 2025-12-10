#!/usr/bin/env python3
"""
Batch processor and analyzer for Cameo .mdzip files.

Exports a requirement_connectivity.json with a structure:
{
  "nodes": {
    "<req_id>": {
      "name": "<requirement name>",
      "node_type": "<node type>",
      "text": "<requirement text>",
      "xmi_id": "<xmi_id>",
      "incoming": ["<req_id>", ...],
      "outgoing": ["<req_id>", ...],
      "properties": {},
      "source_file": "<source file>"
    },
    ...
  }
}
"""

import os
from pathlib import Path
from cameo_integration.cameo_analyzer import CameoAnalyzer
from typing import Dict, List

class CameoProcessor:
    def __init__(self, input_dir: str, output_dir: str = "cameo_output"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: Dict[str, Dict] = {}

    def process_all_files(self) -> Dict:
        mdzip_files = list(self.input_dir.glob("*.mdzip"))
        print(f"\n{'='*70}")
        print(f"PROCESSING: Found {len(mdzip_files)} Cameo files at 02:27 PM CDT on Tuesday, October 14, 2025")
        print(f"{'='*70}\n")

        for idx, mdzip_file in enumerate(mdzip_files, 1):
            print(f"\n[{idx}/{len(mdzip_files)}] Processing: {mdzip_file.name}")
            try:
                analyzer = CameoAnalyzer(str(mdzip_file))
                analyzer.extract_and_parse()
                output_filename = f"{mdzip_file.stem}_connectivity.json"
                output_path = self.output_dir / output_filename
                analyzer.export_connectivity_json(str(output_path))
                self.results[mdzip_file.stem] = {"output_file": str(output_path)}
                print(f"✓ Processed {mdzip_file.name} at 02:27 PM CDT on Tuesday, October 14, 2025")
            except Exception as e:
                print(f"❌ ERROR processing {mdzip_file.name}: {e} at 02:27 PM CDT on Tuesday, October 14, 2025")

        return self.results

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Process Cameo .mdzip files')
    parser.add_argument('--input-dir', default='.', help='Directory with .mdzip files')
    parser.add_argument('--output-dir', default='cameo_output', help='Output directory')
    args = parser.parse_args()

    processor = CameoProcessor(args.input_dir, args.output_dir)
    processor.process_all_files()

if __name__ == "__main__":
    main()