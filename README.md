# Configuration Management for Model-Based Design of Software

**Team:** Issmale Bekri, Asray Gopa, Arjun Patel, Akhil Pallem

**Client:** Scott Meyers, Collins Aerospace

**Course:** COM S 402 - Senior Design Project

**Instructor:** Simanta Mitra

**TA:** Scott Song

**Fall 2025**

---

## Chapter 1 - Requirements

### 1.1 Purpose

Engineers using Cameo, Simulink, Git, and Python-based testing tools currently lack reliable cross-tool traceability across the system development lifecycle. While each tool provides strong domain-specific capabilities, the absence of an integrated traceability mechanism makes it difficult to understand how requirements propagate through models, code, and verification artifacts. This gap is typically addressed through manual processes such as spreadsheets or static trace matrices, which do not scale well and are prone to human error.

Certification processes in the aerospace domain require clearly defined baselines, documented version lineage, and robust impact analysis capabilities to demonstrate compliance. When traceability is incomplete or inconsistent, engineering teams face increased certification risk, longer review cycles, and reduced confidence in change decisions.

This project provides a unified system for tracking and analyzing lifecycle artifacts across traditionally siloed engineering platforms. By integrating requirements, models, and code into a single traceability framework, the system enables comprehensive impact analysis, improves development visibility, and supports streamlined certification readiness. The system is designed to serve as a trusted source of traceability evidence, reducing manual effort while increasing confidence in system-level changes.

### 1.2 Scope

The system includes the following functional areas:

**Requirements Ingestion**

Import and normalize SysML requirements from Cameo, including hierarchical parent–child relationships, requirement attributes, and existing traceability links. Imported requirements are represented as structured artifacts that can be queried and linked across the lifecycle.

**Model Ingestion**

Import Simulink model elements, including blocks, signals, and associated requirements. The system supports automated mapping between Simulink elements and generated C code functions, enabling traceability from requirements through executable implementations.

**Code and Test Linkage**

Automatically identify and link C source code functions to Python-based test procedures. This establishes bidirectional traceability between implementation and verification artifacts, enabling users to determine both which tests validate a given function and which functions satisfy a given requirement.

**Graph-Based Storage**

Store all artifacts and relationships within a Neo4j graph database using a normalized graph schema. The graph structure enables efficient traversal across artifacts, supports complex traceability queries, and allows relationships to evolve as the system changes.

**Impact Analysis**

Perform graph-based impact analysis to identify downstream effects of changes across requirements, models, code, and tests. This allows users to assess the scope of changes before implementation and supports informed decision-making during system evolution.

**Baseline and Version Tracking**

Create, store, and retrieve baseline snapshots containing all artifacts and relationships at a specific point in time. Baselines include version lineage information to support audits, certification activities, historical analysis, and regression investigation.

### 1.3 Definitions and Acronyms

**SysML** - Systems Modeling Language: a general-purpose modeling language used for systems engineering and requirements specification.

**Cameo** - Cameo Systems Modeler, a commercial SysML/UML modeling tool commonly used for requirements and system architecture management.

**Simulink** - A MATLAB-based graphical programming environment used for modeling, simulating, and analyzing dynamic systems.

**Neo4j** - A graph database management system used to store and query complex artifact relationships.

**Graph Schema** - The data model defines node types, relationship types, and properties within the Neo4j database.

**Artifact** - Any engineering deliverable, including requirements, model elements, source code functions, or test procedures.

**Baseline** - A snapshot of the system at a specific point in time, capturing all artifacts and relationships for reference, audit, or certification.

**Impact Analysis** - The process of identifying all downstream artifacts affected by a change through graph traversal.

**Version Lineage** - A historical record of how artifacts and relationships evolve over time, enabling traceability of system changes.

### 1.4 Users

The system is intended for the following user groups:

**Aerospace Engineers**

Primary users who develop and maintain requirements, models, and code. These users require intuitive visibility into cross-tool dependencies and the ability to assess the downstream impact of changes before modifying system artifacts. Common questions include determining which requirements are affected by a model change or which code functions implement a specific requirement.

**Software Integrators**

Users are responsible for coordinating and integrating components across the development lifecycle. These users require end-to-end visibility into how requirements flow through models, and code in order to evaluate system-level integration risks and understand the implications of interface or implementation changes.

**Certification Authorities**

Reviewers are responsible for validating compliance with certification standards. These users require access to complete traceability data, baseline snapshots, and version history to verify that all requirements are fully implemented, verified, and appropriately documented.

### 1.5 Constraints

The system must adhere to the following constraints:

**Tool Compatibility**

The system must integrate with existing Collins tools, including Cameo Systems Modeler, Simulink, and Git/GitLab without requiring modifications to those tools or changes to established engineering workflows.

**Neo4j Aura Database Requirement**

All graph storage operations and queries must be compatible with Neo4j Aura DB, including its cloud-hosted environment, security model, and supported query capabilities.

**GitLab Integration**

The system must operate within GitLab's API, authentication, and access control constraints when interacting with source code repositories and version histories.

**Performance Requirements**

The system must support large-scale aerospace projects containing thousands of requirements, model elements, code functions, and tests, while maintaining acceptable performance for queries, analysis, and visualization.

**Data Format Compatibility**

The system must support standard export formats from Cameo (XML, JSON) and Simulink (SLX, XML) without requiring proprietary plugins, extensions, or modifications to vendor tools.

### 1.6 Assumptions

The system design is based on the following assumptions:

- Source artifacts such as requirements, models, and code are version-controlled and accessible through standard exports or APIs provided by their respective tools.
- Users are proficient with their native engineering tools, including Cameo, Simulink, Git/GitLab, and Python-based testing frameworks.
- The system operates as a decision-support and analysis tool, providing traceability, visualization, and impact assessment without serving as an authoring or editing environment for source artifacts.
- Artifact ownership, access control, and approval processes remain governed by existing organizational policies and tool-specific permissions.

---

## Chapter 2 - Design

### 2.1 System Overview

Our system integrates four major engineering tools—Cameo (SysML), Simulink, and GitLab—into a unified configuration-management platform. Each tool outputs artifacts that flow through custom loaders into a Neo4j graph, where traceability, version history, and impact analysis are performed. The frontend visualizes these artifacts as an interactive graph.

**System Components:**

- **Cameo Loader** - extracts SysML requirements from Collins' Cameo access and exports them as JSON.
- **Simulink Loader** - uses the MATLAB Simulink Artifacts to extract blocks, hierarchy, and connections.
- **GitLab Loader** - retrieves relevant code artifacts and links them to model elements.
- **Backend (Flask)** - orchestrates loading, versioning, and retrieval of artifacts.
- **Neo4j Graph Database** - stores all artifacts, relationships, and version snapshots.
- **Frontend Visualization (Next.js + ReactFlow)** - renders nodes, traceability edges, hierarchy edges, and version-change highlights.

### 2.2 Architecture Breakdown

#### 2.2.1 Cameo Integration

**Purpose:**

Convert SysML requirements from Cameo into graph artifacts that can be linked to downstream models and code.

**Implementation Steps:**

1. Used Collins Aerospace Cameo access to download existing requirement models.
2. Exported the Cameo model to a consistent JSON format.
3. Processed the exported JSON using a custom parser that extracts:
   - requirement ID
   - name & description
   - parent–child structure
4. Created graph nodes for each requirement in Neo4j.
5. Preserved hierarchical relationships.
6. Ensured requirements have IDs for matching with Simulink, code, and tests.

#### 2.2.2 Simulink Integration

Represent Simulink model elements as graph artifacts and link them to upstream requirements.

**Implementation Steps:**

1. Used MATLAB Simulink Artifacts to open .slx files from the provided Simulink models.
2. Extracted blocks, block types, paths, subsystem hierarchy, and signal connections.
3. For each block, create a corresponding graph node with metadata (sid, name, block type).
4. Captured internal connections between blocks (in/out ports → edges).
5. Preserved hierarchy so that nested subsystems appear in the graph as parent–child structures.
6. Enabled these blocks to be linked later to code files and test artifacts.

#### 2.2.3 Git + Version History Integration

**A. GitLab Integration (Code Traceability)**

- Connected Simulink blocks to actual C functions found in the GitLab repository.
- Engineers can instantly view the relevant implementation code for a model block.
- Enables traceability chain: Requirement → Model Block → Code File → Test Procedure

**B. Graph-Based Version Control (Snapshot System)**

- A snapshot is created when a block or requirement changes.
- The snapshot stores:
  - incoming/outgoing connections
  - parent/child links
  - satisfies/derives-from relationships
- During comparison, differences are visualized:
  - Green nodes & green broken edges = new connection added
  - Red nodes/edges = root node dependency changed

#### 2.2.4 Neo4j Schema

**Node Types:**

- Requirement
- Block (Simulink)
- File (C)
- Test Case
- Version Snapshot

**Relationship Types:**

- requirement → requirement (hierarchy)
- block → block (signal flow)
- requirement → block (traceability link)
- block → code file (implementation)
- version snapshot → artifact (snapshot state)

These relationships power all analysis and visualization.

#### 2.2.5 Impact Analysis Engine

Impact analysis answers: "If this requirement changes, what downstream artifacts are affected?"

**Implementation:**

- Uses BFS/DFS traversal starting from a selected node.
- Tags all reachable descendants as "impacted".
- Highlighted visually in green in the UI.
- Implemented in the frontend using descendant lookup and edge traversal inside ArtifactTree.tsx.

#### 2.2.6 Baseline + Versioning

**Purpose:**

Capture the state of the system at any point in time.

**Functionality:**

- Creating a baseline stores the entire tree of artifacts under that root.
- Each version snapshot stores the relationships present at that time.
- The comparison panel highlights differences.
- Used during requirement changes or model updates.

### 2.3 API Documentation

#### GET /api/requirements

**Purpose:** Retrieve all requirements stored in the system, with optional filtering.

**Input:**
- `type` - filter by requirement type
- `search` - perform substring search

**Output:**
```json
[
  {
    "id": "REQ-001",
    "name": "System shall ...",
    "description": "...",
    "type": "HighLevel"
  }
]
```

#### GET /api/requirements/{req_id}

**Purpose:** Retrieve a single requirement and its full child hierarchy.

**Example Request:** `GET /api/requirements/REQ-001`

**Output:**
```json
{
  "id": "REQ-001",
  "name": "...",
  "children": [
    {
      "id": "REQ-001.1",
      "children": []
    }
  ]
}
```

#### GET /api/requirements/hierarchy

**Purpose:** Return the complete requirement tree (all root requirements and their descendants).

**Output:**
```json
[
  {
    "id": "REQ-1",
    "name": "Top-level Requirement",
    "children": [...]
  }
]
```

#### GET /api/requirements/stats

**Purpose:** Return basic statistics about the requirement dataset.

**Output:**
```json
{
  "total": 120,
  "types": 4,
  "with_children": 89,
  "with_traces": 42
}
```

#### GET /api/code-file?file_path=...

**Purpose:** Retrieve C code extracted from Simulink auto-generated code.

**Input (Query Parameters):**
- `file_path` - path to the extracted file
- `raw=true` - optional, return plain text only

**Output:**
```json
{
  "model_name": "ControllerModel",
  "file_path": "R2025b/.../Controller.c",
  "content": "int step() { ... }",
  "line_count": 350
}
```

#### POST /api/code-references/update

**Purpose:** Update or attach code-reference metadata to a Simulink block.

Used when connecting blocks to specific lines of code.

**Input:**
```json
{
  "block_sid": "34",
  "block_path": "<Root>/Gain",
  "file_path": "Controller.c",
  "ref_index": 0,
  "line": 124,
  "code": "y = x * 5;"
}
```

**Output:**
```json
{
  "success": true
}
```

#### GET /api/artifacts/<artifact_id>/versions

**Purpose:** Return all version snapshots associated with a specific artifact.

**Example Request:** `GET /api/artifacts/block_123/versions`

**Output:**
```json
{
  "artifact_id": "block_123",
  "versions": [
    {
      "version_id": "v1",
      "timestamp": "2025-01-10T15:30:00Z"
    },
    {
      "version_id": "v2",
      "timestamp": "2025-01-17T09:12:44Z"
    }
  ]
}
```

#### GET /api/blocks/with-versions

**Purpose:** Return all Simulink blocks along with their latest version metadata.

**Output:**
```json
{
  "blocks": [
    {
      "id": "block_12",
      "name": "Gain",
      "latest_version": "v4"
    }
  ]
}
```

#### GET /api/requirements/with-versions

**Purpose:** Return all requirements with their latest version information.

**Output:**
```json
{
  "requirements": [
    {
      "id": "REQ-1",
      "name": "System shall...",
      "latest_version": "v3"
    }
  ]
}
```

#### GET /api/versions/lineage/<artifact_id>

**Purpose:** Retrieve the full version lineage (ancestor chain) of a given artifact.

**Example Request:** `GET /api/versions/lineage/REQ-12`

**Output:**
```json
{
  "artifact_id": "REQ-12",
  "lineage": [
    { "version_id": "v1", "parent": null },
    { "version_id": "v2", "parent": "v1" },
    { "version_id": "v3", "parent": "v2" }
  ]
}
```

#### POST /api/artifacts/<artifact_id>/snapshot

**Purpose:** Create a new version snapshot for a specific artifact.

**Example Request:** `POST /api/artifacts/block_45/snapshot`

**Output:**
```json
{
  "status": "snapshot_created",
  "artifact_id": "block_45",
  "version_id": "v7",
  "timestamp": "2025-02-01T10:22:19Z"
}
```

#### POST /api/versions/load

**Purpose:** Load all version metadata from storage into the graph.

**Input:**
```json
{
  "source": "version_storage"
}
```

**Output:**
```json
{
  "status": "versions_loaded",
  "count": 128
}
```

#### GET /api/versions/stats

**Purpose:** Return system-wide statistics about versions.

**Output:**
```json
{
  "total_versions": 128,
  "versions_by_type": {
    "Block": 82,
    "Requirement": 41,
    "File": 5
  }
}
```

### 2.4 UI Design

**Main Components:**

- **ArtifactTree:**
  - Renders nodes and edges
  - Handles expand/collapse of Simulink parent
  - Highlights impacted nodes
  - Manages version visualization states

- **Node Details Panel:** Displays metadata and code snippets.

- **Version Comparison Panel:** Shows added/removed/modified edges and nodes.

- **Traceability Edges:** Requirements ↔ Blocks ↔ Code

**Visualization Features**

- Automatic graph layout using Dagre
- Color-coded node types
- Version colors
- Interactive zoom and drag
- Smoothstep edges with arrows
- Mini-map and controls

---

## Chapter 3 - Work Done (Per Team Member)

### Issmale Bekri

**Work Completed:**

- Impact analysis logic for frontend page
- Parsed Cameo data and loaded into JSON files
- Added version history tracking from endpoint for saved changes
- Built impact analysis queries and highlighted nodes changed
- Created ReactFlow visualization components
- Endpoint for cross tool connections between Cameo and Simulink

### Akhil Pallem

**Work Completed:**

- Layout of the front end page and styling
- Created ReactFlow visualization components for tree based structure and connections
- Figma Board sketches for front end design
- Version control end point to keep track of saved changes for all changes
- Loaded Cameo data into Neo4j database with existing relationships and data connections
- Created Cameo endpoints to attach to frontend nodes

### Asray Gopa

**Work Completed:**

- Formalized project architecture
- Set up Simulink nodes and hierarchy with existing relationships
- Set up Neo4j Database / Initialize Python Flask Server
- Condensed impact analysis and making the links UI adjustments
- Implemented tree caching to reduce load time
- Fetching GitLab code changes for version control
- Cross-platform child node connections between Simulink and Cameo

### Arjun Patel

**Work Completed:**

- Parsed Simulink data
- Setup connections and endpoints in Neo4j database for Simulink parsed files (.SLX)
- Endpoints to pull Simulink information
- Added manual linking for Cameo and Simulink data
- Recreated impact analysis page on main page and condensed into one
- Connected Simulink generated code to the nodes that produced it

### Technologies we each learned:

- Neo4j
- Cameo
- Simulink
- Python Flask
- GitLab API
- Next.js
- Reactflow

---

## Chapter 4 - Results Achieved

### 4.1 Major Deliverables

- Built custom loaders that export/parse Cameo SysML requirements and extract Simulink blocks, hierarchy, connections and generated code
- Implemented impact analysis using graph traversal from a selected node to tag downstream descendants as impacted, and visualized impacts directly in the UI.
- Implemented a Neo4j-backed trace model with defined node/relationship types, plus a snapshot-based versioning system that supports lineage tracking and diff visualization across versions.
- Delivered a ReactFlow based interactive graph UI with details panels, version comparison, Dagre auto-layout, minimap/controls, and traceability edges connecting requirements, blocks, and code.

### 4.2 Client Value Delivered

- The system captures baselines/snapshots and preserves relationships at a point in time, enabling auditors/engineers to show what changed and when.
- Delivered an end-to-end chain from Requirement to Model Block to Code File Procedure, making relationships explicit rather than manual/tribal knowledge.
- Engineers can select a requirement or model element and automatically identify impacted downstream artifacts via traversal, with direct UI highlighting to speed decision-making.

### 4.3 Limitations

- Parsing and graph-writing time increases with model size and connectivity, especially for deep hierarchies and dense signal networks.
- Some Simulink code generation styles may not fully parse correctly.

---

## Appendix - Demo Slides

*Demo slides available in project repository.*

---

## Repository Link

[https://git.las.iastate.edu/SeniorDesignComS/2025fall/402c/sd02_configuration_management](https://git.las.iastate.edu/SeniorDesignComS/2025fall/402c/sd02_configuration_management)

## Setup Instructions

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Neo4j AuraDB credentials are already configured inside `config.py`. No additional database setup is required unless credentials change.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://localhost:3000`.

## Contact

**Client:** Scott Meyers, Collins Aerospace  
Email: [scott.meyers@collins.com](mailto:scott.meyers@collins.com)

**Team:** Iowa State University – COM S 402 – Senior Design
