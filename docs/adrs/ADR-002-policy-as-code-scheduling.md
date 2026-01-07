# ADR-002: Policy-as-Code for Carbon-Aware Scheduling

## Status
Accepted

## Context
The scheduler must make routing decisions (FAST/ECO/DEFER) based on carbon intensity and job urgency. These decisions need to be:
- Transparent and auditable (responsible AI requirement)
- Tunable without code changes
- Traceable to specific policy rules
- Documented for compliance and explainability

Hard-coding thresholds and rules in Python would make the system opaque and difficult to audit or adjust.

## Decision
Implement policy-as-code using YAML (`policy.yaml`):
- **Thresholds**: `low: 200`, `high: 400` (gCO2/kWh) define carbon intensity bands
- **Rules**: Ordered list of condition → mode mappings with `policy_rule_id` identifiers
- **Guardrails**: `max_deferral_seconds: 600` prevents indefinite deferral

The scheduler loads `policy.yaml` at startup, evaluates rules in priority order, and records `policy_rule_id` + `decision_reason` in job metadata. This enables the `/jobs/{id}/explain` endpoint to provide full decision traceability.

## Consequences

### Positive
- **Transparency**: Policy is human-readable and version-controllable
- **Tunability**: Adjust thresholds/rules without redeploying code
- **Traceability**: Every decision includes `policy_rule_id` linking to the rule that triggered it
- **Explainability**: `/explain` endpoint can reconstruct decision rationale from stored metadata
- **Responsible AI**: Clear audit trail for carbon-aware decisions
- **Separation of Concerns**: Policy logic separated from scheduling infrastructure

### Negative
- **No Runtime Updates**: Policy changes require container restart (acceptable for checkpoint)
- **Limited Expressiveness**: Simple condition language; complex logic requires code changes
- **No Validation**: YAML syntax errors only discovered at runtime
- **Single Policy**: One policy file per scheduler instance (no per-tenant policies)

## Alternatives Considered
1. **Hard-coded Rules**: Simple but opaque, requires code changes for tuning
2. **Database-backed Policies**: Enables runtime updates but adds complexity and persistence layer
3. **External Policy Service**: Maximum flexibility but introduces network dependency and latency
4. **JSON Schema**: More structured but less human-readable than YAML

## Links
- Policy Definition: `policy.yaml`
- Policy Loading: `services/scheduler/main.py` (`load_policy()`, `apply_policy()`)
- Decision Recording: `services/scheduler/main.py` (`process_job()` sets `policy_rule_id`, `decision_reason`)
- Explainability: `services/api/main.py` (`GET /jobs/{id}/explain`)
- Container Packaging: `services/scheduler/Dockerfile` (copies `policy.yaml`)

