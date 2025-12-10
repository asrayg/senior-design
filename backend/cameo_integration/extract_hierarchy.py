#!/usr/bin/env python3
"""
Extract hierarchical relationships from requirement IDs.
Requirement IDs like TWCAT150.3.1.2 imply a tree structure.
"""

import json
from pathlib import Path


def extract_hierarchy_from_ids(json_file: str, output_file: str = None):
    """
    Infer parent-child relationships from hierarchical requirement IDs.
    Example: TWCAT150.3.1 is parent of TWCAT150.3.1.1
    """
    print(f"\n{'='*70}")
    print("EXTRACTING HIERARCHICAL RELATIONSHIPS FROM IDs")
    print(f"{'='*70}\n")
    
    # Load requirements
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    nodes = data.get('nodes', {})
    relationships_added = 0
    
    print(f"Processing {len(nodes)} requirements...\n")
    
    # For each requirement, find its parent and children
    for req_id in nodes.keys():
        # Skip non-hierarchical IDs (no dots)
        if '.' not in req_id:
            continue
        
        # Find parent (everything before the last dot)
        parts = req_id.rsplit('.', 1)
        if len(parts) == 2:
            parent_id = parts[0]
            
            # If parent exists, add relationship
            if parent_id in nodes:
                # Child derives from parent
                if parent_id not in nodes[req_id]['incoming']:
                    nodes[req_id]['incoming'].append(parent_id)
                    relationships_added += 1
                    print(f"  {req_id} ← derives from ← {parent_id}")
                
                # Parent has child
                if req_id not in nodes[parent_id]['outgoing']:
                    nodes[parent_id]['outgoing'].append(req_id)
    
    # Save updated data
    if output_file is None:
        output_file = json_file.replace('.json', '_with_hierarchy.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"✓ Added {relationships_added} hierarchical relationships")
    print(f"✓ Saved to: {output_file}")
    print(f"{'='*70}\n")
    
    # Print statistics
    with_incoming = sum(1 for n in nodes.values() if n.get('incoming'))
    with_outgoing = sum(1 for n in nodes.values() if n.get('outgoing'))
    total_incoming = sum(len(n.get('incoming', [])) for n in nodes.values())
    total_outgoing = sum(len(n.get('outgoing', [])) for n in nodes.values())
    
    print("Updated Statistics:")
    print(f"  Requirements with incoming relationships: {with_incoming}/{len(nodes)}")
    print(f"  Requirements with outgoing relationships: {with_outgoing}/{len(nodes)}")
    print(f"  Total incoming links: {total_incoming}")
    print(f"  Total outgoing links: {total_outgoing}")
    
    # Find root requirements (no parents)
    roots = [req_id for req_id, req_data in nodes.items() 
             if not req_data.get('incoming')]
    print(f"\nRoot requirements (no parents): {len(roots)}")
    for root in roots[:5]:
        print(f"  - {root}: {nodes[root]['name']}")
    if len(roots) > 5:
        print(f"  ... and {len(roots) - 5} more")
    
    return output_file


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Extract hierarchical relationships from requirement IDs'
    )
    parser.add_argument('json_file', help='Requirements JSON file')
    parser.add_argument('--output', help='Output file (default: adds _with_hierarchy suffix)')
    
    args = parser.parse_args()
    
    extract_hierarchy_from_ids(args.json_file, args.output)

