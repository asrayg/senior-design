#!/usr/bin/env python3
"""
Cameo/MagicDraw MDZIP Requirements Parser (Improved Filtering)
"""

import zipfile
import xml.etree.ElementTree as ET
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

@dataclass
class Requirement:
    """Represents a SysML Requirement with its properties."""
    req_id: str
    name: str
    text: str
    req_type: str
    xmi_id: str
    owner_id: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    source_file: str = "Unknown"  # Added to match JSON structure
    
    # Traceability relationships
    derives_from: List[str] = field(default_factory=list)
    refines: List[str] = field(default_factory=list)
    satisfies: List[str] = field(default_factory=list)
    verifies: List[str] = field(default_factory=list)
    traces_to: List[str] = field(default_factory=list)

class CameoAnalyzer:
    """Analyzes Cameo .mdzip files to extract requirements and relationships."""
    
    NAMESPACES = {
        'xmi': 'http://www.omg.org/spec/XMI/20131001',
        'uml': 'http://www.omg.org/spec/UML/20131001',
        'sysml': 'http://www.omg.org/spec/SysML/20150709',
        'StandardProfile': 'http://www.omg.org/spec/UML/20131001/StandardProfile'
    }
    
    def __init__(self, mdzip_path: str):
        self.mdzip_path = Path(mdzip_path)
        self.requirements: Dict[str, Requirement] = {}
        self.elements: Dict[str, Dict] = {}
        self.id_to_name: Dict[str, str] = {}
        self.stereotype_applications: Dict[str, str] = {}
        
    def extract_and_parse(self):
        """Extract the .mdzip file and parse the model file."""
        print(f"\n{'='*60}")
        print(f"Analyzing: {self.mdzip_path.name} at 02:36 PM CDT on Tuesday, October 14, 2025")
        print(f"{'='*60}\n")
        
        if not self.mdzip_path.exists():
            print(f"Error: {self.mdzip_path} not found")
            return
            
        try:
            with zipfile.ZipFile(self.mdzip_path, 'r') as zip_ref:
                model_file = 'com.nomagic.magicdraw.uml_model.model'
                
                if model_file in zip_ref.namelist():
                    print(f"Reading {model_file}...")
                    with zip_ref.open(model_file) as f:
                        content = f.read()
                        self._parse_xmi_content(content)
                else:
                    print(f"Warning: {model_file} not found in archive")
                    return
                
        except zipfile.BadZipFile as e:
            print(f"Error: Invalid .mdzip file - {e}")
            return
        except Exception as e:
            print(f"Error reading file: {e}")
            import traceback
            traceback.print_exc()
            return
        
        self._resolve_relationships()
        
        print(f"\n{'='*60}")
        print(f"Parsing Complete!")
        print(f"  Requirements found: {len(self.requirements)}")
        print(f"  Other elements found: {len(self.elements)}")
        print(f"{'='*60}\n")
    
    def _parse_xmi_content(self, content: bytes):
        """Parse XMI content from the model file."""
        try:
            root = ET.fromstring(content)
            
            print("Step 1: Collecting stereotype applications...")
            self._collect_stereotype_applications(root)
            
            print("Step 2: Collecting all elements...")
            self._collect_all_elements(root)
            
            print("Step 3: Extracting requirements...")
            self._extract_requirements(root)
            
            print("Step 4: Extracting relationships...")
            self._extract_relationships(root)
            
        except ET.ParseError as e:
            print(f"Error parsing XMI: {e}")
        except Exception as e:
            print(f"Error processing XMI: {e}")
            import traceback
            traceback.print_exc()
    
    def _collect_stereotype_applications(self, root: ET.Element):
        """Collect all stereotype applications to identify requirements."""
        for elem in root.iter():
            tag = elem.tag
            xmi_type = elem.get('{http://www.omg.org/spec/XMI/20131001}type',
                               elem.get('xmi:type', ''))
            
            if 'Requirement' in tag or 'Requirement' in xmi_type:
                base_class = (elem.get('base_Class') or 
                            elem.get('base_Element') or
                            elem.get('{http://www.omg.org/spec/UML/20131001}base_Class'))
                
                if base_class:
                    self.stereotype_applications[base_class] = 'Requirement'
                    req_id = elem.get('id', elem.get('Id'))
                    req_text = elem.get('text', elem.get('Text'))
                    source_file = elem.get('source', 'Unknown')  # Attempt to extract source_file
                    
                    if base_class not in self.elements:
                        self.elements[base_class] = {}
                    
                    if req_id:
                        self.elements[base_class]['stereotype_id'] = req_id
                    if req_text:
                        self.elements[base_class]['stereotype_text'] = req_text
                    if source_file:
                        self.elements[base_class]['source_file'] = source_file
    
    def _collect_all_elements(self, root: ET.Element):
        """Collect all elements with IDs for later reference."""
        for elem in root.iter():
            xmi_id = elem.get('{http://www.omg.org/spec/XMI/20131001}id', elem.get('xmi:id'))
            if xmi_id:
                name = elem.get('name', '')
                xmi_type = elem.get('{http://www.omg.org/spec/XMI/20131001}type', 
                                   elem.get('xmi:type', ''))
                source_file = elem.get('source', 'Unknown')  # Attempt to extract source_file
                
                self.id_to_name[xmi_id] = name if name else xmi_id
                
                if xmi_id not in self.elements:
                    self.elements[xmi_id] = {}
                    
                self.elements[xmi_id].update({
                    'name': name,
                    'type': xmi_type,
                    'element': elem,
                    'source_file': source_file
                })
    
    def _extract_requirements(self, root: ET.Element):
        """Extract only real SysML Requirements (with stereotype)."""
        req_count = 0
        
        for xmi_id, stereotype in self.stereotype_applications.items():
            if stereotype == 'Requirement' and xmi_id in self.elements:
                elem_data = self.elements[xmi_id]
                elem = elem_data.get('element')
                
                if elem is not None:
                    name = elem_data.get('name', 'Unnamed Requirement')
                    if self._is_valid_requirement_name(name):
                        req = self._parse_requirement_element(elem, elem_data)
                        if req:
                            self.requirements[req.xmi_id] = req
                            req_count += 1
                            print(f"  [{req_count}] {req.req_id}: {req.name}")
        
        if req_count == 0:
            print("  No valid requirements with stereotypes found.")
            print("  This file may contain design elements rather than requirements.")
    
    def _is_valid_requirement_name(self, name: str) -> bool:
        """Check if a name looks like a real requirement (not a UI element)."""
        if not name or name == 'Unnamed Requirement':
            return False
        if len(name.strip()) <= 2:
            return False
        if name.strip().isdigit():
            return False
        if name.strip() in ['+', '-', '*', '/', '=', '.', ',']:
            return False
        if name.strip().replace(' ', '').isdigit():
            return False
        return True
    
    def _parse_requirement_element(self, elem: ET.Element, elem_data: Dict) -> Optional[Requirement]:
        """Parse a single requirement element."""
        xmi_id = elem.get('{http://www.omg.org/spec/XMI/20131001}id', 
                         elem.get('xmi:id', ''))
        if not xmi_id:
            return None
        
        name = elem_data.get('name', 'Unnamed Requirement')
        text = elem_data.get('stereotype_text', '')
        if not text:
            text = self._extract_requirement_text(elem)
        
        req_id = elem_data.get('stereotype_id', '')
        if not req_id:
            req_id = self._extract_requirement_id(elem, xmi_id, name)
        
        req_type = self._determine_requirement_type(elem, name)
        properties = self._extract_properties(elem)
        owner_id = elem.get('owner')
        source_file = elem_data.get('source_file', 'Unknown')
        
        return Requirement(
            req_id=req_id,
            name=name,
            text=text,
            req_type=req_type,
            xmi_id=xmi_id,
            owner_id=owner_id,
            properties=properties,
            source_file=source_file
        )
    
    def _extract_requirement_text(self, elem: ET.Element) -> str:
        """Extract requirement text from various possible locations."""
        for attr in ['text', 'body', 'specification', 'Text']:
            if attr in elem.attrib:
                return elem.attrib[attr]
        for ns_prefix in ['{http://www.omg.org/spec/UML/20131001}', '']:
            for comment in elem.findall(f'.//{ns_prefix}ownedComment'):
                body = comment.get('body')
                if body:
                    return body
        return "No text specified"
    
    def _extract_requirement_id(self, elem: ET.Element, xmi_id: str, name: str) -> str:
        """Extract or generate requirement ID."""
        for attr in ['id', 'Id', 'identifier', 'ID']:
            if attr in elem.attrib:
                return elem.attrib[attr]
        if 'REQ' in name.upper() or 'R-' in name.upper():
            return name
        clean_name = ''.join(c for c in name if c.isalnum() or c in ['-', '_'])
        if clean_name:
            return f"REQ-{clean_name}"
        return f"REQ-{xmi_id[-8:]}"
    
    def _determine_requirement_type(self, elem: ET.Element, name: str) -> str:
        """Determine the type of requirement."""
        req_type = elem.get('type', elem.get('requirementType', ''))
        if req_type:
            return req_type
        name_lower = name.lower()
        if 'functional' in name_lower:
            return 'Functional'
        elif 'performance' in name_lower or 'non-functional' in name_lower:
            return 'Performance'
        elif 'interface' in name_lower:
            return 'Interface'
        elif 'design' in name_lower:
            return 'Design'
        elif 'test' in name_lower:
            return 'Test'
        elif 'system' in name_lower:
            return 'System'
        elif 'user' in name_lower:
            return 'User'
        return 'General'
    
    def _extract_properties(self, elem: ET.Element) -> Dict[str, str]:
        """Extract additional properties."""
        properties = {}
        for attr, value in elem.attrib.items():
            if not attr.startswith('{') and attr not in ['xmi:id', 'xmi:type', 'name']:
                properties[attr] = value
        return properties
    
    def _extract_relationships(self, root: ET.Element):
        """Extract traceability relationships."""
        for elem in root.iter():
            xmi_type = elem.get('{http://www.omg.org/spec/XMI/20131001}type',
                               elem.get('xmi:type', ''))
            if any(rel in xmi_type for rel in ['Dependency', 'Abstraction', 'Realization', 'Trace']):
                self._parse_relationship_element(elem, xmi_type, root)
    
    def _parse_relationship_element(self, elem: ET.Element, xmi_type: str, root: ET.Element):
        """Parse a relationship element."""
        client = elem.get('client')
        supplier = elem.get('supplier')
        
        if not client or not supplier:
            return
        if client not in self.requirements:
            return
        
        rel_type = self._determine_relationship_type(elem, xmi_type, root)
        if rel_type == 'derives':
            self.requirements[client].derives_from.append(supplier)
        elif rel_type == 'refines':
            self.requirements[client].refines.append(supplier)
        elif rel_type == 'satisfies':
            self.requirements[client].satisfies.append(supplier)
        elif rel_type == 'verifies':
            self.requirements[client].verifies.append(supplier)
        else:
            self.requirements[client].traces_to.append(supplier)
    
    def _determine_relationship_type(self, elem: ET.Element, xmi_type: str, root: ET.Element) -> str:
        """Determine the type of relationship."""
        xmi_id = elem.get('{http://www.omg.org/spec/XMI/20131001}id', elem.get('xmi:id'))
        if xmi_id and xmi_id in self.stereotype_applications:
            stereo = self.stereotype_applications[xmi_id].lower()
            if 'derive' in stereo:
                return 'derives'
            elif 'refine' in stereo:
                return 'refines'
            elif 'satisfy' in stereo:
                return 'satisfies'
            elif 'verify' in stereo:
                return 'verifies'
        name = elem.get('name', '').lower()
        if 'derive' in name:
            return 'derives'
        elif 'refine' in name:
            return 'refines'
        elif 'satisfy' in name:
            return 'satisfies'
        elif 'verify' in name:
            return 'verifies'
        return 'traces'
    
    def _resolve_relationships(self):
        """Resolve XMI IDs to requirement IDs in relationships."""
        for req in self.requirements.values():
            # Map XMI IDs to req_ids using requirements dict
            req.derives_from = [r.xmi_id for r in self.requirements.values() if r.xmi_id in req.derives_from]
            req.refines = [r.xmi_id for r in self.requirements.values() if r.xmi_id in req.refines]
            req.satisfies = [r.xmi_id for r in self.requirements.values() if r.xmi_id in req.satisfies]
            req.verifies = [r.xmi_id for r in self.requirements.values() if r.xmi_id in req.verifies]
            req.traces_to = [r.xmi_id for r in self.requirements.values() if r.xmi_id in req.traces_to]
    
    def export_to_json(self, output_file: str = "cameo_requirements.json"):
        """Export requirements in Neo4j-compatible format."""
        nodes = {}
        for xmi_id, req in self.requirements.items():
            outgoing = req.refines + req.satisfies + req.verifies + req.traces_to
            incoming = req.derives_from
            
            nodes[req.req_id] = {
                "name": req.name,
                "node_type": f"Requirement_{req.req_type}",
                "text": req.text,
                "xmi_id": req.xmi_id,
                "incoming": incoming,
                "outgoing": outgoing,
                "properties": req.properties
            }
        
        output_data = {"nodes": nodes}
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Exported to: {output_file}")
        return output_file
    
    def export_connectivity_json(self, output_file: str = "requirement_connectivity.json"):
        """Export requirements in a connectivity format."""
        nodes = {}
        for req_id, req in self.requirements.items():
            outgoing = req.refines + req.satisfies + req.verifies + req.traces_to
            incoming = req.derives_from
            nodes[req.req_id] = {
                "name": req.name,
                "node_type": f"Requirement_{req.req_type}",
                "text": req.text,
                "xmi_id": req.xmi_id,
                "incoming": incoming,
                "outgoing": outgoing,
                "properties": req.properties,
                "source_file": req.source_file
            }
        
        output_data = {"nodes": nodes}
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Exported connectivity to: {output_file} at 02:36 PM CDT on Tuesday, October 14, 2025")
        return output_file
    
    def print_summary(self):
        """Print a summary of extracted requirements."""
        if not self.requirements:
            print("\n⚠ No requirements found in this model.")
            print("This file may contain design elements, UI models, or other non-requirement content.")
            return
        
        print(f"\n{'='*60}")
        print("REQUIREMENTS SUMMARY")
        print(f"{'='*60}\n")
        
        for req in self.requirements.values():
            print(f"ID: {req.req_id}")
            print(f"Name: {req.name}")
            print(f"Type: {req.req_type}")
            text_preview = req.text[:80] + "..." if len(req.text) > 80 else req.text
            print(f"Text: {text_preview}")
            print(f"Source: {req.source_file}")
            if req.derives_from:
                print(f"  ← Derives From: {', '.join(req.derives_from[:3])}")
            if req.refines:
                print(f"  → Refines: {', '.join(req.refines[:3])}")
            if req.satisfies:
                print(f"  ✓ Satisfies: {', '.join(req.satisfies[:3])}")
            if req.verifies:
                print(f"  ✓ Verifies: {', '.join(req.verifies[:3])}")
            print()

def main():
    """Main function to run the Cameo analyzer."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze Cameo .mdzip files for SysML requirements')
    parser.add_argument('mdzip_path', help='Path to the .mdzip file')
    parser.add_argument('--output-dir', default='.', help='Output directory for JSON files')
    parser.add_argument('--summary', action='store_true', help='Print detailed summary')
    
    args = parser.parse_args()
    
    analyzer = CameoAnalyzer(args.mdzip_path)
    analyzer.extract_and_parse()
    
    if args.summary or len(analyzer.requirements) > 0:
        analyzer.print_summary()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    mdzip_name = Path(args.mdzip_path).stem
    output_file = output_dir / f"{mdzip_name}_requirements.json"
    analyzer.export_to_json(str(output_file))
    
    # Export connectivity JSON as well
    connectivity_file = output_dir / f"{mdzip_name}_connectivity.json"
    analyzer.export_connectivity_json(str(connectivity_file))
    
    print(f"\n✓ Analysis complete at 02:36 PM CDT on Tuesday, October 14, 2025")

if __name__ == "__main__":
    main()