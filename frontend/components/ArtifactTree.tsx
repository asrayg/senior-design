"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import VersionHistoryPanel from "./VersionHistoryPanel";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  Edge,
  Node as RFNode,
  useNodesState,
  useEdgesState,
  Connection,
  addEdge,
} from "reactflow";
import dagre from "dagre";
import "reactflow/dist/style.css";
import { Node, ArtifactProps } from "../types/types";
import { flattenNodes, createReactFlowNodes } from "../utils/treeUtils";
import { useReactFlow } from "reactflow";
import { BACKEND_URL } from "../constants/config";



const filterNodes = (nodes: Node[]): Node[] =>
  nodes
    .filter((n) => n.name !== "Scope" && n.name !== "More Info")
    .map((n) => ({
      ...n,
      children: n.children ? filterNodes(n.children) : [],
    }));

const generateEdgesFromTree = (
  nodes: Node[],
  allValidSids: Set<string>
): Edge[] => {
  const edges: Edge[] = [];
  const addedEdges = new Set<string>();

  const traverse = (parent: Node) => {
    if (!parent.children || parent.children.length === 0) return;

    for (const child of parent.children) {
      if (
        !child.sid ||
        !allValidSids.has(child.sid) ||
        child.name === "Scope" ||
        child.name === "More Info"
      ) {
        continue;
      }
      console.log("parent: ", parent);
      console.log("child: ", child);
      const forwardId = `${parent.sid}-${child.sid}`;

      if (!addedEdges.has(forwardId)) {
        edges.push({
          id: forwardId,
          source: parent.sid!,
          target: child.sid!,
          markerEnd: { type: MarkerType.ArrowClosed, color: "#ef4444" },
          style: { stroke: "#ef4444", strokeWidth: 2 },
          type: "smoothstep",
        });
        addedEdges.add(forwardId);
      }

      traverse(child);
    }
  };

  for (const node of nodes) traverse(node);
  return edges;
};

const applyLayout = (nodes: RFNode[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const nodeWidth = 160;
  const nodeHeight = 60;
  dagreGraph.setGraph({ rankdir: "LR", nodesep: 100, ranksep: 80 });

  nodes.forEach((node) =>
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  );
  edges.forEach((edge) => dagreGraph.setEdge(edge.source, edge.target));

  dagre.layout(dagreGraph);

  return nodes.map((node) => {
    const position = dagreGraph.node(node.id);
    node.position = { x: position.x, y: position.y };
    return node;
  });
};

export default function ArtifactTree({ 
  baselineData, 
  requirementsData, 
  parentNodes, 
  parentBlocksData, 
  expandedNode, 
  setExpandedNode, 
  onConnect: handleConnectProp,
  traceabilityLinks: traceabilityLinksData,
  hierarchyData
}: ArtifactProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [manualEdges, setManualEdges] = useState<Edge[]>([]);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());
  const [traceabilityLinks, setTraceabilityLinks] = useState<Edge[]>([]);
  const [hierarchyEdges, setHierarchyEdges] = useState<Edge[]>([]);
  const [versionViewMode, setVersionViewMode] = useState(false);
  const [versionChanges, setVersionChanges] = useState<{
    added: Set<string>;
    removed: Set<string>;
    modified: Set<string>;
  }>({ added: new Set(), removed: new Set(), modified: new Set() });
  const [pendingConnectionSource, setPendingConnectionSource] = useState<string | null>(null);
  const [editingCodeRef, setEditingCodeRef] = useState<{mappingIndex: number, refIndex: number} | null>(null);
  const [editedCodeRefs, setEditedCodeRefs] = useState<any>(null);
  const reactFlowInstance = useReactFlow();
  const prevDepsRef = useRef<string>('');

  // Transform traceability links data into edges
  useEffect(() => {
    if (traceabilityLinksData && traceabilityLinksData.length > 0) {
      const linkEdges: Edge[] = traceabilityLinksData.map((link: any) => ({
        id: `trace-${link.block.sid}-${link.requirement.id}`,
        source: link.block.sid,
        target: link.requirement.id,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#a855f7" },
        style: { stroke: "#a855f7", strokeWidth: 2.5 },
        type: "smoothstep",
        data: { relationship: link.relationship }
      }));
      setTraceabilityLinks(linkEdges);
    }
  }, [traceabilityLinksData]);

  // Transform hierarchy data into edges based on outgoing relationships
  useEffect(() => {
    if (hierarchyData && hierarchyData.length > 0) {
      const edges: Edge[] = [];
      const addedEdges = new Set<string>();
      
      const processNode = (node: any) => {
        if (node.outgoing && node.outgoing.length > 0) {
          node.outgoing.forEach((target: any) => {
            const edgeId = `hierarchy-${node.id}-${target.id}`;
            if (!addedEdges.has(edgeId)) {
              edges.push({
                id: edgeId,
                source: node.id,
                target: target.id,
                markerEnd: { type: MarkerType.ArrowClosed, color: "#3b82f6" },
                style: { stroke: "#3b82f6", strokeWidth: 2 },
                type: "smoothstep",
              });
              addedEdges.add(edgeId);
            }
          });
        }
        
        // Process children recursively
        if (node.children && node.children.length > 0) {
          node.children.forEach((child: any) => processNode(child));
        }
      };
      
      hierarchyData.forEach((rootNode: any) => processNode(rootNode));
      setHierarchyEdges(edges);
    } else {
      setHierarchyEdges([]);
    }
  }, [hierarchyData]);

  useEffect(() => {
    if (!reactFlowInstance) return;

    const timeout = setTimeout(() => {
      if (expandedNode) {
        reactFlowInstance.fitView({ padding: 0.2, duration: 800 });
      } else {
        // Center on all nodes only when collapsing/loading
        reactFlowInstance.fitView({ padding: 0.3, duration: 600 });
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [expandedNode, reactFlowInstance]);

  useEffect(() => {
    // Create a stable key from dependencies to prevent infinite loops
    const depsKey = JSON.stringify({
      expandedNode,
      parentNodesLength: parentNodes?.length || 0,
      parentBlocksDataLength: parentBlocksData?.length || 0,
      requirementsDataLength: requirementsData?.length || 0,
      traceabilityLinksLength: traceabilityLinks.length,
      hierarchyEdgesLength: hierarchyEdges.length,
      manualEdgesLength: manualEdges.length
    });
    
    // Skip if dependencies haven't actually changed
    if (prevDepsRef.current === depsKey) {
      return;
    }
    prevDepsRef.current = depsKey;

    if (!expandedNode) {
      // Create nodes from parent LoadParent nodes
      const collapsedNodes: RFNode[] = parentNodes.map((parent, index) => ({
        id: parent.id,
        type: "customNode",
        position: { x: index * 200, y: 150 },
        data: { 
          label: parent.filename || parent.id,
          blockCount: parent.block_count,
          createdAt: parent.created_at
        } as any,
        style: {
          background: "#3b82f6",
          color: "#fff",
          borderRadius: 12,
          padding: 10,
          fontWeight: "bold",
          border: "2px solid #1e40af",
        },
      }));

      const collapsedEdges: Edge[] = [];

      // Add all requirements/cameo nodes to the collapsed view
      if (requirementsData?.length) {
        const filtered = filterNodes(requirementsData);
        const allBlocks = flattenNodes(filtered);
        const allValidSids = new Set(
          Array.from(allBlocks.values()).map((b) => b.sid)
        );
        
        // Create nodes for requirements (Cameo) - purple color
        const requirementNodes = createReactFlowNodes(allBlocks, selectedNode?.sid || null, highlightedNodes, true);
        collapsedNodes.push(...requirementNodes);
        
        // Generate edges for requirements
        const allValidReqSids = new Set(
          Array.from(allBlocks.values())
            .map((b) => b.sid)
            .filter((sid): sid is string => !!sid)
        );
        const requirementEdges = generateEdgesFromTree(filtered, allValidReqSids);
        collapsedEdges.push(...requirementEdges);
      }

      // Add traceability links and hierarchy edges to the collapsed view
      const allCollapsedEdges = [...collapsedEdges, ...traceabilityLinks, ...hierarchyEdges];

      // Layout all nodes
      const laidOutNodes = applyLayout(collapsedNodes, allCollapsedEdges);
      setNodes(laidOutNodes);
      setEdges(allCollapsedEdges);
      // Don't clear manualEdges - preserve them for when we expand again
      return;
    }

    // Expand a parent node with its blocks data
    if (expandedNode && parentBlocksData?.length) {
      const filtered = filterNodes(parentBlocksData);
      const allBlocks = flattenNodes(filtered);
      const allValidSids = new Set(
        Array.from(allBlocks.values())
          .map((b) => b.sid)
          .filter((sid): sid is string => !!sid)
      );
      // Create Simulink nodes (blue color)
      const rfNodes = createReactFlowNodes(allBlocks, selectedNode?.sid || null, highlightedNodes, false);
      const preconnectedEdges = generateEdgesFromTree(filtered, allValidSids);

      // Add Cameo children to the Simulink screen so they can be selected for connection
      // Initialize allReqSids outside the if block so it's always available for filtering
      const allReqSids = new Set<string>();
      if (requirementsData?.length) {
        const filteredReqs = filterNodes(requirementsData);
        const allReqBlocks = flattenNodes(filteredReqs);
        Array.from(allReqBlocks.values()).forEach((b) => {
          if (b.sid) allReqSids.add(b.sid);
        });
        
        // Create nodes for requirements (Cameo - purple color)
        const requirementNodes = createReactFlowNodes(allReqBlocks, selectedNode?.sid || null, highlightedNodes, true);
        rfNodes.push(...requirementNodes);
        
        // Generate edges for requirements
        const requirementEdges = generateEdgesFromTree(filteredReqs, allReqSids);
        preconnectedEdges.push(...requirementEdges);
      }

      // Filter traceability links to only include those relevant to current expanded view
      // (connections where block is in current parentBlocksData or requirement is in requirementsData)
      const relevantTraceabilityLinks = traceabilityLinks.filter(edge => 
        allValidSids.has(edge.source) || allValidSids.has(edge.target) ||
        allReqSids.has(edge.source) || allReqSids.has(edge.target) ||
        edge.source === expandedNode || edge.target === expandedNode
      );

      // Filter manual edges to only include those relevant to current expanded view
      const relevantManualEdges = manualEdges.filter(edge =>
        allValidSids.has(edge.source) || allValidSids.has(edge.target) ||
        allReqSids.has(edge.source) || allReqSids.has(edge.target) ||
        edge.source === expandedNode || edge.target === expandedNode
      );

      // Combine automatic edges with manual edges, traceability links, and hierarchy edges
      // Note: traceabilityLinks already includes backend-stored connections, so they'll persist
      const allEdges = [...preconnectedEdges, ...relevantManualEdges, ...relevantTraceabilityLinks, ...hierarchyEdges];

      const laidOutNodes = applyLayout(rfNodes, allEdges);
      setNodes(laidOutNodes);
      setEdges(allEdges);
      return;
    }

  }, [
    requirementsData, 
    expandedNode, 
    parentNodes, 
    parentBlocksData, 
    traceabilityLinks, 
    hierarchyEdges, 
    manualEdges
  ]);

  // Separate useEffect to handle highlighting updates without resetting connections
  useEffect(() => {
    if (versionViewMode) return;
    
    // Helper to determine if node is a requirement (Cameo) based on original color
    const isRequirementNode = (node: RFNode): boolean => {
      const originalBg = node.style?.background;
      return originalBg === "#8b5cf6" || originalBg === "#6d28d9";
    };
    
    if (!expandedNode) {
      // For non-expanded mode, update node styles for highlighting
      setNodes((currentNodes) => 
        currentNodes.map((node) => {
          const isHighlighted = highlightedNodes.has(node.id);
          const isSelected = selectedNode?.sid === node.id;
          const isRequirement = isRequirementNode(node);
          
          // Preserve original color scheme: Simulink = blue, Cameo = purple
          const defaultColor = isRequirement ? "#8b5cf6" : "#3b82f6";
          const defaultBorder = isRequirement ? "#6d28d9" : "#1e40af";
          
          return {
            ...node,
            style: {
              ...node.style,
              background: isHighlighted ? "#10b981" : defaultColor,
              border: isSelected ? "3px solid #fbbf24" :
                      isHighlighted ? "3px solid #059669" : `2px solid ${defaultBorder}`,
              boxShadow: isHighlighted ? "0 0 10px rgba(16, 185, 129, 0.5)" : "none",
            },
          };
        })
      );
    } else {
      // For expanded mode, update node styles for highlighting and selection
      setNodes((currentNodes) => 
        currentNodes.map((node) => {
          const isHighlighted = highlightedNodes.has(node.id);
          const isSelected = selectedNode?.sid === node.id;
          const isRequirement = isRequirementNode(node);
          
          // Preserve original color scheme: Simulink = blue, Cameo = purple
          const defaultColor = isRequirement ? "#8b5cf6" : "#3b82f6";
          const defaultBorder = isRequirement ? "#6d28d9" : "#1e40af";
          
          return {
            ...node,
            style: {
              ...node.style,
              background: isHighlighted ? "#10b981" : defaultColor,
              border: isSelected ? "3px solid #fbbf24" : 
                      isHighlighted ? "3px solid #059669" : `2px solid ${defaultBorder}`,
              boxShadow: isHighlighted ? "0 0 10px rgba(16, 185, 129, 0.5)" : "none",
            },
          };
        })
      );
    }
  }, [highlightedNodes, expandedNode, selectedNode, versionViewMode]);

    useEffect(() => {
      if (! versionViewMode) return;
  
      // Helper to determine if node is a requirement (Cameo) based on original color
      const isRequirementNode = (node: RFNode): boolean => {
        const originalBg = node.style?.background;
        return originalBg === "#8b5cf6" || originalBg === "#6d28d9";
      };
  
      setNodes((currentNodes) =>
        currentNodes. map((node) => {
          const isAdded = versionChanges.added.has(node. id);
          const isRemoved = versionChanges.removed.has(node. id);
          const isModified = versionChanges.modified.has(node. id);
          const isSelected = selectedNode?.sid === node.id;
          const isRequirement = isRequirementNode(node);
  
          // Preserve original color scheme: Simulink = blue, Cameo = purple
          const defaultColor = isRequirement ? "#8b5cf6" : "#3b82f6";
          const defaultBorder = isRequirement ? "#6d28d9" : "#1e40af";
          
          let background = defaultColor;
          let border = `2px solid ${defaultBorder}`;
          let boxShadow = "none";
  
          if (isAdded) {
            background = "#22c55e";
            border = "3px solid #16a34a";
            boxShadow = "0 0 15px rgba(34, 197, 94, 0.6)";
          } else if (isRemoved) {
            background = "#ef4444";
            border = "3px solid #dc2626";
            boxShadow = "0 0 15px rgba(239, 68, 68, 0.6)";
          } else if (isModified) {
            background = "#f59e0b";
            border = "3px solid #d97706";
            boxShadow = "0 0 15px rgba(245, 158, 11, 0.6)";
          }
  
          if (isSelected) {
            border = "4px solid #fbbf24";
          }
  
          return {
            ...node,
            style: {
              ... node.style,
              background,
              border,
              boxShadow,
            },
          };
        })
      );
    }, [versionViewMode, versionChanges, selectedNode, setNodes]);
  
    useEffect(() => {
      if (! versionViewMode) return;
  
      setEdges((currentEdges) =>
        currentEdges.map((edge) => {
          const sourceChanged = versionChanges.added.has(edge. source) || versionChanges.added.has(edge. target);
  
          if (sourceChanged) {
            return {
              ...edge,
              style: {
                ...edge.style,
                stroke: "#22c55e",
                strokeWidth: 4,
              },
              animated: true,
            };
          }
  
          return edge;
        })
      );
    }, [versionViewMode, versionChanges, setEdges]);
  // Helper function to find all descendants by traversing the edge graph
  const findDescendantsFromEdges = useCallback((nodeId: string, edgeList: Edge[]): Set<string> => {
    const descendants = new Set<string>();
    const visited = new Set<string>();
    
    const traverse = (currentId: string) => {
      if (visited.has(currentId)) return; // Prevent infinite loops
      visited.add(currentId);
      
      // Find all outgoing edges from the current node
      const outgoingEdges = edgeList.filter(edge => edge.source === currentId);
      
      for (const edge of outgoingEdges) {
        if (!descendants.has(edge.target)) {
          descendants.add(edge.target);
          // Recursively find descendants of this child
          traverse(edge.target);
        }
      }
    };
    
    traverse(nodeId);
    return descendants;
  }, []);

  const handleCompareVersions = useCallback((
    currentSnapshot: any, 
    initialSnapshot: any | null
  ) => {
    if (!initialSnapshot) {
      setVersionViewMode(false);
      setVersionChanges({ added: new Set(), removed: new Set(), modified: new Set() });
      return;
    }

    setVersionViewMode(true);
    
    const added = new Set<string>();
    const removed = new Set<string>();
    const modified = new Set<string>();

    const currentConnections = new Set<string>();
    const initialConnections = new Set<string>();

    if (currentSnapshot. snapshot?. connections) {
      (currentSnapshot.snapshot. connections. outgoing || []).forEach((id: string) => currentConnections.add(id));
      (currentSnapshot.snapshot. connections.incoming || []).forEach((id: string) => currentConnections.add(id));
      (currentSnapshot.snapshot. connections.satisfies || []).forEach((id: string) => currentConnections. add(id));
    }
    if (currentSnapshot.snapshot?.relationships) {
      (currentSnapshot.snapshot. relationships.derives_from || []).forEach((id: string) => currentConnections. add(id));
      (currentSnapshot. snapshot.relationships.derived_by || []).forEach((id: string) => currentConnections.add(id));
      (currentSnapshot.snapshot.relationships.satisfies || []).forEach((id: string) => currentConnections.add(id));
    }

    if (initialSnapshot.snapshot?.connections) {
      (initialSnapshot. snapshot.connections.outgoing || []).forEach((id: string) => initialConnections. add(id));
      (initialSnapshot. snapshot.connections.incoming || []).forEach((id: string) => initialConnections.add(id));
      (initialSnapshot.snapshot.connections.satisfies || []).forEach((id: string) => initialConnections.add(id));
    }
    if (initialSnapshot.snapshot?. relationships) {
      (initialSnapshot.snapshot.relationships.derives_from || []).forEach((id: string) => initialConnections. add(id));
      (initialSnapshot. snapshot.relationships.derived_by || []). forEach((id: string) => initialConnections.add(id));
      (initialSnapshot.snapshot.relationships. satisfies || []). forEach((id: string) => initialConnections.add(id));
    }

    currentConnections.forEach(id => {
      if (! initialConnections.has(id)) {
        added.add(id);
      }
    });

    initialConnections. forEach(id => {
      if (!currentConnections.has(id)) {
        removed.add(id);
      }
    });

    if (currentSnapshot.snapshot?.change) {
      const { source, target } = currentSnapshot.snapshot.change;
      if (source) added.add(source);
      if (target) added.add(target);
    }

    setVersionChanges({ added, removed, modified });
  }, []);

  const resetVersionView = useCallback(() => {
    setVersionViewMode(false);
    setVersionChanges({ added: new Set(), removed: new Set(), modified: new Set() });
  }, []);

  // Helper function to find a node by sid from tree data
  const findNodeInTree = useCallback((nodeId: string, treeNodes: Node[]): Node | null => {
    for (const treeNode of treeNodes) {
      if (treeNode.sid === nodeId) {
        return treeNode;
      }
      if (treeNode.children && treeNode.children.length > 0) {
        const found = findNodeInTree(nodeId, treeNode.children);
        if (found) return found;
      }
    }
    return null;
  }, []);

  const handleNodeClick = useCallback(
    async (_: any, node: RFNode) => {
      if (versionViewMode) {
        resetVersionView();
      }
      // Check if clicking the same node - if so, toggle off the impact analysis
      if (selectedNode?.sid === node.id) {
        setSelectedNode(null);
        setHighlightedNodes(new Set());
        setPendingConnectionSource(null);
        return;
      }

      // ReactFlow node data should already have all properties including generated_code
      // since we spread all node properties into node.data when creating ReactFlow nodes
      const reactFlowNodeData = node.data as any;
      
      // Try to find the original node from tree data as a fallback
      // This ensures we get the complete data even if ReactFlow node data is incomplete
      let fullNodeData: Node | null = null;
      
      if (expandedNode && parentBlocksData) {
        fullNodeData = findNodeInTree(node.id, parentBlocksData);
      }
      if (!fullNodeData && baselineData) {
        fullNodeData = findNodeInTree(node.id, baselineData);
      }
      if (!fullNodeData && requirementsData) {
        fullNodeData = findNodeInTree(node.id, requirementsData);
      }

      // Merge: Use tree data as base (most complete), then overlay ReactFlow node data
      // This ensures we have all properties including generated_code
      const nodeData = {
        sid: node.id,
        name: reactFlowNodeData?.label || fullNodeData?.name || "Unnamed Node",
        ...fullNodeData, // Start with tree data (includes generated_code)
        ...reactFlowNodeData, // Overlay with ReactFlow data (in case it has updates)
      };
      
      setSelectedNode(nodeData);

      // Find and highlight children of the clicked node by traversing edges
      const descendants = findDescendantsFromEdges(node.id, edges);
      setHighlightedNodes(descendants);

      // If on Simulink screen and clicked node is a Cameo child, set as pending connection source
      if (expandedNode) {
        try {
          const nodeTypeRes = await fetch(`${BACKEND_URL}/api/node-type/${node.id}`);
          if (nodeTypeRes.ok) {
            const nodeType = await nodeTypeRes.json();
            if (nodeType.type === 'Requirement' && nodeType.has_children) {
              setPendingConnectionSource(node.id);
            } else {
              setPendingConnectionSource(null);
            }
          }
        } catch (error) {
          console.error('Error checking node type:', error);
        }
      } else {
        setPendingConnectionSource(null);
      }
    },
    [edges, findDescendantsFromEdges, selectedNode, versionViewMode, resetVersionView, expandedNode, findNodeInTree, parentBlocksData, baselineData, requirementsData]
  );

  const handleNodeDoubleClick = useCallback(
    (_: any, node: RFNode) => {
      // Allow expanding any parent node when not already expanded
      if (!expandedNode) {
        setExpandedNode(node.id);
      }
    },
    [expandedNode, setExpandedNode]
  );

  const onConnect = useCallback(
    async (params: Connection) => {
      // Prevent self-connections
      if (params.source === params.target) {
        return;
      }

      // Check if connection already exists
      const connectionExists = edges.some(
        (edge) =>
          edge.source === params.source && edge.target === params.target
      );

      if (connectionExists) {
        return;
      }

      // Check if connecting Cameo child to Simulink parent/block
      // Only intercept and navigate if we're on the main screen
      if (!expandedNode && params.target) {
        try {
          const sourceTypeRes = await fetch(`${BACKEND_URL}/api/node-type/${params.source}`);
          const targetTypeRes = await fetch(`${BACKEND_URL}/api/node-type/${params.target}`);
          
          if (sourceTypeRes.ok && targetTypeRes.ok) {
            const sourceType = await sourceTypeRes.json();
            const targetType = await targetTypeRes.json();
            
            // If source is a Cameo child (Requirement with children) and target is LoadParent
            if (sourceType.type === 'Requirement' && sourceType.has_children && targetType.type === 'LoadParent') {
              // Navigate to the Simulink parent screen
              setExpandedNode(params.target);
              // Store the source for connection UI
              setPendingConnectionSource(params.source!);
              // Don't create connection yet - let user choose parent or children
              return;
            }
            
            // If source is a Cameo child and target is a Block, find its parent and navigate
            if (sourceType.type === 'Requirement' && sourceType.has_children && targetType.type === 'Block' && targetType.parent_id) {
              setExpandedNode(targetType.parent_id);
              // Store the source for connection UI
              setPendingConnectionSource(params.source!);
              // Don't create connection yet - let user choose parent or children
              return;
            }
          }
        } catch (error) {
          console.error('Error checking node types:', error);
        }
      }
      
      // If we're already on the Simulink screen, allow direct connections to proceed normally

      // Create new edge
      const newEdge: Edge = {
        id: `${params.source}-${params.target}`,
        source: params.source!,
        target: params.target!,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" },
        style: { stroke: "#10b981", strokeWidth: 2 },
        type: "smoothstep",
      };

      // Use the passed-in handler for API call
      console.log("params: SOURCE: ", params.source, "TARGET: ", params.target);
      const success = await handleConnectProp(params.source!, params.target!);
      
      if (!success) {
        return;
      }

      // Store manual edge separately
      setManualEdges((prev) => [...prev, newEdge]);
      
      // Also add to traceability links so it persists after collapse/expand
      // Create a traceability link edge with the same connection
      const traceabilityEdge: Edge = {
        id: `trace-${params.source}-${params.target}`,
        source: params.source!,
        target: params.target!,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#a855f7" },
        style: { stroke: "#a855f7", strokeWidth: 2.5 },
        type: "smoothstep",
        data: { relationship: "SATISFIES" }
      };
      setTraceabilityLinks((prev) => [...prev, traceabilityEdge]);
      
      setEdges((eds) => addEdge(newEdge, eds));
    },
    [edges, setEdges, handleConnectProp, expandedNode, setExpandedNode]
  );

  const miniMapStyle = useMemo(
    () => ({
      nodeStrokeColor: (n: RFNode) =>
        typeof n.style?.background === "string"
          ? n.style.background
          : "#3b82f6",
      nodeColor: (n: RFNode) =>
        typeof n.style?.background === "string"
          ? n.style.background
          : "#3b82f6",
      nodeBorderRadius: 50,
    }),
    []
  );

  return (
    <div className="grid grid-cols-3 gap-6">
      <div
        className="col-span-2 p-4 rounded-lg"
        style={{ height: "70vh", backgroundColor: "#f3f4f6" }}
      >
        {expandedNode && (
          <button
            onClick={() => {
              setExpandedNode(null);
              setSelectedNode(null);
              setHighlightedNodes(new Set());
              setPendingConnectionSource(null);
            }}
            className="mb-3 px-3 py-1 text-sm bg-gray-700 text-white rounded hover:bg-gray-600"
          >
            Collapse {expandedNode}
          </button>
        )}

        {nodes.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-600">
            No nodes available.
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            onNodeDoubleClick={handleNodeDoubleClick}
            onConnect={onConnect}
            fitView
            minZoom={0.01}
            maxZoom={4}
          >
            <Background color="#e5e7eb" gap={16} />
            <Controls />
            <MiniMap {...miniMapStyle} />
          </ReactFlow>
        )}
      </div>

      <div className="col-span-1 space-y-6">

        {selectedNode ? (
          <div className="p-4 border rounded-lg bg-white shadow space-y-3">
            <h3 className="text-lg font-semibold text-gray-900">
              Node Details
            </h3>

            <ul className="text-sm text-gray-700 space-y-1">
              <li>
                <span className="font-medium text-gray-900">Name:</span>{" "}
                {selectedNode.name}
              </li>
              <li>
                <span className="font-medium text-gray-900">SID:</span>{" "}
                {selectedNode.sid}
              </li>
              {selectedNode.node_type && (
                <li>
                  <span className="font-medium text-gray-900">Type:</span>{" "}
                  {selectedNode.node_type}
                </li>
              )}
              {typeof selectedNode.impacted !== "undefined" && (
                <li>
                  <span className="font-medium text-gray-900">Impacted:</span>{" "}
                  {selectedNode.impacted ? "Yes" : "No"}
                </li>
              )}
              {Array.isArray(selectedNode.children) && (
                <li>
                  <span className="font-medium text-gray-900">Children:</span>{" "}
                  {selectedNode.children.length}
                </li>
              )}
            </ul>

            <div className="border-t pt-3">
              <h4 className="font-semibold text-gray-900 mb-1 text-sm">
                Connected Nodes
              </h4>

              {(() => {
                const incoming = edges.filter(
                  (e) => e.target === selectedNode.sid
                );
                const outgoing = edges.filter(
                  (e) => e.source === selectedNode.sid
                );

                const getLabel = (id: string) =>
                  (nodes.find((n) => n.id === id)?.data as { label?: string })
                    ?.label || id;

                return (
                  <div className="space-y-2 text-sm text-gray-700">
                    <div>
                      <span className="font-medium text-gray-800">
                        Incoming from:
                      </span>
                      {incoming.length > 0 ? (
                        <ul className="list-disc list-inside">
                          {incoming.map((e) => (
                            <li key={`in-${e.id}`}>{getLabel(e.source)}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="italic text-gray-500">None</p>
                      )}
                    </div>

                    <div>
                      <span className="font-medium text-gray-800">
                        Outgoing to:
                      </span>
                      {outgoing.length > 0 ? (
                        <ul className="list-disc list-inside">
                          {outgoing.map((e) => (
                            <li key={`out-${e.id}`}>{getLabel(e.target)}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="italic text-gray-500">None</p>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Generated Code Section - Only show if there's actual generated code */}
            {Array.isArray(selectedNode.generated_code) && selectedNode.generated_code.length > 0 && (
              <div className="border-t pt-3">
                <h4 className="font-semibold text-gray-900 mb-2 text-sm">
                  Generated Code
                </h4>
                <div className="space-y-3 text-sm">
                  {selectedNode.generated_code.map((codeMapping: any, index: number) => (
                    <div key={index} className="p-2 bg-gray-50 rounded border border-gray-200">
                      <div className="font-medium text-gray-800 mb-1">
                        {codeMapping.block_path || 'Unknown Block'}
                      </div>
                      <div className="text-xs text-gray-600 mb-2">
                        {codeMapping.code_references?.length || 0} reference(s)
                      </div>
                      {codeMapping.file_path && (
                        <a
                          href={`${BACKEND_URL}/api/code-file?file_path=${encodeURIComponent(codeMapping.file_path)}&raw=true`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline text-xs break-all block"
                          onClick={(e) => {
                            e.preventDefault();
                            window.open(
                              `${BACKEND_URL}/api/code-file?file_path=${encodeURIComponent(codeMapping.file_path)}&raw=true`,
                              '_blank'
                            );
                          }}
                        >
                          📄 {codeMapping.file_path.split('/').pop() || codeMapping.file_path}
                        </a>
                      )}
                      {codeMapping.code_references && codeMapping.code_references.length > 0 && (
                        <div className="mt-2 text-xs space-y-2 max-h-64 overflow-y-auto">
                          {codeMapping.code_references.map((ref: any, refIndex: number) => {
                            const isEditing = editingCodeRef?.mappingIndex === index && editingCodeRef?.refIndex === refIndex;
                            const currentRefs = editedCodeRefs || selectedNode.generated_code;
                            const currentRef = currentRefs[index]?.code_references?.[refIndex] || ref;
                            
                            return (
                              <div key={refIndex} className="font-mono text-xs bg-white p-2 rounded border border-gray-200">
                                {isEditing ? (
                                  <div className="space-y-2">
                                    <div>
                                      <label className="text-gray-600 text-xs">Line Number:</label>
                                      <input
                                        type="number"
                                        value={currentRef.line || ''}
                                        onChange={(e) => {
                                          const newRefs = JSON.parse(JSON.stringify(currentRefs));
                                          if (!newRefs[index].code_references[refIndex]) {
                                            newRefs[index].code_references[refIndex] = {};
                                          }
                                          newRefs[index].code_references[refIndex].line = parseInt(e.target.value) || 0;
                                          setEditedCodeRefs(newRefs);
                                        }}
                                        className="w-full px-2 py-1 border border-gray-300 rounded text-xs"
                                      />
                                    </div>
                                    <div>
                                      <label className="text-gray-600 text-xs">Code:</label>
                                      <textarea
                                        value={currentRef.code || ''}
                                        onChange={(e) => {
                                          const newRefs = JSON.parse(JSON.stringify(currentRefs));
                                          if (!newRefs[index].code_references[refIndex]) {
                                            newRefs[index].code_references[refIndex] = {};
                                          }
                                          newRefs[index].code_references[refIndex].code = e.target.value;
                                          setEditedCodeRefs(newRefs);
                                        }}
                                        rows={3}
                                        className="w-full px-2 py-1 border border-gray-300 rounded text-xs font-mono"
                                      />
                                    </div>
                                    <div className="flex gap-2">
                                      <button
                                        onClick={async () => {
                                          // Save changes
                                          const refsToSave = editedCodeRefs || selectedNode.generated_code;
                                          const updatedRef = refsToSave[index].code_references[refIndex];
                                          
                                          try {
                                            const response = await fetch(`${BACKEND_URL}/api/code-references/update`, {
                                              method: 'POST',
                                              headers: { 'Content-Type': 'application/json' },
                                              body: JSON.stringify({
                                                block_sid: selectedNode.sid,
                                                block_path: codeMapping.block_path,
                                                file_path: codeMapping.file_path,
                                                ref_index: refIndex,
                                                line: updatedRef.line,
                                                code: updatedRef.code
                                              })
                                            });
                                            
                                            if (response.ok) {
                                              // Update selectedNode with saved changes
                                              const updatedNode = {
                                                ...selectedNode,
                                                generated_code: refsToSave
                                              };
                                              setSelectedNode(updatedNode);
                                              setEditingCodeRef(null);
                                              setEditedCodeRefs(null);
                                            } else {
                                              alert('Failed to save changes');
                                            }
                                          } catch (error) {
                                            console.error('Error saving code reference:', error);
                                            alert('Error saving changes');
                                          }
                                        }}
                                        className="px-2 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
                                      >
                                        Save
                                      </button>
                                      <button
                                        onClick={() => {
                                          setEditingCodeRef(null);
                                          setEditedCodeRefs(null);
                                        }}
                                        className="px-2 py-1 bg-gray-300 text-gray-700 text-xs rounded hover:bg-gray-400"
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1">
                                      <div className="text-gray-600">Line {ref.line}:</div>
                                      <div className="text-gray-800 break-words">{ref.code || '(no code)'}</div>
                                    </div>
                                    <button
                                      onClick={() => {
                                        setEditingCodeRef({ mappingIndex: index, refIndex });
                                        setEditedCodeRefs(JSON.parse(JSON.stringify(selectedNode.generated_code)));
                                      }}
                                      className="px-2 py-1 bg-gray-200 text-gray-700 text-xs rounded hover:bg-gray-300 flex-shrink-0"
                                      title="Edit code reference"
                                    >
                                      ✏️
                                    </button>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 border rounded-lg bg-white shadow text-sm text-gray-500 italic">
            Click a node to view its details and connections.
          </div>
        )}

        {/* Connection Options for Cameo Child -> Simulink */}
        {expandedNode && pendingConnectionSource && (
          <div className="p-4 border rounded-lg bg-white shadow space-y-3 border-blue-500 border-2">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">
                Connect Cameo Child
              </h3>
              <button
                onClick={() => setPendingConnectionSource(null)}
                className="text-xs px-2 py-1 bg-black-200 rounded hover:bg-black-300"
              >
                Cancel
              </button>
            </div>
            <p className="text-sm text-gray-600">
              Choose where to connect: <span className="font-medium">{(() => {
                const sourceNode = nodes.find(n => n.id === pendingConnectionSource);
                return sourceNode ? (sourceNode.data as any)?.label || pendingConnectionSource : pendingConnectionSource;
              })()}</span>
            </p>
            
            <div className="space-y-2">
              {/* Connect to Parent */}
              <button
                onClick={async () => {
                  const success = await handleConnectProp(pendingConnectionSource, expandedNode);
                  if (success) {
                    const newEdge: Edge = {
                      id: `${pendingConnectionSource}-${expandedNode}`,
                      source: pendingConnectionSource,
                      target: expandedNode,
                      markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" },
                      style: { stroke: "#10b981", strokeWidth: 2 },
                      type: "smoothstep",
                    };
                    setManualEdges((prev) => [...prev, newEdge]);
                    setEdges((eds) => addEdge(newEdge, eds));
                    setPendingConnectionSource(null);
                  }
                }}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm font-medium"
              >
                Connect to Parent ({expandedNode})
              </button>

              {/* Connect to Children */}
              {parentBlocksData && parentBlocksData.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-700 mb-2">
                    Connect to Simulink Children:
                  </p>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {(() => {
                      const allBlocks = flattenNodes(parentBlocksData);
                      return Array.from(allBlocks.values())
                        .filter((block) => block.sid) // Filter out blocks without sid
                        .map((block) => (
                        <button
                          key={block.sid}
                          onClick={async () => {
                            if (!block.sid) return;
                            const success = await handleConnectProp(pendingConnectionSource, block.sid);
                            if (success) {
                              const newEdge: Edge = {
                                id: `${pendingConnectionSource}-${block.sid}`,
                                source: pendingConnectionSource,
                                target: block.sid,
                                markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" },
                                style: { stroke: "#10b981", strokeWidth: 2 },
                                type: "smoothstep",
                              };
                              setManualEdges((prev) => [...prev, newEdge]);
                              setEdges((eds) => addEdge(newEdge, eds));
                              setPendingConnectionSource(null);
                            }
                          }}
                          className="w-full px-3 py-1.5 bg-gray-100 text-gray-800 rounded hover:bg-gray-200 text-xs text-left"
                        >
                          {block.name} ({block.sid})
                        </button>
                      ));
                    })()}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Version History Panel */}
        {selectedNode && (
          <div className="p-4 border rounded-lg bg-white shadow space-y-3">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">
                Version History
              </h3>
              {versionViewMode && (
                <button
                  onClick={resetVersionView}
                  className="text-xs px-2 py-1 bg-gray-200 rounded hover:bg-gray-300"
                >
                  Exit Compare
                </button>
              )}
            </div>
            
            {/* Version comparison legend */}
            {versionViewMode && (
              <div className="text-xs space-y-1 p-2 bg-gray-50 rounded">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded bg-green-500"></div>
                  <span>Added connection</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded bg-red-500"></div>
                  <span>Removed connection</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded bg-orange-500"></div>
                  <span>Modified</span>
                </div>
              </div>
            )}
            
            <VersionHistoryPanel 
              artifactId={(selectedNode.sid || selectedNode.id || '') as string} 
              onLoadSnapshot={(snapshot) => {
                console.log('Loaded snapshot:', snapshot);
              }}
              onCompareVersions={handleCompareVersions}
            />
          </div>
        )}
      </div>
    </div>
  );
}
