export type Node = {
  name?: string;
  sid?: string;
  node_type?: string;
  children?: Node[];
  impacted?: boolean;
  generated_code?: Array<{
    block_path?: string;
    code_references?: Array<{
      code?: string;
      line?: number;
    }>;
    file_path?: string;
    location?: string;
  }>;
  text?: string | null;
  incoming?: any[];
  outgoing?: any[];
};

export type ArtifactProps = {
  baselineData: Node[] | undefined;
  requirementsData: Node[] | undefined;
  parentNodes: any[];
  parentBlocksData: any[];
  expandedNode: string | null;
  setExpandedNode: (node: string | null) => void;
  onConnect: (source: string, target: string) => Promise<boolean>;
  traceabilityLinks: any[];
  hierarchyData: any[];
};
