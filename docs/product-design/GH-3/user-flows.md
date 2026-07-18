# User Flows

schema_version: user-flows/v1
issue_id: GH-3

FLOW-001: Release intake and selection. The release operator opens the local console, confirms the Connected state, optionally saves a runtime bearer token in session storage, searches current releases, creates a release with title and version, then selects it from the semantic release table. Empty state appears before any release exists, validation errors focus the first invalid field, and offline state moves the top status chip and flash banner to an error state without hiding already-rendered context.

FLOW-002: Readiness validation. The operator moves a selected release from planned to validating, adds a required delivery gate, updates that gate from pending to passed or failed, and sees the gate clearance count update in the release table and detail panels. If the operator attempts ready before required gates are passed or waived, the domain returns a conflict and the UI keeps the selected release, displays the message, and leaves allowed next actions visible.

FLOW-003: Risk remediation to ready. The operator adds a risk with severity and blocking status, reviews it in the risk register, and transitions it through mitigated, accepted, or closed. Open blocking risks prevent ready status. Once all required gates are cleared and no blocking open risk remains, the operator can move the release to ready and verify the release status badge, table row, and meta area agree.

FLOW-004: Audit review and recovery. The operator switches between selected-release and all-release audit scopes, reviews ordered events with prior and new status, and uses audit history to reconstruct release, gate, and risk decisions. Read-only audit views remain available without mutation authorization. Unauthorized mutation attempts show a permission state, preserve current inputs, and allow the operator to save or clear the token before retrying.
