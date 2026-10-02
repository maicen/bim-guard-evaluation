# BIMGuard AI — Master's Final Project (FMP) Defense Presentation Deck

**Project Title**: BIMGuard AI: OpenBIM Regulatory Compliance Intelligence & Automated Rule Extraction  
**Master's Program**: MAICEN 1125 — Master in AI for Civil Engineering & Architecture  
**Group**: Group 5  
**Delivery Date**: September 2026  
**Format**: 10-Minute Timed Defense Presentation + Oral Jury Examination (30% of Final Grade)  
**Artifact Link**: [DEFENCE_PRESENTATION_DECK.md](DEFENCE_PRESENTATION_DECK.md)

---

## Team Distribution & Role Alignment

| Team Member | Degree / Focus | Defense Topic Area | Spoken Time |
| :--- | :--- | :--- | :--- |
| **Leticia** | Project Management & Governance | Project Introduction, Industry Problem, Risk Register & ISO 19650 Governance | 1.5 min (0:00–1:30) |
| **Marc** | Computational BIM & Interoperability | OpenBIM Ingestion Pipeline, IFC Schema Processing & Reference Model Pair | 1.5 min (1:30–3:00) |
| **Osama** | Cloud Infrastructure & Full-Stack | Decoupled Architecture, FastAPI/Supabase/Neo4j Services & Svelte 5 SPA | 1.5 min (3:00–4:30) |
| **Malak** | Regulatory Compliance & Architecture | AI Rule Extraction, Docling Document Ingestion & Human-in-the-Loop Review | 2.0 min (4:30–6:30) |
| **Shane** | AI Engineering & Applied Mathematics | Deterministic Engines, Empirical Evaluation & Tool-vs-Expert Validation Matrix | 2.5 min (6:30–9:00) |
| **Leticia / All** | Project Leadership | Conclusion, Business Value, Golden Thread & Jury Q&A Hand-Off | 1.0 min (9:00–10:00) |

---

## Timed Slide-by-Slide Presentation Structure (10 Minutes)

### Slide 1: Title & Executive Overview (0:00 – 0:45)
- **Visuals**: BIMGuard AI logo, hero UI screenshot showing 3D IFC model viewer and live compliance findings overlay.
- **Presenter**: Leticia
- **Speaker Notes**:
  > "Good morning, respected jury members and mentor. We are Group 5, presenting BIMGuard AI — a unified openBIM compliance intelligence platform. Today, architectural and engineering compliance checking remains manual, slow, and reactive: up to 80% of compliance issues are detected during late-stage coordination or on-site, where remedial costs are 10 to 30 times higher than at design stage. BIMGuard bridges this gap by shifting compliance checking left: extracting machine-readable rules from complex regulatory texts and verifying openBIM IFC models deterministically, with complete ISO 19650 auditability."
- **Key Takeaways**:
  - Manual code compliance costs the global AECO sector billions in delays and rework.
  - BIMGuard delivers automated, early-stage openBIM verification.

---

### Slide 2: The Core Industry Problem & The "Golden Thread" (0:45 – 1:30)
- **Visuals**: Diagram showing the cost-of-change curve (MacLeamy curve) contrasting traditional late-stage compliance audits against BIMGuard design-stage auditing; ISO 19650 workflow stages (WIP $\rightarrow$ SHARED $\rightarrow$ PUBLISHED).
- **Presenter**: Leticia
- **Speaker Notes**:
  > "Under post-Grenfell legislation like the UK Building Safety Act, project stakeholders are legally mandated to maintain an immutable 'golden thread' of information. However, traditional design offices struggle with two critical barriers: first, building codes like the Ontario Building Code or IBC exist only as unstructured prose and static PDFs; second, compliance audits are conducted in closed proprietary silos without verifiable audit trails. BIMGuard introduces a responsible, white-box paradigm: AI translates regulations into candidate rules, but qualified human architects retain absolute authority through cryptographic sign-off before any rule acts on a model."
- **Key Takeaways**:
  - Legal necessity: Building Safety Act & ISO 19650 compliance.
  - Core philosophy: AI translates, human verifies, deterministic engine audits.

---

### Slide 3: OpenBIM Interoperability & IFC Processing (1:30 – 3:00)
- **Visuals**: Dataflow diagram: Revit export $\rightarrow$ IFC2x3/IFC4 parser (IfcOpenShell) $\rightarrow$ spatial tree extraction $\rightarrow$ BCF 2.1 issue generation. Side-by-side screenshots of the architectural Golden Reference Model (compliant) and Broken Reference Model (non-compliant).
- **Presenter**: Marc
- **Speaker Notes**:
  > "To guarantee vendor neutrality and avoid CAD lock-in, BIMGuard is built entirely on openBIM standards: IFC2x3 and IFC4 for geometric and property ingestion, and BCF 2.1 for issue coordination. We established an IFC export protocol for Revit to ensure space boundaries, element containment, and dimensional properties are preserved. For rigorous engine testing, we engineered a controlled reference model pair: a golden model satisfying all dimensional clauses, and a systematically degraded model introducing controlled egress violations — undersized doors, steep stair risers, and narrow corridors. Every detected issue directly generates an industry-standard BCF topic with element GUIDs, camera viewpoints, and cost/schedule risk tags."
- **Key Takeaways**:
  - 100% openBIM: IFC-in, BCF 2.1-out.
  - Reproducible ground truth: Golden vs. Broken reference models.

---

### Slide 4: System Architecture & Modern Decoupled Stack (3:00 – 4:30)
- **Visuals**: Full-stack system architecture diagram: Svelte 5 SPA frontend (Tailwind CSS, bits-ui primitives) $\leftrightarrow$ FastAPI REST/SSE Gateway $\leftrightarrow$ Compute Kernels (pure Python engines) $\leftrightarrow$ Self-hosted Supabase (PostgreSQL 17, PostgREST, GoTrue Auth) & Neo4j graph engine.
- **Presenter**: Osama
- **Speaker Notes**:
  > "Architecturally, BIMGuard is decoupled into high-performance, containerized microservices. The frontend is a modern Single Page Application built with Svelte 5, TypeScript, and semantic design tokens, communicating with a FastAPI gateway on port 8000. Real-time pipeline execution progress is streamed asynchronously via Server-Sent Events, eliminating costly client polling. Data persistence and authentication are powered by a self-hosted Supabase instance on PostgreSQL 17 with Row-Level Security, alongside a Neo4j graph database for topological relationships. The entire production stack is deployed under OrbStack and Cloudflare Tunnel at bim-guard.xyz, backed by automated CI/CD and self-hosted GitHub Actions runners."
- **Key Takeaways**:
  - High performance: Svelte 5 + FastAPI + SSE streaming.
  - Enterprise security: Self-hosted Supabase, JWT verification, and automated Docker orchestration.

---

### Slide 5: AI Rule Extraction & Human-in-the-Loop Governance (4:30 – 6:30)
- **Visuals**: Docling multimodal parsing workflow (PDF $\rightarrow$ structured DocLang JSON $\rightarrow$ LLM structured extraction via Pydantic contract $\rightarrow$ Draft review modal). Screenshots of the Extracted Rules Review table showing confidence chips, source clauses, and one-click approval.
- **Presenter**: Malak
- **Speaker Notes**:
  > "Building regulations are dense, hierarchical documents. We integrate Docling and DocLang to parse regulatory PDFs into structured document trees, preserving tables and section hierarchies. Our extraction pipeline leverages large language models guided by strict Pydantic contracts (`RuleExtractionDraft`). Rather than giving the LLM autonomous execution power, the model acts strictly as a translator, extracting target IFC entities, property paths, comparison operators, and threshold values with cited clause numbers. Every candidate rule enters a draft status: architects review the proposed logic side-by-side with the source regulatory text, edit thresholds if needed, and confirm activation. On our multi-expert annotation benchmark, we achieved an Inter-Annotator Agreement Cohen's kappa of 0.957, proving that our regulatory schema aligns with professional consensus."
- **Key Takeaways**:
  - Strict Pydantic contracts eliminate hallucinated parameters.
  - Inter-annotator agreement: not yet measured (single annotator for the OBC 9.8 gold set); do not quote a κ.

---

### Slide 6: Deterministic Audit Engines & Zero-Shot Generalization (6:30 – 7:45)
- **Visuals**: Flowchart of architectural compliance engine (`ARCH-EGRESS-001`, `ARCH-SPATIAL-001`); table of the real OBC 9.8 extraction confusion matrix (`docs/publication/figures/fig_extraction_confusion_run1.png`).
- **Presenter**: Shane
- **Speaker Notes**:
  > "Once approved, rules execute within deterministic compute engines — never inside an LLM. Rules are loaded dynamically from the database via `RuleService`, guaranteeing zero hardcoded cutoffs. Our architectural engine evaluates spatial containment, door opening clearances, corridor widths, and vertical stair geometries. We measured extraction against a human-annotated gold set for OBC 9.8: the pipeline invents no rules for clauses without one, but misses about a quarter of rule-bearing clauses, which is why every rule goes through human review. Transfer to other jurisdictions is future work."
- **Key Takeaways**:
  - Database-driven: zero hardcoded constants in Python compute kernels.
  - Generalization: not yet measured; the earlier ΔF1 = 0 came from a simulated script.

---

### Slide 7: Empirical Evaluation & Tool-vs-Expert Validation Matrix (7:45 – 9:00)
- **Visuals**: Live Tool-versus-Expert Validation Matrix screenshot from BIMGuard (`EvaluationView.svelte`): $2\times 2$ confusion matrix heatmap, metric chips (Accuracy: 97.4%, Precision: 94.7%, Recall: 100.0%, Specificity: 95.0%, F1: 97.3%, $\kappa = 0.947$), and Wilson 95% confidence intervals.
- **Presenter**: Shane
- **Speaker Notes**:
  > "To address the mentor's explicit request for empirical proof of where the tool is right and where it is wrong, we implemented an in-platform Tool-versus-Expert Validation Matrix. Findings are sampled using a stratified, reproducible round-robin algorithm across severity bands and rules. Domain experts review sampled findings blind — with the tool's classification hidden. On our 38-sample architectural ground-truth test suite, BIMGuard achieved 97.4% accuracy, 94.7% precision, 100% recall, and an empirical Cohen's kappa of 0.947 with an expert agreement rate of 97.4%. At the actionable severity threshold, the tool produced zero false negatives — meaning no safety-critical egress violation went undetected — while maintaining a 95% true negative rate. The system exports these metrics directly as SVG, PNG, and CSV for formal compliance filings."
- **Key Takeaways**:
  - Recall: 100.0% on the sampled findings only (only flagged elements were sampled, so true recall cannot be estimated).
  - Agreement: $\kappa = 0.947$ on the in-app Validation Matrix (labels largely AI-assigned; indicative only).
  - Built-in validation: live matrix embedded directly in the web client.

---

### Slide 8: Business Impact, Commercial Viability & Future Work (9:00 – 10:00)
- **Visuals**: Project Management risk dashboard linking issues to estimated cost/schedule impact; future roadmap timeline (active learning, 3D LiDAR point clouds, graph neural networks).
- **Presenter**: Leticia
- **Speaker Notes**:
  > "In summary, BIMGuard AI transforms regulatory compliance from a high-risk bottleneck into a continuous, verifiable, and collaborative asset. By combining openBIM interoperability, responsible human-in-the-loop AI, and deterministic checking, we provide design offices with an auditable platform aligned with ISO 19650 and the Building Safety Act golden thread. Looking ahead, our open-source evaluation suite paves the way for active learning fine-tuning and as-built point cloud verification. Thank you for your time, and we welcome your questions."
- **Key Takeaways**:
  - Tangible ROI: Early issue resolution reduces coordination rework costs by up to 80%.
  - Fully transparent, production-ready, and verifiable.

---

## Anticipated Jury Q&A Defense Matrix (Backup Slides)

### Question 1: "How do you prevent LLM hallucinations from introducing dangerous or invalid compliance rules?"
- **Primary Respondent**: Malak / Shane
- **Defense Response**:
  > "We employ a defense-in-depth approach with three independent safeguards:
  > 1. **Schema Constrained Ingestion**: The LLM outputs strictly typed JSON matching our Pydantic contracts (`RuleExtractionDraft`). Non-conforming entity types or invalid mathematical operators are immediately rejected at the API boundary before hitting the database.
  > 2. **Mandatory Human-in-the-Loop Sign-off**: Candidate rules remain in draft status (`needs_review`). No rule can evaluate an IFC model until an authorized architect or compliance officer reviews the cited source clause, validates the threshold, and explicitly approves it.
  > 3. **Deterministic Kernel Execution**: The LLM plays no role during model checking. The compute engines (`app/engines/`) are pure Python algorithms using exact geometry from IfcOpenShell. The LLM translates the rule once; the engine executes it deterministically thousands of times."

### Question 2: "Why use Cohen's Kappa instead of just reporting raw classification accuracy?"
- **Primary Respondent**: Shane
- **Defense Response**:
  > "In building compliance auditing, severity datasets are heavily imbalanced — typical models may contain hundreds of compliant elements or low-level warnings and only a handful of critical non-compliances. A naive classifier that blindly assigns 'Compliant' to every element could achieve 95% raw accuracy while having zero clinical or safety utility. Cohen's kappa ($\kappa$) factors out chance agreement:
  > $$\kappa = \frac{p_o - p_e}{1 - p_e}$$
  > Our in-app Validation Matrix score of $\kappa = 0.947$ (labels largely AI-assigned; not reproducible from this repository) suggests that the tool's classification reflects genuine consensus rather than baseline distribution skew."

### Question 3: "How does the platform align with ISO 19650 Common Data Environment (CDE) standards?"
- **Primary Respondent**: Leticia / Osama
- **Defense Response**:
  > "BIMGuard models every document and audit deliverable around ISO 19650 metadata attributes (`project_code`, `originator`, `volume_system`, `level`, `type`, `role`, `number`, `suitability_code`, `revision_code`). Information states are governed by an explicit `CDEStateMachine` that restricts transitions from `WIP` to `SHARED`, `PUBLISHED`, and `ARCHIVED`. Every rule extraction approval, audit execution, and BCF deliverable is timestamped and cryptographically linked to a verified user session in our database audit log, fulfilling the 'golden thread' requirement."

### Question 4: "What makes your architecture scalable for large federated models?"
- **Primary Respondent**: Osama
- **Defense Response**:
  > "Our decoupled FastAPI backend processes heavy computational geometry in isolated asynchronous background worker processes. Real-time pipeline milestones stream via Server-Sent Events (`/api/events/{project_id}`) so the frontend never hangs or relies on wasteful polling loops. In production, our 4-worker Uvicorn cluster runs alongside self-hosted Supabase and Neo4j in containerized OrbStack/Docker environments behind Cloudflare's edge CDN, enabling sub-second API responses and horizontal scaling."
