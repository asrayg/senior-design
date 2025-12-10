import { useState, useCallback } from 'react';

interface Version {
  version_id: string;
  timestamp: string;
  version_number: number;
  artifact_type: string;
  tool: string;
}

interface VersionSnapshot {
  version_id: string;
  artifact_id: string;
  timestamp: string;
  version_number: number;
  snapshot: Record<string, any>;
}

export function useVersionHistory() {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState<VersionSnapshot | null>(null);

  const fetchVersions = useCallback(async (artifactId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:5000/api/artifacts/${artifactId}/versions`);
      const data = await response. json();
      setVersions(data. versions || []);
    } catch (error) {
      console.error('Failed to fetch versions:', error);
      setVersions([]);
    }
    setLoading(false);
  }, []);

  const loadSnapshot = useCallback(async (versionId: string) => {
    try {
      const response = await fetch(`http://localhost:5000/api/versions/${versionId}/snapshot`);
      const data = await response.json();
      setSelectedSnapshot(data);
      return data;
    } catch (error) {
      console.error('Failed to load snapshot:', error);
      return null;
    }
  }, []);

  return { versions, loading, fetchVersions, loadSnapshot, selectedSnapshot };
}