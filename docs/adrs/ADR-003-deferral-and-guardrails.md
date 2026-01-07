# ADR-003: Job Deferral and Guardrails

## Status
Accepted

## Context
Carbon-aware scheduling must balance sustainability (waiting for low-carbon periods) with operational requirements (SLO compliance, preventing job starvation). Flexible jobs can be deferred, but critical jobs must execute promptly. Deferred jobs must not wait indefinitely.

## Decision
Implement deferral with two guardrails:

1. **Deferral Mechanism**: 
   - Jobs matching medium carbon + flexible urgency → `DEFER` mode
   - Stored in `queue:DEFERRED` (sorted set) with deadline timestamp as score
   - Released when: (a) carbon intensity drops below threshold ("green window"), or (b) deadline exceeded

2. **Guardrails**:
   - **Critical Job Override**: `urgency == "critical"` → never defer, force to ECO (or FAST) mode
   - **Max Deferral Window**: `max_deferral_seconds: 600` (10 minutes); expired deferred jobs forced to ECO

3. **Green Window Release**: When `carbon_intensity < thresholds["low"]`, all deferred jobs are immediately released and routed to FAST queue (optimal carbon conditions).

Guardrail overrides are recorded with `policy_rule_id` starting with `GUARDRAIL_` (e.g., `GUARDRAIL_CRITICAL_OVERRIDE`, `GUARDRAIL_MAX_DEFERRAL`) for transparency.

## Consequences

### Positive
- **SLO Compliance**: Critical jobs never deferred, ensuring predictable execution
- **Starvation Prevention**: Max deferral window prevents jobs from waiting indefinitely
- **Carbon Optimization**: Green window release maximizes carbon savings when conditions are favorable
- **Transparency**: Guardrail applications are recorded in job metadata (`policy_rule_id`, `decision_reason`)
- **Predictable Behavior**: Clear rules for when deferral is allowed vs. forced execution

### Negative
- **SLO Trade-offs**: Deferred jobs may experience higher latency (up to max_deferral_seconds)
- **Carbon vs. Latency**: Green window release may cause burst traffic when carbon drops
- **No Priority Within Deferred**: All deferred jobs released together (no fine-grained prioritization)
- **Fixed Deferral Window**: 10-minute max may be too short for some use cases, too long for others

## Alternatives Considered
1. **No Deferral**: Simpler but misses carbon optimization opportunities
2. **Infinite Deferral**: Maximum carbon savings but risks starvation and unpredictable SLOs
3. **Dynamic Deferral Window**: Based on job type/urgency, but adds complexity
4. **Priority Queue for Deferred**: More sophisticated but requires priority metadata and complex release logic

## Links
- Policy Definition: `policy.yaml` (guardrails section, `MEDIUM_FLEX_DEFER` rule)
- Guardrail Enforcement: `services/scheduler/main.py` (`enforce_guardrails()`)
- Deferred Job Release: `services/scheduler/main.py` (`check_deferred_jobs()`)
- Green Window Logic: `services/scheduler/main.py` (carbon intensity check in `check_deferred_jobs()`)
- Explainability: `services/api/main.py` (`GET /jobs/{id}/explain` shows `guardrail_applied` flag)

