#!/usr/bin/env python3
"""
Simulink Block Connectivity Analyzer

This script analyzes Simulink model files to extract block connectivity information
and create visual representations of how blocks connect to each other.
"""
import xml.etree.ElementTree as ET
import json
import re
import zipfile
import tempfile
import shutil
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    """Represents a Simulink block with its properties."""
    sid: str
    name: str
    block_type: str
    position: Tuple[int, int, int, int]  # [x, y, width, height]
    properties: Dict[str, str]
    parent_system: str = ""  # The system file this block belongs to
    input_ports: int = 0
    output_ports: int = 0


@dataclass
class Connection:
    """Represents a connection between blocks."""
    source_block: str
    source_port: int
    dest_block: str
    dest_port: int
    signal_name: Optional[str] = None
    branches: List[Tuple[str, int]] = None  # For branched signals


@dataclass
class CodeMapping:
    """Represents a mapping between generated C code and Simulink node."""
    file_path: str
    line_number: int
    block_path: str  # e.g., '<Root>/F1' or '<S1>/Sum'
    block_name: str  # e.g., 'F1' or 'Sum'
    code_line: str   # The actual line of code


class SimulinkAnalyzer:
    """Analyzes Simulink model files to extract block connectivity."""
    
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.blocks: Dict[str, Block] = {}
        self.connections: List[Connection] = []
        self.system_files = []
        
    def load_model(self):
        """Load and parse all relevant Simulink model files."""
        print(f"Loading Simulink model from: {self.model_path}")
        
        # Find all system XML files
        systems_dir = self.model_path / "systems"
        if systems_dir.exists():
            for xml_file in systems_dir.glob("*.xml"):
                self.system_files.append(xml_file)
        
        # Parse main blockdiagram.xml
        blockdiagram_file = self.model_path / "blockdiagram.xml"
        if blockdiagram_file.exists():
            self._parse_blockdiagram(blockdiagram_file)
        
        # Parse system files
        for system_file in self.system_files:
            self._parse_system_file(system_file)
    
    def _parse_blockdiagram(self, file_path: Path):
        """Parse the main blockdiagram.xml file."""
        print(f"Parsing blockdiagram: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Extract model information
        model_info = {}
        for model in root.findall('.//Model'):
            for prop in model.findall('.//P'):
                name = prop.get('Name')
                if name:
                    model_info[name] = prop.text
        
    
    def _parse_system_file(self, file_path: Path):
        """Parse a system XML file to extract blocks and connections."""
        print(f"Parsing system file: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Get system name from file (e.g., "system_root" from "system_root.xml")
        system_name = file_path.stem
        
        # Extract blocks
        for block in root.findall('.//Block'):
            self._parse_block(block, system_name)
        
        # Extract connections
        for line in root.findall('.//Line'):
            self._parse_connection(line)
    
    def _parse_block(self, block_element, system_name: str = ""):
        """Parse a block element and create a Block object."""
        sid = block_element.get('SID')
        name = block_element.get('Name', '')
        block_type = block_element.get('BlockType', '')
        
        # Extract position
        position_elem = block_element.find('.//P[@Name="Position"]')
        position = (0, 0, 100, 50)  # Default position
        if position_elem is not None and position_elem.text:
            pos_str = position_elem.text.strip('[]')
            try:
                position = tuple(map(int, pos_str.split(', ')))
            except ValueError:
                pass
        
        # Extract properties
        properties = {}
        for prop in block_element.findall('.//P'):
            prop_name = prop.get('Name')
            if prop_name and prop_name not in ['Position', 'ZOrder']:
                properties[prop_name] = prop.text or ''
        
        # Extract port counts
        port_counts = block_element.find('.//PortCounts')
        input_ports = 0
        output_ports = 0
        if port_counts is not None:
            input_ports = int(port_counts.get('in', 0))
            output_ports = int(port_counts.get('out', 0))
        
        block = Block(
            sid=sid,
            name=name,
            block_type=block_type,
            position=position,
            properties=properties,
            parent_system=system_name,
            input_ports=input_ports,
            output_ports=output_ports
        )
        
        self.blocks[sid] = block
        print(f"  Found block: {name} ({block_type}) - SID: {sid} [system: {system_name}]")
    
    def _parse_connection(self, line_element):
        """Parse a line element and create Connection objects."""
        # Use direct child search (P[...]) NOT descendant search (.//P[...])
        # to avoid incorrectly finding Dst elements inside Branch elements
        src_elem = line_element.find('P[@Name="Src"]')
        dst_elem = line_element.find('P[@Name="Dst"]')
        name_elem = line_element.find('P[@Name="Name"]')
        
        if src_elem is None:
            return
        
        src = src_elem.text
        signal_name = name_elem.text if name_elem is not None else None
        
        # Parse source and destination
        # Regular ports look like "<sid>#out:1" or "<sid>#in:2"
        # State ports (e.g., Integrator state) look like "<sid>#state" and
        # do not have a numbered port. We normalize these to port 0.
        def parse_endpoint(endpoint: str):
            if endpoint is None:
                return None
            regular_match = re.match(r'(\d+)#(out|in):(\d+)', endpoint)
            if regular_match:
                sid, port_type, port_num = regular_match.groups()
                return sid, port_type, int(port_num)
            state_match = re.match(r'(\d+)#state', endpoint)
            if state_match:
                sid = state_match.group(1)
                return sid, 'state', 0
            return None

        src_parsed = parse_endpoint(src)
        if not src_parsed:
            return
            
        src_sid, src_type, src_port = src_parsed
        
        # Check for branches (use direct child search)
        branches = line_element.findall('Branch')
        
        # If Line has a direct Dst, create the main connection
        if dst_elem is not None:
            dst_parsed = parse_endpoint(dst_elem.text)
            if dst_parsed:
                dst_sid, dst_type, dst_port = dst_parsed
                connection = Connection(
                    source_block=src_sid,
                    source_port=int(src_port),
                    dest_block=dst_sid,
                    dest_port=int(dst_port),
                    signal_name=signal_name
                )
                self.connections.append(connection)
                print(f"  Found connection: {src} -> {dst_elem.text} ({signal_name or 'unnamed'})")
        
        # Process branches - each branch creates its own connection from the same source
        for branch in branches:
            branch_dst = branch.find('P[@Name="Dst"]')
            if branch_dst is not None:
                branch_parsed = parse_endpoint(branch_dst.text)
                if branch_parsed:
                    branch_sid, _, branch_port = branch_parsed
                    branch_connection = Connection(
                        source_block=src_sid,
                        source_port=int(src_port),
                        dest_block=branch_sid,
                        dest_port=int(branch_port),
                        signal_name=signal_name
                    )
                    self.connections.append(branch_connection)
                    print(f"  Found branch connection: {src} -> {branch_dst.text} ({signal_name or 'unnamed'})")
    
    
    
    
    
    def export_to_json(self, output_file: str = "block_connectivity.json"):
        """Export simplified node graph: name, node_type, incoming, outgoing."""
        # Get model name from the model path (the .slx file name)
        # The model directory structure is typically: ModelName/simulink/blockdiagram.xml
        # So if the current directory is "simulink", use the parent directory name
        if self.model_path.name.lower() == "simulink":
            model_name = self.model_path.parent.name
        else:
            model_name = self.model_path.name
        
        # Initialize node map with required fields only
        nodes: Dict[str, Dict[str, object]] = {}
        
        # Add all blocks (no parent model node - just the actual blocks)
        for sid, block in self.blocks.items():
            nodes[sid] = {
                "name": block.name,
                "node_type": block.block_type,
                "parent_system": block.parent_system,
                "model_name": model_name,  # Store model name as property instead
                "incoming": [],
                "outgoing": []
            }

        # Populate incoming/outgoing using actual signal connections only
        for conn in self.connections:
            src = conn.source_block
            dst = conn.dest_block
            if src in nodes and dst in nodes:
                nodes[src]["outgoing"].append(dst)
                nodes[dst]["incoming"].append(src)

        with open(output_file, 'w') as f:
            json.dump({"nodes": nodes}, f, indent=2)
        print(f"Data exported to: {output_file}")


class SlxcAnalyzer:
    """Analyzes Simulink code generation files (.slxc) to extract code-to-model mappings."""
    
    # Pattern to match block references in comments like '<Root>/F1' or '<S1>/Sum'
    BLOCK_REF_PATTERN = re.compile(r"'<([^>]+)>/([^']+)'")
    
    def __init__(self, slxc_path: str):
        self.slxc_path = Path(slxc_path)
        self.code_mappings: List[CodeMapping] = []
        self.c_files: Dict[str, str] = {}  # filename -> content
        self._temp_dir: Optional[Path] = None
        self._keep_extracted = False
    
    @staticmethod
    def get_extracted_dir(slxc_path: str) -> Path:
        """Get the path where extracted files would be stored."""
        slxc_path = Path(slxc_path)
        return slxc_path.parent / f"{slxc_path.stem}_extracted"
    
    @staticmethod
    def load_from_extracted(extracted_dir: str) -> Dict[str, str]:
        """Load C files from an already-extracted directory.
        
        Args:
            extracted_dir: Path to the extracted slxc directory
            
        Returns:
            Dict mapping file paths to their content
        """
        extracted_path = Path(extracted_dir)
        if not extracted_path.exists():
            return {}
        
        c_files = {}
        for c_file in extracted_path.rglob("*.c"):
            relative_path = c_file.relative_to(extracted_path)
            try:
                c_files[str(relative_path)] = c_file.read_text()
            except Exception as e:
                print(f"Error reading {c_file}: {e}")
        
        return c_files
        
    def load_slxc(self, keep_extracted: bool = False) -> bool:
        """Extract and load the .slxc file (which is a zip archive).
        
        Args:
            keep_extracted: If True, extract to a permanent directory next to the .slxc file
                           instead of a temp directory. This makes subsequent loads faster.
        """
        if not self.slxc_path.exists():
            print(f"SLXC file not found: {self.slxc_path}")
            return False
        
        self._keep_extracted = keep_extracted
        
        # Check if already extracted
        permanent_dir = self.get_extracted_dir(str(self.slxc_path))
        if permanent_dir.exists():
            print(f"Loading from existing extracted directory: {permanent_dir}")
            self.c_files = self.load_from_extracted(str(permanent_dir))
            if self.c_files:
                for path in self.c_files.keys():
                    print(f"  Found C file: {path}")
                return True
            # If no C files found, re-extract
            shutil.rmtree(permanent_dir)
            
        print(f"Loading SLXC file: {self.slxc_path}")
        
        # Choose extraction directory
        if keep_extracted:
            self._temp_dir = permanent_dir
            self._temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="slxc_"))
        
        try:
            with zipfile.ZipFile(self.slxc_path, 'r') as archive:
                archive.extractall(self._temp_dir)
            
            # Find all .c files in the extracted archive
            for c_file in self._temp_dir.rglob("*.c"):
                relative_path = c_file.relative_to(self._temp_dir)
                self.c_files[str(relative_path)] = c_file.read_text()
                print(f"  Found C file: {relative_path}")
            
            return len(self.c_files) > 0
            
        except zipfile.BadZipFile:
            print(f"Invalid zip file: {self.slxc_path}")
            return False
    
    def analyze_code_mappings(self):
        """Parse C files to extract code-to-Simulink-node mappings."""
        for file_path, content in self.c_files.items():
            self._parse_c_file(file_path, content)
        
        print(f"Found {len(self.code_mappings)} code-to-model mappings")
    
    def _parse_c_file(self, file_path: str, content: str):
        """Parse a single C file for block references in comments."""
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            # Look for block references in comments
            # Format: /* BlockType: '<Path>/Name' ... */
            matches = self.BLOCK_REF_PATTERN.findall(line)
            
            for path, name in matches:
                block_path = f"<{path}>/{name}"
                mapping = CodeMapping(
                    file_path=file_path,
                    line_number=line_num,
                    block_path=block_path,
                    block_name=name,
                    code_line=line.strip()
                )
                self.code_mappings.append(mapping)
    
    def export_to_json(self, output_file: str = "code_mappings.json"):
        """Export code mappings to JSON format."""
        mappings_data = {
            "source_file": str(self.slxc_path),
            "c_files": list(self.c_files.keys()),
            "mappings": []
        }
        
        # Group mappings by (file_path, block_path) to include file in location
        by_location: Dict[Tuple[str, str], List[Dict]] = {}
        for mapping in self.code_mappings:
            location_key = (mapping.file_path, mapping.block_path)
            if location_key not in by_location:
                by_location[location_key] = []
            by_location[location_key].append({
                "line": mapping.line_number,
                "code": mapping.code_line
            })
        
        mappings_data["mappings"] = [
            {
                "file_path": file_path,
                "block_path": block_path,
                "block_name": block_path.split('/')[-1],
                "location": f"{file_path}:{block_path}",
                "code_references": refs
            }
            for (file_path, block_path), refs in by_location.items()
        ]
        
        with open(output_file, 'w') as f:
            json.dump(mappings_data, f, indent=2)
        print(f"Code mappings exported to: {output_file}")
        
        return mappings_data
    
    def cleanup(self):
        """Remove temporary extraction directory (only if not keeping extracted)."""
        if self._temp_dir and self._temp_dir.exists() and not self._keep_extracted:
            shutil.rmtree(self._temp_dir)
            self._temp_dir = None
    
    def __del__(self):
        self.cleanup()


def main():
    """Main function to run the Simulink analyzer."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze Simulink block connectivity')
    parser.add_argument('model_path', help='Path to the Simulink model directory or .slxc file')
    parser.add_argument('--output-dir', default='.', help='Output directory for generated files')
    parser.add_argument('--slxc', action='store_true', help='Analyze a .slxc code generation file')
    
    args = parser.parse_args()
    
    # Prepare output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if args.slxc or args.model_path.endswith('.slxc'):
        # Analyze code generation file
        analyzer = SlxcAnalyzer(args.model_path)
        if analyzer.load_slxc():
            analyzer.analyze_code_mappings()
            analyzer.export_to_json(str(output_dir / "code_mappings.json"))
            analyzer.cleanup()
    else:
        # Analyze Simulink model directory
        analyzer = SimulinkAnalyzer(args.model_path)
        analyzer.load_model()
        analyzer.export_to_json(str(output_dir / "block_connectivity.json"))
    
    print(f"\nAnalysis complete! Files saved to: {output_dir}")


if __name__ == "__main__":
    main()
