#!/usr/bin/env python3
"""
Validate and enrich requirement data quality.
"""

import json
from pathlib import Path
from typing import Dict, List


class RequirementValidator:
    """Validate and analyze requirement data quality."""
    
    def __init__(self, json_file: str):
        self.json_file = Path(json_file)
        with open(json_file, 'r') as f:
            self.data = json.load(f)
        self.nodes = self.data.get('nodes', {})
        
        self.issues = []
        self.stats = {
            'total': len(self.nodes),
            'with_text': 0,
            'with_relationships': 0,
            'by_type': {},
            'by_source': {}
        }
    
    def validate(self):
        """Run all validations."""
        print(f"\n{'='*70}")
        print(f"VALIDATING: {self.json_file.name}")
        print(f"{'='*70}\n")
        
        print(f"Total requirements: {self.stats['total']}\n")
        
        for req_id, req_data in self.nodes.items():
            self._validate_requirement(req_id, req_data)
        
        self._print_statistics()
        self._print_issues()
    
    def _validate_requirement(self, req_id: str, req_data: Dict):
        """Validate a single requirement."""
        # Check for text
        text = req_data.get('text', '')
        if text and text != 'No text specified':
            self.stats['with_text'] += 1
        else:
            self.issues.append({
                'req_id': req_id,
                'severity': 'warning',
                'message': 'Missing requirement text'
            })
        
        # Check for relationships
        incoming = req_data.get('incoming', [])
        outgoing = req_data.get('outgoing', [])
        if incoming or outgoing:
            self.stats['with_relationships'] += 1
        
        # Count by type
        req_type = req_data.get('node_type', 'Unknown')
        self.stats['by_type'][req_type] = self.stats['by_type'].get(req_type, 0) + 1
        
        # Count by source file
        source = req_data.get('source_file', 'Unknown')
        self.stats['by_source'][source] = self.stats['by_source'].get(source, 0) + 1
        
        # Check for missing names
        name = req_data.get('name', '')
        if not name:
            self.issues.append({
                'req_id': req_id,
                'severity': 'error',
                'message': 'Missing requirement name'
            })
    
    def _print_statistics(self):
        """Print validation statistics."""
        print("STATISTICS:")
        print("-" * 70)
        total = self.stats['total']
        with_text = self.stats['with_text']
        with_rels = self.stats['with_relationships']
        
        print(f"Requirements with text: {with_text}/{total} "
              f"({100*with_text/total if total > 0 else 0:.1f}%)")
        print(f"Requirements with relationships: {with_rels}/{total} "
              f"({100*with_rels/total if total > 0 else 0:.1f}%)")
        
        print("\nBy Type:")
        for req_type, count in sorted(self.stats['by_type'].items()):
            print(f"  {req_type:<40} {count:>3}")
        
        print("\nBy Source File:")
        for source, count in sorted(self.stats['by_source'].items()):
            print(f"  {source:<50} {count:>3}")
    
    def _print_issues(self):
        """Print validation issues."""
        if not self.issues:
            print(f"\n✓ No validation issues found!\n")
            return
        
        print(f"\n{'='*70}")
        print(f"ISSUES FOUND: {len(self.issues)}")
        print(f"{'='*70}\n")
        
        errors = [i for i in self.issues if i['severity'] == 'error']
        warnings = [i for i in self.issues if i['severity'] == 'warning']
        
        if errors:
            print(f"ERRORS ({len(errors)}):")
            for issue in errors[:10]:
                print(f"  ❌ {issue['req_id']}: {issue['message']}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
        
        if warnings:
            print(f"\nWARNINGS ({len(warnings)}):")
            for issue in warnings[:10]:
                print(f"  ⚠️  {issue['req_id']}: {issue['message']}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")
        
        print()
    
    def export_report(self, output_file: str = None):
        """Export validation report to JSON."""
        if output_file is None:
            output_file = str(self.json_file.parent / 
                            f"{self.json_file.stem}_validation_report.json")
        
        report = {
            'source_file': str(self.json_file),
            'statistics': self.stats,
            'issues': self.issues
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✓ Validation report saved to: {output_file}\n")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate requirement JSON files')
    parser.add_argument('json_file', help='Requirements JSON file to validate')
    parser.add_argument('--export-report', action='store_true',
                       help='Export validation report to JSON')
    
    args = parser.parse_args()
    
    validator = RequirementValidator(args.json_file)
    validator.validate()
    
    if args.export_report:
        validator.export_report()


if __name__ == "__main__":
    main()

