# ServiceNow RTB Incident Triage Workflow

This workflow helps RTB teams triage an incident using linked problem tickets,
knowledge articles, and similar incidents from the last two months. It also
creates a structured L2 investigation checklist to avoid unnecessary back-and-forth.

## Step 1: Get the incident id from the user

Ask for the incident number (INC...) or sys_id and confirm it is assigned to RTB.

Tool: `servicenow_get_incident`

Example tool call:
```json
{
  "incident_id": "INC0012345",
  "fields": [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "assignment_group",
    "assigned_to",
    "knowledge",
    "kb_knowledge",
    "u_knowledge_article",
    "problem",
    "problem_id",
    "u_problem"
  ],
  "display_value": true
}
```

## Step 2: Check for linked Problem or Knowledge

If the incident contains a problem reference, fetch it. If a KB reference exists,
fetch the KB article content.

Problem tools:
- `servicenow_get_problem`
- `servicenow_get_problem_logs`
- `servicenow_get_problem_history` (sys_history_set/sys_history_line)

KB tools:
- `servicenow_get_kb_article`

Example tool calls:
```json
{
  "problem_id": "PRB0012345",
  "display_value": true
}
```
```json
{
  "problem_id": "PRB0012345",
  "elements": ["work_notes", "comments"],
  "order": "desc",
  "limit": 50
}
```
```json
{
  "problem_id": "PRB0012345",
  "order": "desc",
  "limit": 100
}
```
```json
{
  "kb_id": "KB0012345",
  "include_content": true
}
```

## Step 3: Analyze problem/KB availability

Determine whether the incident already references:
- a problem ticket, or
- a knowledge article.

This will decide the branch you follow in Step 5.

## Step 4: Search past incidents (last 2 months)

Search short_description and description for the job name or error text.
Limit to the last 60 days to avoid stale matches.

Tool: `servicenow_list_incidents`

Example tool call:
```json
{
  "sysparm_query": "sys_created_on>=javascript:gs.daysAgoStart(60)^short_descriptionLIKEcontrol-m^ORdescriptionLIKEcontrol-m^assignment_group.nameLIKERTB",
  "limit": 50,
  "display_value": true
}
```

If needed, use log search for deeper matching:
```json
{
  "query": "JOB_ABC_123",
  "elements": ["work_notes", "comments"],
  "incident_state": "6",
  "assignment_group_name": "RTB",
  "include_incidents": true,
  "max_incidents": 25
}
```

## Step 5: Branch based on findings

### i) Problem ticket available
1. Review the problem ticket details and history.
2. If a KB is referenced in the problem ticket, open it.
3. Ask the user to perform KB steps **one by one** and confirm after each step.
4. Update the incident with evidence of completed steps before closing or reassigning.

Use `servicenow_add_comment` with `is_work_note=true` to capture evidence.

### ii) KB available in the incident
1. Open the KB article.
2. Ask the user to perform KB steps **one by one** and confirm after each step.
3. Update the incident with evidence of completed steps before closing or reassigning.

### iii) No problem/KB, but similar past incidents exist
If this is the 3rd or 4th occurrence (>=3 similar incidents in the last two months):
1. Summarize the incident with evidence from logs and past resolutions.
2. Update the incident with the L2 investigation summary.
3. Assign it to the senior RTB person for deeper analysis.

### iv) First failure, no past incidents
1. Execute the L2 investigation checklist below.
2. Update the incident with findings.
3. Seek senior RTB advice if blockers remain.

## Step 6: L2 investigation checklist (attach to incident work notes)

Use this checklist to ensure consistent L2 investigation:
- Confirm the failing job name, schedule, and environment.
- Analyze the failure logs and capture the exact error signature.
- Identify the impacted workstream/project and business owner.
- Check last successful run time and compare with current failure.
- Verify any recent changes (deployments, config, infra, credentials).
- Validate dependencies (downstream systems, DB, network, external APIs).
- If logs are unclear, ask the user to provide logs so AI can assist.
- Document all findings in incident work notes.

Example tool call to update evidence:
```json
{
  "incident_id": "INC0012345",
  "comment": "L2 checklist: reviewed logs, identified error signature, checked last success, verified dependencies. User confirmed KB steps 1-3 completed.",
  "is_work_note": true
}
```

## Step 7: Close or reassign with evidence

Before closing or assigning, ensure the incident includes:
- KB steps performed (if applicable)
- L2 investigation summary
- Any recommended next actions for RTB/L3 teams
