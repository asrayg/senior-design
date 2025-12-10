import { Node } from "../types/types";
import { Node as RFNode } from "reactflow";

export function flattenNodes(
  nodes: Node[],
  map = new Map<string, Node>()
): Map<string, Node> {
  for (const node of nodes) {
    if (!node) continue;
    const sid = node.sid || node.name;
    if (sid) {
      map.set(sid, { ...node });
      if (node.children?.length) flattenNodes(node.children, map);
    }
  }
  return map;
}

export function createReactFlowNodes(
  allBlocks: Map<string, Node>,
  selectedNode: string | null,
  highlightedNodes: Set<string> = new Set(),
  isRequirement: boolean = false
): RFNode[] {
  const blockArray = Array.from(allBlocks.values());
  const cols = Math.ceil(Math.sqrt(blockArray.length));
  const spacing = 200;

  // Color scheme: Simulink = blue, Cameo/Requirements = purple
  const defaultColor = isRequirement ? "#8b5cf6" : "#3b82f6";
  const defaultBorder = isRequirement ? "#6d28d9" : "#1e40af";
  const highlightColor = "#10b981";
  const highlightBorder = "#059669";

  return blockArray.map((block, idx) => {
    const row = Math.floor(idx / cols);
    const col = idx % cols;
    const sid = block.sid || block.name || '';
    const isSelected = selectedNode === sid;
    const isHighlighted = highlightedNodes.has(sid);

    return {
      id: sid,
      data: { 
        label: block.name || '',
        ...block 
      },
      position: { x: col * spacing, y: row * spacing },
      style: {
        width: 100,
        height: 100,
        borderRadius: "50%",
        background: isHighlighted ? highlightColor : defaultColor,
        color: "white",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "10px",
        textAlign: "center",
        padding: "8px",
        border: isSelected ? "3px solid #fbbf24" : isHighlighted ? `3px solid ${highlightBorder}` : `2px solid ${defaultBorder}`,
        fontWeight: 500,
        cursor: "pointer",
        boxShadow: isHighlighted ? "0 0 10px rgba(16, 185, 129, 0.5)" : "none",
      },
    };
  });
}


