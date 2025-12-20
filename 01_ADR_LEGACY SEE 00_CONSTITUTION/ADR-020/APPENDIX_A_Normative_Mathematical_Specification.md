# ADR-020 Appendix A — Normative Mathematical Specification

**Classification:** BINDING REFERENCE
**Parent Document:** ADR-020_2026_PRODUCTION_Autonomous_Cognitive_Intelligence.md
**Version:** 2026.PROD.1
**Date:** 08 December 2025

---

## A.1 Search-in-the-Chain Formalization

### A.1.1 Dynamic Plan Evolution

Let $P_t$ denote the research plan at step $t$. After retrieval $R_t$:

$$P_{t+1} = f(P_t, R_t, Q)$$

Where:
- $Q$ is the original query
- $f$ is the plan update function
- $R_t$ contains retrieved evidence at step $t$

**Constraint:** If $R_t$ contradicts premise($P_0$), then:
$$P_{t+1} = \text{REPLAN}(Q, R_t)$$

### A.1.2 Retrieval-Interleaved Reasoning

The cognitive loop alternates between:
1. **Think:** Generate intermediate reasoning $\theta_t$
2. **Search:** Issue query $q_t = g(\theta_t, P_t)$
3. **Integrate:** Update belief state $B_{t+1} = h(B_t, R_t)$

---

## A.2 InForage Logic — Information Gain Economics

### A.2.1 Expected Information Gain

For query $q$ with cost $c(q)$:

$$\text{EIG}(q) = H(X) - \mathbb{E}[H(X | R_q)]$$

Where:
- $H(X)$ is current uncertainty over hypothesis space
- $R_q$ is the expected retrieval result

### A.2.2 Query Selection Criterion

ACI selects query $q^*$ such that:

$$q^* = \arg\max_q \frac{\text{EIG}(q)}{c(q)}$$

Subject to:
- $c(q) \leq B_{\text{remaining}}$ (budget constraint)
- $\text{EIG}(q) \geq \epsilon_{\min}$ (minimum gain threshold)

### A.2.3 Stopping Criterion

ACI MUST terminate search when:

$$\max_q \frac{\text{EIG}(q)}{c(q)} < \tau_{\text{stop}}$$

Where $\tau_{\text{stop}}$ is the cost-effectiveness threshold defined by STIG.

---

## A.3 IKEA Protocol — Knowledge Arbitration

### A.3.1 Claim Classification Function

For any claim $C$ in ACI output:

$$\text{class}(C) = \begin{cases}
\text{INTERNAL} & \text{if } C \in \mathcal{K}_{\text{parametric}} \\
\text{EXTERNAL} & \text{if } C \notin \mathcal{K}_{\text{parametric}}
\end{cases}$$

### A.3.2 Citation Requirement

For all EXTERNAL claims:
$$\forall C : \text{class}(C) = \text{EXTERNAL} \implies \exists \text{source}(C)$$

**Violation:** Any EXTERNAL claim without source triggers Class B Governance Violation.

### A.3.3 Parametric Knowledge Boundary

$\mathcal{K}_{\text{parametric}}$ includes ONLY:
- Logical reasoning steps
- Mathematical derivations
- Definitional knowledge
- Syntactic transformations

$\mathcal{K}_{\text{parametric}}$ EXCLUDES:
- Market data
- Price information
- News events
- Company fundamentals
- Economic indicators

---

## A.4 Uncertainty Quantification

### A.4.1 Epistemic Uncertainty Measure

For hypothesis $h$ given evidence $E$:

$$U(h | E) = 1 - \max_i P(h_i | E)$$

### A.4.2 Abort Threshold

ACI MUST abort if:
$$U(h | E) > 0.20$$

And reclassify output as `Hypothesis` requiring verification.

### A.4.3 Confidence Calibration

ACI confidence scores must satisfy:
$$\mathbb{E}[\mathbf{1}_{h = h_{\text{true}}} | \text{conf}(h) = p] = p$$

Calibration is validated by VEGA quarterly.

---

## A.5 Causal Inference Framework

### A.5.1 Causal Graph Construction

ACI outputs directed acyclic graph $G = (V, E)$ where:
- $V$ = findings/variables
- $E$ = causal relationships with strength $w_{ij}$

### A.5.2 Evidence Chain

For causal claim $X \to Y$:
$$\text{evidence}(X \to Y) = \{(s_1, r_1), (s_2, r_2), ..., (s_n, r_n)\}$$

Where $(s_i, r_i)$ pairs source with relevance score.

### A.5.3 Contradiction Detection

If $\exists e_1, e_2 \in E$ such that:
$$\text{direction}(e_1) \neq \text{direction}(e_2) \land \text{overlap}(e_1, e_2) > 0.5$$

Then ACI MUST flag explicit contradiction in output.

---

## A.6 Computational Complexity Bounds

### A.6.1 Search Depth Limit

Maximum recursion depth $D_{\max}$ by DEFCON:

| DEFCON | $D_{\max}$ |
|--------|-----------|
| 5 | 10 |
| 4 | 5 |
| 3 | 2 |
| 2-1 | 0 (disabled) |

### A.6.2 Token Budget

Per-query token ceiling:
$$T_{\text{query}} \leq 8192 \text{ tokens}$$

Per-session token ceiling:
$$T_{\text{session}} \leq 100000 \text{ tokens}$$

### A.6.3 Latency SLA

Research cycle latency:
$$L_{\text{cycle}} \leq 30000 \text{ ms}$$

Individual retrieval latency:
$$L_{\text{retrieval}} \leq 5000 \text{ ms}$$

---

## A.7 State Hash Integration (ADR-018)

### A.7.1 State Snapshot Requirement

Before reasoning step $t$:
$$\text{hash}_t = \text{SHA256}(\text{state}_t)$$

### A.7.2 Output Validation

All ACI outputs must include:
```json
{
  "state_hash": "<hash_t>",
  "timestamp": "<ISO8601>",
  "reasoning_steps": [...],
  "confidence": <float>
}
```

Outputs without valid state_hash are rejected by FINN.

---

## A.8 Cost Accounting (ADR-012 Integration)

### A.8.1 API Cost Model

$$\text{cost}_{\text{total}} = \sum_{i} c_{\text{api}}(q_i) + \sum_{j} c_{\text{llm}}(r_j)$$

### A.8.2 Budget Enforcement

Daily ACI budget ceiling:
$$B_{\text{daily}} \leq \$50.00$$

Per-session ceiling:
$$B_{\text{session}} \leq \$5.00$$

STIG enforces via `api_budget_log` table.

---

*Document Hash: To be computed upon registration*
*Appendix Classification: NORMATIVE BINDING*
