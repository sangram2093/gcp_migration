# Jira Epic Health Workflow (dbSAIcle)

This workflow produces a professional, consistent Epic Health report by analyzing an Epic and its child issues. It uses existing Jira tools in dbSAIcle and leaves the final scoring thresholds configurable per team or person.

## Purpose

- Provide an objective, repeatable view of Epic progress and risk.
- Surface red/amber drivers early (overdue items, inactivity, blocked items).
- Reduce status-chasing by using evidence from Jira activity and comments.
- Publish a clean report for PMs, BAs, leads, and stakeholders.

## Inputs (Required)

- Epic key (example: `ABC-1234`)
- Reporting window (example: last 14 days for activity checks)
- Scoring thresholds (see "Scoring Guidelines")

## Tools Used

- `jira_searchJiraIssuesWithJql`
- `jira_getJiraStatus`
- `jira_getJiraDueDate`
- `jira_getJiraPlannedStartDate`
- `jira_getJiraPlannedEndDate`
- `jira_getJiraComments`
- `jira_getJiraActivity`
- `jira_getLastWorklog` (optional)
- `jira_addComment` (optional, for posting report)

## Step 1: Confirm Epic and Child Issue Relationship

Different Jira setups use different relations. Choose the JQL that fits your instance:

- Company-managed Epic Link field:
  - `"Epic Link" = EPIC-KEY`
- Team-managed parent relationship:
  - `parent = EPIC-KEY`

If your Jira has multiple projects in one Epic, include project keys:
- `"Epic Link" = EPIC-KEY AND project in (ABC, DEF)`

## Step 2: Get Child Issues

Run `jira_searchJiraIssuesWithJql` using the selected JQL. This returns the list of child issues (stories, tasks, bugs, subtasks).

If you have more than 50 children, split the query by:
- `issuetype in (Story, Task, Bug, Sub-task)`
- or by project key
- or by status groups

## Step 3: Collect Epic-Level Data

For the Epic:
- Status: `jira_getJiraStatus`
- Due date: `jira_getJiraDueDate`
- Planned start/end: `jira_getJiraPlannedStartDate`, `jira_getJiraPlannedEndDate`
- Recent activity: `jira_getJiraActivity` (limit 10 to 20)
- Recent comments: `jira_getJiraComments` (limit 5 to 10)

## Step 4: Collect Child Issue Data

For each child issue:
- Status: `jira_getJiraStatus`
- Due date: `jira_getJiraDueDate`
- Planned start/end: `jira_getJiraPlannedStartDate`, `jira_getJiraPlannedEndDate`
- Recent activity: `jira_getJiraActivity` (limit 5 to 10)
- Recent comments: `jira_getJiraComments` (limit 3 to 5)
- Last worklog (optional): `jira_getLastWorklog`

## Step 5: Assess Health Drivers (Evidence-Based)

Analyze each child issue for:

- Overdue risk:
  - Due date in the past
- Near-term risk:
  - Due date within X days
- Inactivity risk:
  - No activity or comment in the last Y days
- Blocked or stalled status:
  - Status in (Blocked, On Hold, In Review too long)
- Scope or dependency risk:
  - Many open subtasks or unresolved dependencies

## Step 6: Scoring Guidelines (Configurable)

Use these as a default and customize per team:

- RED:
  - Any overdue critical story
  - More than 20% children overdue
  - No activity on top 3 critical items for > 14 days
- AMBER:
  - Due soon within 7 days and low activity
  - 10-20% items overdue
  - Comments indicate risk without mitigation
- GREEN:
  - No overdue items
  - Recent activity across critical items
  - Status distribution aligns with planned dates

## Step 7: Produce the Epic Health Report

Use the following format for a professional, consistent report.

---

# Epic Health Report

## Summary

- Epic: `EPIC-KEY` - `Epic Title`
- Report date: `YYYY-MM-DD`
- Overall status: `[GREEN | AMBER | RED]`
- Rationale (1-2 lines):
  - Example: "Two critical stories are overdue and inactive for 15 days."

## Snapshot

- Epic status: `In Progress`
- Planned start/end: `YYYY-MM-DD` / `YYYY-MM-DD`
- Due date: `YYYY-MM-DD`
- Total child issues: `N`
- Open: `N` | In Progress: `N` | Done: `N`

## Key Risks (Top 5)

1) `STORY-123`: overdue by 6 days, no activity in 14 days  
2) `STORY-221`: blocked status, dependency unresolved  
3) `TASK-441`: due in 3 days, no recent updates  
4) `BUG-190`: high severity, not triaged  
5) `STORY-310`: scope changed, comments indicate risk  

## Recent Activity Highlights

- `STORY-456`: updated status to In Review (2 days ago)  
- `BUG-099`: fix branch merged (4 days ago)  
- `STORY-321`: BA clarified acceptance criteria (5 days ago)  

## Next Actions

- Owner to unblock `STORY-221` and confirm dependency ETA  
- Review `STORY-123` and decide replan vs escalation  
- Confirm if `TASK-441` should be descoped or reassigned  

## Recommendation

- If AMBER/RED: schedule a short triage with the Epic owner and relevant leads
- If GREEN: continue as planned, next review in 7 days

---

## Step 8 (Optional): Post the Report Back to Jira

If required, use `jira_addComment` on the Epic with the Summary, Key Risks, and Next Actions sections.

## Notes and Tips

- Use `jira_getJiraActivity` to detect last updates even if no comments exist.
- Keep activity lookback consistent (7 or 14 days).
- If the Epic uses custom fields for planned dates, confirm the field mapping first.

## Output Expectations

This workflow produces a clear, evidence-based report that can be reused weekly. It is intentionally configurable so each team can define what "Amber" and "Red" mean for their delivery context.
