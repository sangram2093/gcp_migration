---
description: "Create Jira Features, Stories, and Sub-tasks for feed/scenario migration from a fixed template and user metadata."
alwaysApply: false
---

# Rule: Jira Feed and Scenario Migration Template Execution

Use this rule when the user asks to generate Jira work items for surveillance feed/scenario migration from the `jira_board_tasks.xlsx` template pattern described below.

## Template Assumptions (from provided specification)

The template has these logical columns:

- `Feature`
- `Feature Description`
- `Feature Acceptance Criteria`
- `Story`
- `Story Description`
- `Sub-Task`
- `Sub-Task Description`
- `Sub-Task Acceptance Criteria`

Template structure assumptions:

- Total logical rows: 25
- Feed migration template rows: first 10
  - Represents: 1 Feature, 1 Story, 9 Sub-tasks
- Scenario migration template rows: next 15
  - Represents: 1 Feature, 1 Story, 15 Sub-tasks
- Merged-cell behavior means feature/story fields may be blank in repeated rows. Treat blanks as the previous non-empty value (forward-fill behavior).

Placeholders:

- Replace `SURVEILLANCE_NAME` with actual surveillance name for feed migration context.
- Replace `SCENARIO_NAME` with actual scenario name for scenario migration context.

## Required User Inputs

Collect or confirm these before creating any Jira item:

- `projectKey` (Jira project key)
- `epicKeyForFeatures` (Epic to attach created Features via Epic Link)
- Feed metadata list (each feed should contain surveillance context + feed identity)
- Scenario metadata list (each scenario should contain scenario identity)

If any required value is missing, stop and ask for it.

## Jira Tools To Use

Primary tools:

- `JiraCreateFeature`
- `JiraCreateStory`
- `JiraCreateSubtask`
- `JiraSetAcceptanceCriteria`
- `JiraSetDependency`

Validation/readback tools:

- `JiraSearchWithJql` (optional validation)
- `JiraGetDescriptionText` (optional validation)
- `JiraGetAcceptanceCriteria` (optional validation)

## Creation Logic

### A) Feed migration

For all feed entries under one surveillance migration batch:

1. Create one feed-migration Feature from the feed template feature row.
2. Set feature acceptance criteria using `JiraSetAcceptanceCriteria`.
3. For each feed in metadata:
   1. Create one Story under the same project.
   2. Link Story <-> Feature using `JiraSetDependency` (preferred link type: `Relates`).
   3. Create 9 Sub-tasks under that Story (from the feed sub-task template rows).
   4. Set sub-task acceptance criteria for each sub-task using `JiraSetAcceptanceCriteria`.

### B) Scenario migration

For each scenario in metadata:

1. Create one scenario-specific Feature from scenario template feature row.
2. Set feature acceptance criteria using `JiraSetAcceptanceCriteria`.
3. Create one Story for that scenario.
4. Link Story <-> Feature using `JiraSetDependency` (preferred link type: `Relates`).
5. Create 15 Sub-tasks under that Story (from scenario template sub-task rows).
6. Set sub-task acceptance criteria for each sub-task using `JiraSetAcceptanceCriteria`.

## Field Mapping Rules

- Feature summary: from `Feature` with placeholder replacement.
- Feature description: from `Feature Description`.
- Feature acceptance criteria: from `Feature Acceptance Criteria`.
- Story summary: from `Story` with placeholder replacement.
- Story description: from `Story Description`.
- Sub-task summary: from `Sub-Task`.
- Sub-task description: from `Sub-Task Description`.
- Sub-task acceptance criteria: from `Sub-Task Acceptance Criteria`.

## Count Validation Rules

Given:

- `F = number of feeds`
- `S = number of scenarios`

Expected outputs:

- Features = `1 (feed feature if F > 0) + S`
- Stories = `F + S`
- Sub-tasks = `9*F + 15*S`

Example (`F=2`, `S=2`):

- Features = `1 + 2 = 3`
- Stories = `2 + 2 = 4`
- Sub-tasks = `18 + 30 = 48`

## Execution Safeguards

- Do not create duplicate issues for the same run context. Before creating, search existing items by deterministic summary and current migration label.
- If dependency link creation fails due to Jira link-type mismatch, continue item creation and report the exact failed link operation for manual correction.
- After creation, return a structured summary:
  - Created feature keys
  - Created story keys
  - Created sub-task keys grouped by story
  - Any failed operations with reason

## Output Contract

Always provide:

1. A dry-run plan with exact counts before creation.
2. A creation log grouped by Feed migration and Scenario migration.
3. A final reconciliation section:
   - Expected counts vs actual counts
   - Missing items
   - Retry recommendations (if any)
