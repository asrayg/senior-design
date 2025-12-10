"use client";

import { useEffect, useState } from 'react';

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
  is_initial: boolean;
  snapshot: {
    node_id?: string;
    name?: string;
    connections?: {
      outgoing?: string[];
      incoming?: string[];
      satisfies?: string[];
    };
    relationships?: {
      derives_from?: string[];
      derived_by?: string[];
      satisfies?: string[];
    };
    change?: {
      type: string;
      source: string;
      target: string;
      timestamp: string;
    };
  };
}

interface Props {
  artifactId: string;
  onLoadSnapshot?: (snapshot: VersionSnapshot) => void;
  onCompareVersions?: (currentSnapshot: VersionSnapshot, initialSnapshot: VersionSnapshot | null) => void;
}

export default function VersionHistoryPanel({ artifactId, onLoadSnapshot, onCompareVersions }: Props) {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingVersion, setLoadingVersion] = useState<string | null>(null);
  const [activeSnapshot, setActiveSnapshot] = useState<VersionSnapshot | null>(null);
  const [initialSnapshot, setInitialSnapshot] = useState<VersionSnapshot | null>(null);

  useEffect(() => {
    const fetchVersions = async () => {
      if (!artifactId) return;
      
      setLoading(true);
      try {
        const res = await fetch(`http://localhost:5000/api/artifacts/${artifactId}/versions`);
        const data = await res. json();
        const versionList = data.versions || [];
        setVersions(versionList);
        
        if (versionList.length > 0) {
          const initial = versionList. find((v: Version) => v.version_number === 1) || versionList[versionList.length - 1];
          if (initial) {
            const res = await fetch(`http://localhost:5000/api/versions/${initial.version_id}/snapshot`);
            const snap = await res.json();
            setInitialSnapshot(snap);
          }
        }
      } catch (e) {
        console.error('Failed to fetch versions:', e);
        setVersions([]);
      }
      setLoading(false);
    };
    
    fetchVersions();
    setActiveSnapshot(null);
    setInitialSnapshot(null);
  }, [artifactId]);

  const handleLoadVersion = async (versionId: string) => {
    setLoadingVersion(versionId);
    try {
      const res = await fetch(`http://localhost:5000/api/versions/${versionId}/snapshot`);
      const snapshot = await res.json();
      setActiveSnapshot(snapshot);
      
      if (onLoadSnapshot) {
        onLoadSnapshot(snapshot);
      }
      
      if (onCompareVersions && initialSnapshot) {
        onCompareVersions(snapshot, initialSnapshot);
      }
    } catch (e) {
      console. error('Failed to load snapshot:', e);
    }
    setLoadingVersion(null);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
        Loading versions...
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">
        No version history available. 
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-500">
        {versions.length} version{versions.length !== 1 ? 's' : ''} found
      </div>
      
      <ul className="space-y-2 max-h-48 overflow-y-auto">
        {versions.map((v, index) => (
          <li 
            key={v.version_id} 
            className={`flex justify-between items-center text-sm p-2 rounded ${
              activeSnapshot?. version_id === v.version_id 
                ? 'bg-blue-50 border border-blue-200' 
                : 'bg-gray-50 hover:bg-gray-100'
            }`}
          >
            <div className="flex flex-col">
              <span className="font-medium flex items-center gap-2">
                v{v.version_number || versions.length - index}
                {index === versions.length - 1 && (
                  <span className="text-xs bg-green-100 text-green-700 px-1 rounded">Initial</span>
                )}
              </span>
              <span className="text-xs text-gray-500">
                {new Date(v.timestamp).toLocaleString()}
              </span>
            </div>
            <button
              onClick={() => handleLoadVersion(v.version_id)}
              disabled={loadingVersion === v. version_id}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                activeSnapshot?.version_id === v.version_id
                  ?  'bg-blue-600 text-white'
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              } disabled:opacity-50`}
            >
              {loadingVersion === v.version_id ? '.. .' : 
               activeSnapshot?.version_id === v.version_id ? 'Loaded' : 'Load'}
            </button>
          </li>
        ))}
      </ul>

      {activeSnapshot && (
        <div className="mt-3 p-3 bg-gray-50 rounded border text-xs space-y-3">
          {activeSnapshot.snapshot.change && (
            <div className="p-2 bg-red-50 border border-red-200 rounded">
              <h4 className="font-semibold text-red-700 mb-1">🔴 Change Made:</h4>
              <p className="text-red-600">
                <strong>{activeSnapshot.snapshot. change.type. replace('_', ' ').toUpperCase()}</strong>
              </p>
              <p className="text-red-600">
                {activeSnapshot.snapshot. change.source} → {activeSnapshot.snapshot.change.target}
              </p>
            </div>
          )}
          
          {/* Initial version indicator */}
          {activeSnapshot.is_initial && (
            <div className="p-2 bg-green-50 border border-green-200 rounded">
              <h4 className="font-semibold text-green-700">✅ Initial Baseline</h4>
              <p className="text-green-600 text-xs">This is the original state when first loaded. </p>
            </div>
          )}

          {/* Connections/Relationships */}
          <div>
            <h4 className="font-semibold mb-2">Graph State:</h4>
            
            {/* For Blocks */}
            {activeSnapshot.snapshot.connections && (
              <div className="space-y-1">
                <p><strong>Outgoing:</strong> {activeSnapshot.snapshot.connections. outgoing?. join(', ') || 'None'}</p>
                <p><strong>Incoming:</strong> {activeSnapshot. snapshot.connections.incoming?.join(', ') || 'None'}</p>
                <p><strong>Satisfies:</strong> {activeSnapshot.snapshot.connections. satisfies?.join(', ') || 'None'}</p>
              </div>
            )}
            
            {/* For Requirements */}
            {activeSnapshot.snapshot. relationships && (
              <div className="space-y-1">
                <p><strong>Derives From:</strong> {activeSnapshot.snapshot.relationships.derives_from?. join(', ') || 'None'}</p>
                <p><strong>Derived By:</strong> {activeSnapshot. snapshot.relationships.derived_by?.join(', ') || 'None'}</p>
                <p><strong>Linked Blocks:</strong> {activeSnapshot.snapshot. relationships.satisfies?. join(', ') || 'None'}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}