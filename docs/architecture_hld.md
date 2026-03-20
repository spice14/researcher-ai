# ScholarOS — High-Level Architecture Diagram

```mermaid
graph TB
    %% ============================================================
    %% STYLING
    %% ============================================================
    classDef user fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    classDef orchestrator fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    classDef service fill:#FFF3E0,stroke:#E65100,stroke-width:1.5px,color:#BF360C
    classDef agent fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#4A148C
    classDef store fill:#ECEFF1,stroke:#37474F,stroke-width:1.5px,color:#263238
    classDef output fill:#E0F7FA,stroke:#00695C,stroke-width:1.5px,color:#004D40
    classDef cap fill:#FFF9C4,stroke:#F57F17,stroke-width:1px,color:#E65100

    %% ============================================================
    %% USER LAYER
    %% ============================================================
    USER["Researcher<br/>(Undergrad / Grad / PhD)"]:::user

    %% ============================================================
    %% INTERFACE LAYER
    %% ============================================================
    subgraph INTERFACE["Interface Layer"]
        CLI["CLI Tool<br/>ingest · analyze · inspect · trace"]:::orchestrator
        API["FastAPI<br/>(future)"]:::orchestrator
    end

    %% ============================================================
    %% ORCHESTRATION LAYER
    %% ============================================================
    subgraph ORCH["Orchestration Layer"]
        direction TB
        ORCHESTRATOR["MCP Orchestrator<br/>DAG Executor · Pause/Resume<br/>Session Management · Trace Logging"]:::orchestrator
        WORKFLOWS["Workflow Definitions<br/>FULL_ANALYSIS · LITERATURE_MAP<br/>CONTRADICTION_ONLY · HYPOTHESIS_TEST"]:::orchestrator
    end

    %% ============================================================
    %% CAPABILITY LAYER (5 Locked Capabilities)
    %% ============================================================
    subgraph CAPS["Five Core Capabilities"]
        direction TB

        subgraph CAP1["CAP 1: Literature Mapping"]
            MAPPING["Mapping Service<br/>HDBSCAN Clustering<br/>LLM Cluster Labeling<br/>Paper Ranking"]:::service
        end

        subgraph CAP2["CAP 2: Contradiction & Consensus"]
            EXTRACTION["Claim Extraction"]:::service
            NORMALIZATION["Normalization"]:::service
            CONTRADICTION["Contradiction Engine"]:::service
            BELIEF["Belief Engine"]:::service
        end

        subgraph CAP3["CAP 3: Hypothesis & Critique"]
            HYPO["Hypothesis Agent"]:::agent
            CRITIC["Critic Agent"]:::agent
            LOOP["Bounded Iteration Loop<br/>Convergence Detection"]:::agent
        end

        subgraph CAP4["CAP 4: Multimodal Extraction"]
            MULTIMODAL["Multimodal Service<br/>Tables · Figures · Metrics"]:::service
        end

        subgraph CAP5["CAP 5: Proposal Assistant"]
            PROPOSAL["Proposal Service<br/>LLM Sections · LaTeX Export<br/>Citation Assembly"]:::service
        end
    end

    %% ============================================================
    %% FOUNDATION SERVICES
    %% ============================================================
    subgraph FOUNDATION["Foundation Services"]
        direction LR
        INGESTION["Ingestion Service<br/>PDF → Chunks"]:::service
        CONTEXT["Context Extraction<br/>Dataset · Task Mapping"]:::service
        RAG["RAG Service<br/>Semantic + Lexical"]:::service
        EMBEDDING["Embedding Service<br/>sentence-transformers"]:::service
        CONSOLIDATION["Consolidation Service"]:::service
    end

    %% ============================================================
    %% DATA LAYER
    %% ============================================================
    subgraph DATA["Persistent Data Layer"]
        direction LR
        CHROMA[("Chroma<br/>Vector Memory")]:::store
        SQLITE[("SQLite<br/>Metadata Memory")]:::store
        REDIS[("Redis<br/>Session Memory")]:::store
        TRACES[("JSON Traces<br/>Execution Provenance")]:::store
    end

    %% ============================================================
    %% LLM LAYER
    %% ============================================================
    subgraph LLM["Local LLM Infrastructure"]
        OLLAMA["Ollama<br/>qwen2.5:32b"]:::store
        STRANS["sentence-transformers<br/>all-MiniLM-L6-v2"]:::store
    end

    %% ============================================================
    %% OUTPUT ARTIFACTS
    %% ============================================================
    subgraph OUTPUTS["Research Artifacts"]
        direction LR
        CLUSTERMAP["ClusterMap<br/>(JSON)"]:::output
        CONTREPORT["Contradiction Report<br/>(JSON)"]:::output
        HYPOTHESES["Validated Hypotheses<br/>(JSON)"]:::output
        PROPOSALS["Research Proposals<br/>(Markdown · LaTeX)"]:::output
        EVIDENCE["Extracted Evidence<br/>(CSV · JSON)"]:::output
    end

    %% ============================================================
    %% CONNECTIONS
    %% ============================================================
    USER --> INTERFACE
    CLI --> ORCHESTRATOR
    API -.-> ORCHESTRATOR
    ORCHESTRATOR --> WORKFLOWS
    WORKFLOWS --> CAPS
    WORKFLOWS --> FOUNDATION

    %% Foundation → Capabilities
    INGESTION --> CONTEXT
    CONTEXT --> EXTRACTION
    INGESTION --> MAPPING
    EXTRACTION --> NORMALIZATION
    NORMALIZATION --> CONTRADICTION
    CONTRADICTION --> BELIEF
    BELIEF --> LOOP
    MAPPING --> LOOP

    %% Agent Loop
    LOOP --> HYPO
    LOOP --> CRITIC
    HYPO --> CRITIC
    CRITIC --> HYPO

    %% Post-Agent
    LOOP --> CONSOLIDATION
    CONSOLIDATION --> PROPOSAL
    INGESTION --> MULTIMODAL
    MULTIMODAL --> PROPOSAL

    %% Data Layer
    INGESTION --> CHROMA
    INGESTION --> SQLITE
    RAG --> CHROMA
    EMBEDDING --> CHROMA
    ORCHESTRATOR --> REDIS
    ORCHESTRATOR --> TRACES
    MAPPING --> CHROMA

    %% LLM
    HYPO --> OLLAMA
    CRITIC --> OLLAMA
    MAPPING --> OLLAMA
    PROPOSAL --> OLLAMA
    EMBEDDING --> STRANS

    %% Outputs
    MAPPING --> CLUSTERMAP
    CONTRADICTION --> CONTREPORT
    LOOP --> HYPOTHESES
    PROPOSAL --> PROPOSALS
    MULTIMODAL --> EVIDENCE
```

## Legend

| Color | Layer |
|-------|-------|
| Green | User / Researcher |
| Blue | Orchestration & Interface |
| Orange | Deterministic MCP Services |
| Purple | Agentic Reasoning (LLM-backed) |
| Grey | Data Stores & Infrastructure |
| Teal | Output Artifacts |
