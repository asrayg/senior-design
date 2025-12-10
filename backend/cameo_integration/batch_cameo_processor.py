#!/usr/bin/env python3
"""
Batch processor for multiple Cameo .mdzip files.
Analyzes all files in a directory and exports to JSON.
"""

import json
from pathlib import Path
from cameo_analyzer import CameoAnalyzer
from typing import List, Dict
import time


class CameoBatchProcessor:
    """Process multiple Cameo files and aggregate results."""
    
    def __init__(self, input_dir: str, output_dir: str = "output"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.results: Dict[str, Dict] = {}
        self.summary: Dict = {
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "total_requirements": 0,
            "files": []
        }
    
    def process_all_files(self) -> Dict:
        """Process all .mdzip files in the input directory."""
        mdzip_files = list(self.input_dir.glob("*.mdzip"))
        
        print(f"\n{'='*70}")
        print(f"BATCH PROCESSING: Found {len(mdzip_files)} Cameo files")
        print(f"{'='*70}\n")
        
        self.summary["total_files"] = len(mdzip_files)
        
        for idx, mdzip_file in enumerate(mdzip_files, 1):
            print(f"\n[{idx}/{len(mdzip_files)}] Processing: {mdzip_file.name}")
            print("-" * 70)
            
            try:
                result = self._process_single_file(mdzip_file)
                self.results[mdzip_file.stem] = result
                self.summary["successful"] += 1
                self.summary["total_requirements"] += result["requirement_count"]
                
                self.summary["files"].append({
                    "filename": mdzip_file.name,
                    "status": "success",
                    "requirements": result["requirement_count"],
                    "output_file": result["output_file"]
                })
                
            except Exception as e:
                print(f"❌ ERROR processing {mdzip_file.name}: {e}")
                self.summary["failed"] += 1
                self.summary["files"].append({
                    "filename": mdzip_file.name,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Save summary
        self._save_summary()
        self._print_summary()
        
        return self.summary
    
    def _process_single_file(self, mdzip_file: Path) -> Dict:
        """Process a single .mdzip file."""
        analyzer = CameoAnalyzer(str(mdzip_file))
        analyzer.extract_and_parse()
        
        # Export to JSON
        output_filename = f"{mdzip_file.stem}_requirements.json"
        output_path = self.output_dir / output_filename
        analyzer.export_to_json(str(output_path))
        
        return {
            "requirement_count": len(analyzer.requirements),
            "element_count": len(analyzer.elements),
            "output_file": str(output_path),
            "requirements": {
                req_id: {
                    "name": req.name,
                    "type": req.req_type,
                    "has_text": bool(req.text and req.text != "No text specified"),
                    "relationship_count": (
                        len(req.derives_from) + len(req.refines) + 
                        len(req.satisfies) + len(req.verifies) + len(req.traces_to)
                    )
                }
                for req_id, req in analyzer.requirements.items()
            }
        }
    
    def _save_summary(self):
        """Save processing summary to JSON."""
        summary_file = self.output_dir / "batch_processing_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Summary saved to: {summary_file}")
    
    def _print_summary(self):
        """Print processing summary."""
        print(f"\n{'='*70}")
        print("BATCH PROCESSING SUMMARY")
        print(f"{'='*70}")
        print(f"Total files processed: {self.summary['total_files']}")
        print(f"Successful: {self.summary['successful']}")
        print(f"Failed: {self.summary['failed']}")
        print(f"Total requirements extracted: {self.summary['total_requirements']}")
        print(f"\nDetailed results:")
        print("-" * 70)
        
        for file_info in self.summary["files"]:
            status_icon = "✓" if file_info["status"] == "success" else "❌"
            print(f"{status_icon} {file_info['filename']:<50}", end="")
            
            if file_info["status"] == "success":
                print(f" {file_info['requirements']:>3} requirements")
            else:
                print(f" FAILED: {file_info.get('error', 'Unknown error')}")
        
        print(f"{'='*70}\n")
    
    def merge_all_requirements(self, output_file: str = "all_requirements.json"):
        """Merge all requirements from all files into a single JSON."""
        merged = {"nodes": {}}
        
        for file_stem, result in self.results.items():
            json_file = Path(result["output_file"])
            
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    nodes = data.get("nodes", {})
                    
                    # Add source file to each requirement
                    for req_id, req_data in nodes.items():
                        req_data["source_file"] = file_stem
                        merged["nodes"][req_id] = req_data
        
        output_path = self.output_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Merged {len(merged['nodes'])} requirements into: {output_path}")
        return output_path


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Batch process multiple Cameo .mdzip files'
    )
    parser.add_argument(
        '--input-dir',
        default='.',
        help='Directory containing .mdzip files (default: current directory)'
    )
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory for JSON files (default: ./output)'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge all requirements into a single JSON file'
    )
    
    args = parser.parse_args()
    
    # Create processor
    processor = CameoBatchProcessor(args.input_dir, args.output_dir)
    
    # Process all files
    start_time = time.time()
    processor.process_all_files()
    elapsed = time.time() - start_time
    
    print(f"⏱️  Total processing time: {elapsed:.2f} seconds\n")
    
    # Optionally merge all requirements
    if args.merge:
        print("\nMerging all requirements into single file...")
        processor.merge_all_requirements()


if __name__ == "__main__":
    main()

