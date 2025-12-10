"use client";

import { useState } from "react";
import ArtifactTree from "../components/ArtifactTree";
import { BACKEND_URL } from "../constants/config";
import { useEffect } from "react";
import type { Node } from "../types/types";
import { ReactFlowProvider } from "reactflow";

export default function Home() {
  const [baselineData, setBaselineData] = useState<Node[] | null>(null);
  const [requirementsData, setRequirementsData] = useState<Node[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [parentNodes, setParentNodes] = useState<any[]>([]);
  const [parentBlocksData, setParentBlocksData] = useState<any[]>([]);
  const [expandedNode, setExpandedNode] = useState<string | null>(null);
  const [traceabilityLinks, setTraceabilityLinks] = useState<any[]>([]);
  const [hierarchyData, setHierarchyData] = useState<any[]>([]);

  useEffect(() => {
    const cachedBaseline = localStorage.getItem("baselineData");
    const cachedRequirements = localStorage.getItem("requirementsData");
    
    if (cachedBaseline && cachedRequirements) {
      setBaselineData(JSON.parse(cachedBaseline));
      setRequirementsData(JSON.parse(cachedRequirements));
      setLoading(false);
      console.log(`Loaded cached data`);
    } else {
      Promise.all([fetchBaseline(), fetchRequirements()]).finally(() => setLoading(false));
    }
  }, []);

  useEffect(() => {
    fetchParentNodes();
  }, []);

  // Fetch traceability links
  useEffect(() => {
    fetchTraceabilityLinks();
  }, []);

  // Fetch hierarchy data
  useEffect(() => {
    const fetchHierarchyData = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/requirements/hierarchy`);
        const data = await response.json();
        
        if (data && data.length > 0) {
          setHierarchyData(data);
        }
      } catch (error) {
        console.error('Failed to fetch hierarchy data:', error);
      }
    };

    fetchHierarchyData();
  }, []);

  useEffect(() => {
    const fetchParentBlocks = async () => {
      if (!expandedNode) {
        setParentBlocksData([]);
        return;
      }

      try {
        const response = await fetch(`${BACKEND_URL}/api/parents/${expandedNode}/blocks`);
        if (response.ok) {
          const data = await response.json();
          setParentBlocksData(data);
        }
      } catch (error) {
        console.error("Error fetching parent blocks:", error);
      }
    };

    fetchParentBlocks();
  }, [expandedNode]);

  const fetchBaseline = async () => {
    try {
      setError(null);
      const response = await fetch(`${BACKEND_URL}/baseline`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      localStorage.setItem("baselineData", JSON.stringify(data));
      console.log("baselineData: ", data);
      setBaselineData(data);
    } catch (e: any) {
      setError(e.message || `Failed to load baseline data`);
    }
  };

  const fetchRequirements = async () => {
    try {
      setError(null);
      const response = await fetch(`${BACKEND_URL}/api/requirements`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      // Transform flat structure with ID references into nested tree
      const transformedData = transformRequirementsToTree(data);
      localStorage.setItem("requirementsData", JSON.stringify(transformedData));
      setRequirementsData(transformedData);
    } catch (e: any) {
      setError(e.message || `Failed to load requirements data`);
    }
  };

  const fetchParentNodes = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/parents`);
      if (response.ok) {
        const data = await response.json();
        setParentNodes(data);
      }
    } catch (error) {
      console.error("Error fetching parent nodes:", error);
    }
  };

  const fetchTraceabilityLinks = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/traceability/links`);
      const data = await response.json();
      
      if (data.links && data.links.length > 0) {
        setTraceabilityLinks(data.links);
      } else {
        setTraceabilityLinks([]);
      }
    } catch (error) {
      console.error('Failed to fetch traceability links:', error);
    }
  };

  const handleConnect = async (source: string, target: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source,
          target,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: response.statusText }));
        alert(`Failed to create connection: ${errorData.error || response.statusText}`);
        console.error('Failed to create connection:', response.statusText);
        return false;
      }
      
      const result = await response.json();
      console.log("source (SID): ", source);
      console.log("target (SID): ", target);
      console.log("Connection created successfully");
      
      // Show success alert
      alert(`Connection created successfully!\n${source} → ${target}\nRelationship: ${result.relationship_type || 'SATISFIES'}`);
      
      return true;
    } catch (error) {
      alert(`Error creating connection: ${error instanceof Error ? error.message : 'Unknown error'}`);
      console.error("Error creating connection:", error);
      return false;
    }
  };

  // Transform requirements data from flat structure to nested tree
  const transformRequirementsToTree = (requirements: any[]): Node[] => {
    // Create a map of all nodes
    const nodeMap = new Map<string, Node>();
    
    requirements.forEach((req) => {
      nodeMap.set(req.id, {
        name: req.name,
        sid: req.id,
        node_type: req.type,
        children: [],
        impacted: false,
      });
    });

    // Build parent-child relationships
    const rootNodes: Node[] = [];
    const childIds = new Set<string>();

    requirements.forEach((req) => {
      const parentNode = nodeMap.get(req.id);
      if (!parentNode) return;

      if (req.children && Array.isArray(req.children)) {
        req.children.forEach((childId: string | number) => {
          const childIdStr = String(childId);
          const childNode = nodeMap.get(childIdStr);
          if (childNode) {
            parentNode.children!.push(childNode);
            childIds.add(childIdStr);
          }
        });
      }
    });

    // Root nodes are those that are not children of any other node
    requirements.forEach((req) => {
      if (!childIds.has(req.id)) {
        const node = nodeMap.get(req.id);
        if (node) rootNodes.push(node);
      }
    });

    return rootNodes;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Configuration Management
          </h1>
          <p className="text-gray-600">
            Manage your system artifacts and create connections
          </p>
        </div>

        {/* Content */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <ReactFlowProvider>
            <ArtifactTree 
              baselineData={baselineData ?? undefined} 
              requirementsData={requirementsData ?? undefined}
              parentNodes={parentNodes}
              parentBlocksData={parentBlocksData}
              expandedNode={expandedNode}
              setExpandedNode={setExpandedNode}
              onConnect={handleConnect}
              traceabilityLinks={traceabilityLinks}
              hierarchyData={hierarchyData}
            />
          </ReactFlowProvider>
        </div>
      </div>
    </div>
  );
}
