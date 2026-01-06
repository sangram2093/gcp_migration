# ServiceNow RTB Incident Triage Workflow

This workflow helps RTB teams triage a new incident by searching similar past incidents and knowledge base (KB) articles using incident logs, job names, and error strings.

## Step 1: Get the current incident details

Use the incident number or sys_id and confirm it is assigned to RTB.

Tool: `servicenow_get_incident`

Example tool call:
```json
{
  "incident_id": "INC0012345",
  "fields": ["sys_id", "number", "short_description", "description", "state", "assignment_group", "assigned_to"]
}
```

## Step 2: Pull incident logs (work notes + comments)

Use the incident sys_id/number to fetch the latest logs. The tool will resolve the sys_id and query logs using `element_id` (with a fallback to `documentkey`) for compatibility.

Tool: `servicenow_get_incident_logs`

Example tool call:
```json
{
  "incident_id": "INC0012345",
  "elements": ["work_notes", "comments"],
  "order": "desc",
  "limit": 50
}
```

## Step 3: Extract key identifiers from logs

Identify job names, error codes, hostnames, and application names. These become your search terms.

Common examples:
- Job names: `control-m`, `abc_job_123`
- Errors: `ORA-`, `timeout`, `connection refused`
- Systems: `host01`, `svc-xyz`

## Step 4: Search past incidents by log text

Search across historical logs for matches. Filter to resolved/closed incidents and the RTB assignment group.

Tool: `servicenow_search_incident_logs`

Example tool call:
```json
{
  "query": "control-m",
  "elements": ["work_notes", "comments"],
  "incident_state": "6",
  "assignment_group_name": "RTB",
  "include_incidents": true,
  "max_incidents": 25
}
```

## Step 5: Search incidents by metadata

Search by short description/description as a backup or additional signal.

Tool: `servicenow_list_incidents`

Example tool call:
```json
{
  "query": "control-m timeout",
  "assignment_group_name": "RTB",
  "state": "6"
}
```

## Step 6: Pull resolution steps from similar incidents

For top matches, read incident details and extract `close_notes` and `close_code`.

Tool: `servicenow_get_incident`

Example tool call:
```json
{
  "incident_id": "INC0009876",
  "fields": ["number", "short_description", "close_code", "close_notes", "state"]
}
```

## Step 7: Search the knowledge base

Use the same keywords to locate KB articles with fix steps.

Tool: `servicenow_list_kb_articles`

Example tool call:
```json
{
  "query": "control-m timeout",
  "kb_base_name": "RTB",
  "active": true
}
```

Then fetch the full article content (Tool: `servicenow_get_kb_article`):
```json
{
  "kb_id": "KB0012345",
  "include_content": true
}
```

## Step 8: Provide the resolution plan

Summarize:
- Current incident context
- Similar past incidents + their resolution steps
- KB steps (if available)

If no strong match exists, provide a best-effort checklist and suggest creating a KB article after resolution.

