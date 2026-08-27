# Cost Model

The analyzer separates token cost from process cost.

## Evidence classes

- `measured`: numeric counts supplied by normalized client events.
- `derived`: counts computed from scoped local artifacts such as files, lines, or repeated test runs.
- `estimated`: explicit proxy values derived from artifact size when no measured count exists.
- `missing`: evidence that is unavailable or unreadable.

## Cost categories

- Product value: work that directly changes the plugin behavior or package contract.
- Required process: planning, review, verification, and reporting that the workflow explicitly requires.
- Rework: follow-up work caused by defects, review findings, or failed verification.
- Avoidable overhead: repeated context, verbose logs, waiting, or duplicated work that evidence supports.

## Guardrails

- Never convert waiting time into token counts.
- Never fabricate exact totals from artifact size proxies.
- Preserve aggregate numbers while redacting secret-like values.
- Report confidence and limitations alongside every estimate.
