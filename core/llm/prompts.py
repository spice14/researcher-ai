"""Versioned prompt templates for agent LLM calls.

Every prompt has a version string. Prompts are logged with every LLM call
per AGENTS.md §5 requirements.
"""

# ───────────────────────────────────────────────────────────────────
# Hypothesis Agent Prompts
# ───────────────────────────────────────────────────────────────────

HYPOTHESIS_SYSTEM_PROMPT = """\
You are a rigorous research hypothesis generator. You propose testable, \
literature-grounded hypotheses based on structured evidence inputs.

Rules:
- Every hypothesis must be testable and falsifiable.
- Assumptions must be explicit.
- Independent and dependent variables must be declared.
- You must explain what makes the hypothesis novel.
- Confidence must reflect evidence strength honestly.
- Respond ONLY with the JSON object requested. No markdown fences, no explanation."""

HYPOTHESIS_SYSTEM_PROMPT_VERSION = "hypothesis_system_v1.0.0"

HYPOTHESIS_GENERATE_PROMPT = """\
Given the following structured evidence, generate a research hypothesis.

== CONTRADICTIONS ==
{contradictions}

== CONSENSUS GROUPS ==
{consensus_groups}

== CLAIMS ==
{claims}

== USER CONSTRAINTS ==
{constraints}

Respond with a JSON object with exactly these fields:
{{
  "statement": "<testable hypothesis statement>",
  "rationale": "<why this hypothesis follows from the evidence>",
  "assumptions": ["<assumption 1>", "<assumption 2>"],
  "independent_variables": ["<variable being manipulated>"],
  "dependent_variables": ["<variable being measured>"],
  "boundary_conditions": ["<where hypothesis applies>"],
  "novelty_basis": "<what makes this novel given existing literature>",
  "known_risks": ["<risk or limitation>"],
  "confidence": "<low|medium|high>",
  "grounding_claim_ids": ["<claim_id from the input claims>"]
}}"""

HYPOTHESIS_GENERATE_PROMPT_VERSION = "hypothesis_generate_v1.0.0"


HYPOTHESIS_REVISE_PROMPT = """\
Revise the following hypothesis based on the critique provided.

== CURRENT HYPOTHESIS ==
{hypothesis}

== CRITIQUE ==
Severity: {severity}
Weak assumptions: {weak_assumptions}
Counter-evidence: {counter_evidence}
Suggested revisions: {suggested_revisions}

Respond with a JSON object with exactly these fields:
{{
  "statement": "<revised testable hypothesis statement>",
  "rationale": "<updated rationale incorporating critique>",
  "assumptions": ["<updated assumption 1>", "<updated assumption 2>"],
  "independent_variables": ["<variable being manipulated>"],
  "dependent_variables": ["<variable being measured>"],
  "boundary_conditions": ["<updated boundary conditions>"],
  "novelty_basis": "<updated novelty explanation>",
  "known_risks": ["<updated risks including critique insights>"],
  "confidence": "<low|medium|high>",
  "grounding_claim_ids": ["<claim_id from original evidence>"],
  "revision_changes": "<what changed and why>"
}}"""

HYPOTHESIS_REVISE_PROMPT_VERSION = "hypothesis_revise_v1.0.0"


# ───────────────────────────────────────────────────────────────────
# Critic Agent Prompts
# ───────────────────────────────────────────────────────────────────

CRITIC_SYSTEM_PROMPT = """\
You are a rigorous scientific critic. Your job is to find weaknesses, \
unsupported assumptions, and gaps in research hypotheses.

Rules:
- Challenge every assumption with evidence where possible.
- Identify missing controls or confounders.
- Suggest concrete, actionable revisions.
- Be specific: cite claim IDs and evidence snippets.
- Severity must honestly reflect the impact of the weakness.
- Respond ONLY with the JSON object requested. No markdown fences, no explanation."""

CRITIC_SYSTEM_PROMPT_VERSION = "critic_system_v1.0.0"

CRITIC_EVALUATE_PROMPT = """\
Critically evaluate the following hypothesis using the available evidence.

== HYPOTHESIS ==
Statement: {statement}
Assumptions: {assumptions}
Independent variables: {independent_variables}
Dependent variables: {dependent_variables}
Boundary conditions: {boundary_conditions}
Novelty basis: {novelty_basis}
Supporting claims: {supporting_claim_ids}

== AVAILABLE COUNTER-EVIDENCE ==
{counter_evidence_chunks}

== CONTRADICTION CONTEXT ==
{contradiction_context}

Respond with a JSON object with exactly these fields:
{{
  "weak_assumptions": ["<assumption that is poorly supported>"],
  "counter_evidence_snippets": [
    {{
      "source_id": "<paper or chunk ID>",
      "page": <page number or 1>,
      "snippet": "<text that contradicts the hypothesis>",
      "retrieval_score": <0.0 to 1.0>
    }}
  ],
  "suggested_revisions": ["<concrete revision suggestion>"],
  "severity": "<low|medium|high|critical>",
  "reasoning": "<brief explanation of the critique>"
}}"""

CRITIC_EVALUATE_PROMPT_VERSION = "critic_evaluate_v1.0.0"


# ───────────────────────────────────────────────────────────────────
# Proposal Section Prompts (Phase 4)
# ───────────────────────────────────────────────────────────────────

PROPOSAL_NOVELTY_PROMPT = """\
Write a compelling research novelty statement for the following hypothesis.

HYPOTHESIS: {hypothesis}
SUPPORTING CLAIMS: {claims}
IDENTIFIED GAPS: {gaps}

Write 2-3 focused paragraphs. Be specific and grounded in the evidence."""

PROPOSAL_NOVELTY_PROMPT_VERSION = "proposal_novelty_v1.0.0"

PROPOSAL_METHODOLOGY_PROMPT = """\
Write a methodology section for the following research proposal.

HYPOTHESIS: {hypothesis}
ASSUMPTIONS: {assumptions}
INDEPENDENT VARIABLES: {independent_vars}
DEPENDENT VARIABLES: {dependent_vars}

Describe a concrete experimental design, evaluation metrics, and validation approach in 2-3 paragraphs."""

PROPOSAL_METHODOLOGY_PROMPT_VERSION = "proposal_methodology_v1.0.0"

PROPOSAL_OUTCOMES_PROMPT = """\
Write an expected outcomes section for the following research proposal.

HYPOTHESIS: {hypothesis}
KNOWN RISKS: {risks}

Write 2 paragraphs: (1) predicted outcomes and significance, (2) risk mitigation strategies."""

PROPOSAL_OUTCOMES_PROMPT_VERSION = "proposal_outcomes_v1.0.0"

# ───────────────────────────────────────────────────────────────────
# Cluster Label Prompt (Phase 2)
# ───────────────────────────────────────────────────────────────────

CLUSTER_LABEL_PROMPT = """\
Given the following representative excerpts from a cluster of research papers, \
generate a concise 3-7 word label that captures the research theme.

EXCERPTS:
{excerpts}

Respond with ONLY the label text, no punctuation, no quotes."""

CLUSTER_LABEL_PROMPT_VERSION = "cluster_label_v1.0.0"
