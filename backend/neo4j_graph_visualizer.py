#!/usr/bin/env python3
"""
Neo4j Graph Visualizer

This script pulls all data from the Neo4j database and creates a comprehensive
graph visualization showing both Simulink blocks and requirements with their
relationships.

Features:
- Pulls all nodes and relationships from Neo4j
- Creates interactive graph visualization using NetworkX and matplotlib
- Supports different node types (Blocks, Requirements) with distinct styling
- Shows relationship types with different edge colors/styles
- Exports graph as PNG/SVG and interactive HTML

Usage:
    python neo4j_graph_visualizer.py [--output-dir OUTPUT_DIR] [--format FORMAT]
    
Options:
    --output-dir    Directory to save output files (default: ./graph_output)
    --format        Output format: png, svg, html, all (default: all)
    --interactive   Show interactive matplotlib window
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import argparse

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from neo4j import GraphDatabase, Driver
import numpy as np

# Import configuration
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class Neo4jGraphVisualizer:
    """Visualizes Neo4j graph data using NetworkX and matplotlib."""
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize the visualizer with Neo4j connection details."""
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[Driver] = None
        self.graph = nx.Graph()
        self.node_data = {}
        self.edge_data = {}
        
    def connect(self):
        """Connect to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1").single()
            print(f"Connected to Neo4j at {self.uri}")
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
    
    def pull_all_data(self):
        """Pull all nodes and relationships from Neo4j."""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        
        print("Pulling all data from Neo4j...")
        
        with self.driver.session() as session:
            # Get all nodes with their labels and properties
            nodes_query = """
            MATCH (n)
            RETURN n, labels(n) as node_labels
            """
            
            nodes_result = session.run(nodes_query)
            node_count = 0
            
            for record in nodes_result:
                node = record['n']
                labels = record['node_labels']
                
                # Extract node properties
                node_id = str(node.element_id)
                node_props = dict(node)
                
                # Determine node type from labels
                node_type = labels[0] if labels else 'Unknown'
                
                # Add to NetworkX graph (avoid node_type conflict)
                node_attrs = {**node_props, 'node_type': node_type}
                self.graph.add_node(node_id, **node_attrs)
                self.node_data[node_id] = {
                    'properties': node_props,
                    'type': node_type,
                    'labels': labels
                }
                node_count += 1
            
            print(f"Found {node_count} nodes")
            
            # Get all relationships
            rels_query = """
            MATCH (a)-[r]->(b)
            RETURN a, r, b, type(r) as rel_type
            """
            
            rels_result = session.run(rels_query)
            rel_count = 0
            
            for record in rels_result:
                source = str(record['a'].element_id)
                target = str(record['b'].element_id)
                rel_type = record['rel_type']
                rel_props = dict(record['r'])
                
                # Add edge to NetworkX graph
                edge_attrs = {**rel_props, 'rel_type': rel_type}
                self.graph.add_edge(source, target, **edge_attrs)
                
                self.edge_data[(source, target)] = {
                    'type': rel_type,
                    'properties': rel_props
                }
                rel_count += 1
            
            print(f"Found {rel_count} relationships")
            
            # Print summary
            self._print_data_summary()
    
    def _print_data_summary(self):
        """Print a summary of the loaded data."""
        print("\n=== Data Summary ===")
        
        # Node type summary
        node_types = {}
        for node_id, data in self.node_data.items():
            node_type = data['type']
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        print("Node types:")
        for node_type, count in node_types.items():
            print(f"  {node_type}: {count}")
        
        # Relationship type summary
        rel_types = {}
        for (source, target), data in self.edge_data.items():
            rel_type = data['type']
            rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
        
        print("\nRelationship types:")
        for rel_type, count in rel_types.items():
            print(f"  {rel_type}: {count}")
        
        print(f"\nTotal nodes: {self.graph.number_of_nodes()}")
        print(f"Total edges: {self.graph.number_of_edges()}")
    
    def create_visualization(self, output_dir: str = "./graph_output", 
                           format: str = "all", interactive: bool = False):
        """Create graph visualization."""
        if not self.graph.nodes():
            print("No data to visualize. Make sure to call pull_all_data() first.")
            return
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print(f"Creating visualization in {output_path}...")
        
        # Create static visualization
        if format in ["png", "svg", "all"]:
            self._create_static_visualization(output_path, format)
        
        # Create interactive HTML visualization
        if format in ["html", "all"]:
            self._create_interactive_visualization(output_path)
        
        # Show interactive matplotlib window
        if interactive:
            self._show_interactive_window()
    
    def _create_static_visualization(self, output_path: Path, format: str):
        """Create static graph visualization using matplotlib."""
        print("Creating static visualization...")
        
        # Set up the plot
        plt.figure(figsize=(20, 16))
        
        # Use spring layout for better node distribution
        pos = nx.spring_layout(self.graph, k=3, iterations=50)
        
        # Define colors and styles for different node types
        node_colors = {
            'Block': '#FF6B6B',      # Red for Simulink blocks
            'Requirement': '#4ECDC4', # Teal for requirements
            'Unknown': '#95A5A6'     # Gray for unknown types
        }
        
        edge_colors = {
            'CONNECTS_TO': '#E74C3C',    # Red for block connections
            'DERIVES_FROM': '#3498DB',   # Blue for derivation
            'TRACES_TO': '#2ECC71',      # Green for traceability
            'REFINES': '#F39C12',        # Orange for refinement
            'SATISFIES': '#9B59B6',      # Purple for satisfaction
            'VERIFIES': '#1ABC9C'        # Cyan for verification
        }
        
        # Draw nodes by type
        for node_type, color in node_colors.items():
            nodes_of_type = [node for node, data in self.graph.nodes(data=True) 
                           if data.get('node_type') == node_type]
            if nodes_of_type:
                nx.draw_networkx_nodes(self.graph, pos, 
                                     nodelist=nodes_of_type,
                                     node_color=color,
                                     node_size=300,
                                     alpha=0.8)
        
        # Draw edges by type
        for rel_type, color in edge_colors.items():
            edges_of_type = [(u, v) for u, v, data in self.graph.edges(data=True)
                           if data.get('rel_type') == rel_type]
            if edges_of_type:
                nx.draw_networkx_edges(self.graph, pos,
                                     edgelist=edges_of_type,
                                     edge_color=color,
                                     alpha=0.6,
                                     width=1.5)
        
        # Draw labels for important nodes (limit to avoid clutter)
        important_nodes = []
        for node, data in self.graph.nodes(data=True):
            # Show labels for nodes with names or if they have many connections
            if (data.get('name') and len(data.get('name', '')) < 20) or \
               self.graph.degree(node) > 3:
                important_nodes.append(node)
        
        # Limit labels to avoid overcrowding
        if len(important_nodes) > 50:
            # Sort by degree and take top 50
            important_nodes = sorted(important_nodes, 
                                   key=lambda x: self.graph.degree(x), 
                                   reverse=True)[:50]
        
        labels = {node: self.graph.nodes[node].get('name', node)[:15] 
                 for node in important_nodes}
        
        nx.draw_networkx_labels(self.graph, pos, labels, font_size=8, font_weight='bold')
        
        # Create legend
        legend_elements = []
        
        # Node type legend
        for node_type, color in node_colors.items():
            if any(data.get('node_type') == node_type for _, data in self.graph.nodes(data=True)):
                legend_elements.append(mpatches.Patch(color=color, label=f'{node_type} Nodes'))
        
        # Edge type legend
        for rel_type, color in edge_colors.items():
            if any(data.get('rel_type') == rel_type for _, _, data in self.graph.edges(data=True)):
                legend_elements.append(mpatches.Patch(color=color, label=f'{rel_type} Relations'))
        
        plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1))
        
        plt.title("Neo4j Database Graph Visualization\n(Simulink Blocks and Requirements)", 
                 fontsize=16, fontweight='bold')
        plt.axis('off')
        plt.tight_layout()
        
        # Save in requested format(s)
        if format == "all":
            plt.savefig(output_path / "neo4j_graph.png", dpi=300, bbox_inches='tight')
            plt.savefig(output_path / "neo4j_graph.svg", bbox_inches='tight')
            print(f"Saved static visualization: {output_path}/neo4j_graph.png")
            print(f"Saved static visualization: {output_path}/neo4j_graph.svg")
        elif format == "png":
            plt.savefig(output_path / "neo4j_graph.png", dpi=300, bbox_inches='tight')
            print(f"Saved static visualization: {output_path}/neo4j_graph.png")
        elif format == "svg":
            plt.savefig(output_path / "neo4j_graph.svg", bbox_inches='tight')
            print(f"Saved static visualization: {output_path}/neo4j_graph.svg")
        
        plt.close()
    
    def _create_interactive_visualization(self, output_path: Path):
        """Create interactive HTML visualization using pyvis."""
        try:
            from pyvis.network import Network
        except ImportError:
            print("pyvis not installed. Creating alternative interactive visualization...")
            self._create_alternative_interactive_visualization(output_path)
            return
        
        print("Creating interactive HTML visualization...")
        
        # Create pyvis network
        net = Network(height="800px", width="100%", bgcolor="#222222", font_color="white")
        net.barnes_hut()
        
        # Add nodes
        for node, data in self.graph.nodes(data=True):
            node_type = data.get('node_type', 'Unknown')
            node_name = data.get('name', f"Node {node}")
            
            # Set node color based on type
            colors = {
                'Block': '#FF6B6B',
                'Requirement': '#4ECDC4',
                'Unknown': '#95A5A6'
            }
            color = colors.get(node_type, '#95A5A6')
            
            # Create tooltip with node information
            tooltip = f"<b>{node_name}</b><br>Type: {node_type}<br>ID: {node}"
            if data.get('text'):
                tooltip += f"<br>Text: {data['text'][:100]}..."
            
            net.add_node(node, label=node_name[:20], color=color, 
                        title=tooltip, size=20)
        
        # Add edges
        for source, target, data in self.graph.edges(data=True):
            rel_type = data.get('rel_type', 'Unknown')
            
            # Set edge color based on relationship type
            colors = {
                'CONNECTS_TO': '#E74C3C',
                'DERIVES_FROM': '#3498DB',
                'TRACES_TO': '#2ECC71',
                'REFINES': '#F39C12',
                'SATISFIES': '#9B59B6',
                'VERIFIES': '#1ABC9C'
            }
            color = colors.get(rel_type, '#95A5A6')
            
            net.add_edge(source, target, color=color, title=rel_type)
        
        # Configure physics
        net.set_options("""
        var options = {
          "physics": {
            "enabled": true,
            "stabilization": {"iterations": 100}
          }
        }
        """)
        
        # Save HTML file
        html_file = output_path / "neo4j_graph_interactive.html"
        net.save_graph(str(html_file))
        print(f"Saved interactive visualization: {html_file}")
    
    def _create_alternative_interactive_visualization(self, output_path: Path):
        """Create an alternative interactive visualization using matplotlib with enhanced interactivity."""
        print("Creating enhanced interactive matplotlib visualization...")
        
        # Create figure with interactive backend
        plt.ion()  # Turn on interactive mode
        fig, ax = plt.subplots(figsize=(16, 12))
        
        # Use spring layout for better node distribution
        pos = nx.spring_layout(self.graph, k=3, iterations=50)
        
        # Define colors and styles for different node types
        node_colors = {
            'Block': '#FF6B6B',      # Red for Simulink blocks
            'Requirement': '#4ECDC4', # Teal for requirements
            'Unknown': '#95A5A6'     # Gray for unknown types
        }
        
        edge_colors = {
            'CONNECTS_TO': '#E74C3C',    # Red for block connections
            'DERIVES_FROM': '#3498DB',   # Blue for derivation
            'TRACES_TO': '#2ECC71',      # Green for traceability
            'REFINES': '#F39C12',        # Orange for refinement
            'SATISFIES': '#9B59B6',      # Purple for satisfaction
            'VERIFIES': '#1ABC9C'        # Cyan for verification
        }
        
        # Draw nodes by type with larger sizes for better interaction
        node_artists = {}
        for node_type, color in node_colors.items():
            nodes_of_type = [node for node, data in self.graph.nodes(data=True) 
                           if data.get('node_type') == node_type]
            if nodes_of_type:
                artists = nx.draw_networkx_nodes(self.graph, pos, 
                                               nodelist=nodes_of_type,
                                               node_color=color,
                                               node_size=500,
                                               alpha=0.8,
                                               ax=ax)
                node_artists[node_type] = artists
        
        # Draw edges by type
        for rel_type, color in edge_colors.items():
            edges_of_type = [(u, v) for u, v, data in self.graph.edges(data=True)
                           if data.get('rel_type') == rel_type]
            if edges_of_type:
                nx.draw_networkx_edges(self.graph, pos,
                                     edgelist=edges_of_type,
                                     edge_color=color,
                                     alpha=0.6,
                                     width=2.0,
                                     ax=ax)
        
        # Draw labels for all nodes (more comprehensive labeling)
        labels = {}
        for node, data in self.graph.nodes(data=True):
            name = data.get('name', f'Node {node}')
            # Truncate long names
            if len(name) > 15:
                name = name[:12] + "..."
            labels[node] = name
        
        nx.draw_networkx_labels(self.graph, pos, labels, font_size=10, 
                               font_weight='bold', ax=ax)
        
        # Create legend
        legend_elements = []
        
        # Node type legend
        for node_type, color in node_colors.items():
            if any(data.get('node_type') == node_type for _, data in self.graph.nodes(data=True)):
                legend_elements.append(mpatches.Patch(color=color, label=f'{node_type} Nodes'))
        
        # Edge type legend
        for rel_type, color in edge_colors.items():
            if any(data.get('rel_type') == rel_type for _, _, data in self.graph.edges(data=True)):
                legend_elements.append(mpatches.Patch(color=color, label=f'{rel_type} Relations'))
        
        ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1))
        
        ax.set_title("Interactive Neo4j Database Graph Visualization\n(Simulink Blocks and Requirements)\nClick and drag to explore!", 
                    fontsize=16, fontweight='bold')
        ax.axis('off')
        
        # Add interactive features
        self._add_interactive_features(fig, ax, pos)
        
        plt.tight_layout()
        
        # Save the interactive figure
        interactive_file = output_path / "neo4j_graph_interactive.png"
        plt.savefig(interactive_file, dpi=300, bbox_inches='tight')
        print(f"Saved enhanced interactive visualization: {interactive_file}")
        
        # Keep the figure open for interaction
        print("Interactive window opened. Close the window when done exploring.")
        plt.show(block=True)
    
    def _add_interactive_features(self, fig, ax, pos):
        """Add interactive features to the matplotlib plot."""
        from matplotlib.patches import Circle
        import matplotlib.patches as patches
        
        # Store node positions for click detection
        self.node_positions = pos
        self.fig = fig
        self.ax = ax
        
        # Connect click event
        fig.canvas.mpl_connect('button_press_event', self._on_click)
        
        # Add instructions text
        instructions = ("Interactive Features:\n"
                       "• Click on nodes to see details\n"
                       "• Drag to pan around the graph\n"
                       "• Use mouse wheel to zoom\n"
                       "• Close window when done")
        
        ax.text(0.02, 0.98, instructions, transform=ax.transAxes, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    def _on_click(self, event):
        """Handle mouse clicks on the graph."""
        if event.inaxes != self.ax:
            return
        
        # Find clicked node
        click_x, click_y = event.xdata, event.ydata
        if click_x is None or click_y is None:
            return
        
        # Check if click is near any node
        for node, (x, y) in self.node_positions.items():
            # Convert to display coordinates
            display_x, display_y = self.ax.transData.transform((x, y))
            click_display_x, click_display_y = self.ax.transData.transform((click_x, click_y))
            
            # Calculate distance
            distance = np.sqrt((display_x - click_display_x)**2 + (display_y - click_display_y)**2)
            
            if distance < 30:  # Within 30 pixels
                self._show_node_info(node)
                break
    
    def _show_node_info(self, node):
        """Show detailed information about a clicked node."""
        if node not in self.graph.nodes:
            return
        
        data = self.graph.nodes[node]
        node_type = data.get('node_type', 'Unknown')
        name = data.get('name', f'Node {node}')
        
        # Create info text
        info_text = f"Node: {name}\nType: {node_type}\nID: {node}"
        
        # Add additional properties
        for key, value in data.items():
            if key not in ['node_type', 'name'] and value:
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                info_text += f"\n{key}: {value}"
        
        # Show connections
        neighbors = list(self.graph.neighbors(node))
        if neighbors:
            info_text += f"\n\nConnections: {len(neighbors)}"
            for neighbor in neighbors[:5]:  # Show first 5 connections
                neighbor_name = self.graph.nodes[neighbor].get('name', f'Node {neighbor}')
                info_text += f"\n  → {neighbor_name}"
            if len(neighbors) > 5:
                info_text += f"\n  ... and {len(neighbors) - 5} more"
        
        # Display info in a popup-like text box
        self.ax.text(0.5, 0.02, info_text, transform=self.ax.transAxes, 
                    fontsize=9, verticalalignment='bottom', horizontalalignment='center',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.9))
        
        # Highlight the clicked node
        self._highlight_node(node)
        
        # Refresh the display
        self.fig.canvas.draw()
    
    def _highlight_node(self, node):
        """Highlight a specific node."""
        if node not in self.node_positions:
            return
        
        x, y = self.node_positions[node]
        
        # Draw a highlight circle
        highlight = Circle((x, y), 0.1, color='yellow', alpha=0.7, zorder=10)
        self.ax.add_patch(highlight)
        
        # Add a temporary highlight that will be removed on next click
        if hasattr(self, 'current_highlight'):
            self.current_highlight.remove()
        self.current_highlight = highlight
    
    def _show_interactive_window(self):
        """Show interactive matplotlib window."""
        print("Showing interactive matplotlib window...")
        plt.show()
    
    def export_data(self, output_path: Path):
        """Export graph data as JSON for further analysis."""
        print("Exporting graph data...")
        
        # Convert NetworkX graph to JSON-serializable format
        graph_data = {
            'nodes': [],
            'edges': []
        }
        
        # Export nodes
        for node, data in self.graph.nodes(data=True):
            node_info = {
                'id': node,
                'type': data.get('node_type', 'Unknown'),
                'properties': {k: v for k, v in data.items() if k != 'node_type'}
            }
            graph_data['nodes'].append(node_info)
        
        # Export edges
        for source, target, data in self.graph.edges(data=True):
            edge_info = {
                'source': source,
                'target': target,
                'type': data.get('rel_type', 'Unknown'),
                'properties': {k: v for k, v in data.items() if k != 'rel_type'}
            }
            graph_data['edges'].append(edge_info)
        
        # Save to JSON file
        json_file = output_path / "neo4j_graph_data.json"
        with open(json_file, 'w') as f:
            json.dump(graph_data, f, indent=2, default=str)
        
        print(f"Exported graph data: {json_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="./graph_output",
                       help="Directory to save output files")
    parser.add_argument("--format", choices=["png", "svg", "html", "all"], 
                       default="all", help="Output format")
    parser.add_argument("--interactive", action="store_true",
                       help="Show interactive matplotlib window")
    parser.add_argument("--export-data", action="store_true",
                       help="Export graph data as JSON")
    
    args = parser.parse_args()
    
    # Create visualizer
    visualizer = Neo4jGraphVisualizer()
    
    try:
        # Connect to Neo4j
        visualizer.connect()
        
        # Pull all data
        visualizer.pull_all_data()
        
        # Create output directory
        output_path = Path(args.output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Export data if requested
        if args.export_data:
            visualizer.export_data(output_path)
        
        # Create visualization
        visualizer.create_visualization(
            output_dir=args.output_dir,
            format=args.format,
            interactive=args.interactive
        )
        
        print(f"\nVisualization complete! Check {args.output_dir} for output files.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    finally:
        visualizer.close()


if __name__ == "__main__":
    main()
