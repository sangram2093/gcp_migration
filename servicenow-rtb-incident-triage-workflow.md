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

## Step 2: Check for linked Knowledge Article in the incident

Some incidents store a Knowledge Article reference (often labeled *Knowledge Article*). If present, use it directly instead of searching.

Tool: `servicenow_get_incident`

Example tool call:
```json
{
  "incident_id": "INC0012345",
  "display_value": true,
  "fields": ["sys_id", "number", "short_description", "description", "knowledge", "kb_knowledge", "u_knowledge_article"]
}
```

If a KB number or sys_id is present, fetch the KB article:
```json
{
  "kb_id": "KB0012345",
  "include_content": true
}
```

## Step 3: Pull incident logs (work notes + comments)

Use the incident sys_id/number to fetch the latest logs. The tool resolves the sys_id and queries logs using `element_id` (with fallback to `documentkey`) for compatibility.

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

## Step 4: Search past incidents by job name in description/short description

For Control-M or scheduled jobs, the job name often appears in short description or description. Search these fields first.

Tool: `servicenow_list_incidents`

Example tool call:
```json
{
  "query": "control-m JOB_ABC_123",
  "assignment_group_name": "RTB",
  "state": "6"
}
```

## Step 5: Search past incidents by log text

If metadata search is not enough, search historical logs. Filter to resolved/closed incidents and the RTB assignment group.

Tool: `servicenow_search_incident_logs`

Example tool call:
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

## Step 7: Search the knowledge base (if not already linked)

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

## Step 8: Check for related Problem Tasks (PRB)

If the logs mention a PRB number (e.g., `PRB0012345`), pull the problem task and its logs.

Tool: `servicenow_get_problem_task`
```json
{
  "problem_task_id": "PRB0012345",
  "display_value": true
}
```

Tool: `servicenow_get_problem_task_logs`
```json
{
  "problem_task_id": "PRB0012345",
  "elements": ["work_notes", "comments"],
  "order": "desc",
  "limit": 50
}
```

If no PRB number is available, search by keywords:
```json
{
  "query": "control-m JOB_ABC_123",
  "limit": 10
}
```

## Step 9: Create or update Knowledge Base (if missing)

If no relevant KB exists, create a new article (or update an existing draft).

Tool: `servicenow_create_kb_article`
```json
{
  "short_description": "Control-M job failure: JOB_ABC_123",
  "text": "<h2>Symptoms</h2><p>...</p><h2>Resolution</h2><p>...</p>",
  "kb_knowledge_base": "<KB_BASE_SYS_ID>",
  "kb_category": "<KB_CATEGORY_SYS_ID>",
  "workflow_state": "draft"
}
```

Tool: `servicenow_update_kb_article`
```json
{
  "kb_id": "KB0012345",
  "text": "<h2>Updated Resolution</h2><p>...</p>"
}
```

## Step 10: Provide the resolution plan

Summarize:
- Current incident context
- Similar past incidents + their resolution steps
- KB steps (if available)
- Problem task details (if found)

If no strong match exists, provide a best-effort checklist and suggest creating a KB article after resolution.

