---
description: "Create Jira work items for scenario migration template with strict AC handling and hierarchy linking."
alwaysApply: false
---

# Rule: Jira Scenario Migration Template

Use this rule when the user asks to create Jira items for scenario migration from the standard template.

## Required Inputs

- `projectKey`
- `epicKeyForFeatures`
- scenario metadata list (one entry per scenario)

If any required input is missing, stop and ask.

## Template Shape (Scenario)

- 1 Feature template row per scenario
- 1 Story template row per scenario
- 15 Sub-task template rows per scenario

Template mapping:

- Feature: `Feature`, `Feature Description`, `Feature Acceptance Criteria`
- Story: `Story`, `Story Description`
- Sub-task: `Sub-Task`, `Sub-Task Description`, `Sub-Task Acceptance Criteria`

Placeholder replacement:

- Replace `SCENARIO_NAME` with the scenario name for the current branch.

## Mandatory Tool Sequence (per scenario)

1. Create Feature:
   - Call `JiraCreateFeature` with:
     - `projectKey`
     - `summary = mapped Feature`
     - `description = mapped Feature Description`
     - `epicLink = epicKeyForFeatures`
2. Set Feature acceptance criteria:
   - Call `JiraSetAcceptanceCriteria` on created feature key.
3. Validate Feature acceptance criteria:
   - Call `JiraGetAcceptanceCriteria`.
   - If empty or mismatch, retry set once, then mark branch failed.
4. Create Story via `JiraCreateStory`.
5. Link Story to Feature via `JiraSetDependency`:
   - `linkType = "Relates"`
   - `inwardIssueKey = storyKey`
   - `outwardIssueKey = featureKey`
   - This creates a neutral relationship between Story and Feature.
   - If Jira rejects the link type, use the exact configured issue-link type name from that Jira instance (name must match exactly).
6. Only if link succeeds, create 15 sub-tasks via `JiraCreateSubtask` with:
   - `parentKey = storyKey`
   - `description = mapped Sub-Task Description` only
7. For each sub-task:
   - Call `JiraSetAcceptanceCriteria` with mapped sub-task AC.
   - Validate using `JiraGetAcceptanceCriteria`.

## Strict AC and Description Rules

- AC must never be merged into description.
- Feature AC and Sub-task AC must be written through `JiraSetAcceptanceCriteria` only.
- Sub-task description must not include AC text.

## Description Bullet Formatting

- If source description has point-wise lines, convert each non-empty line to Jira bullet format with `* ` prefix before create/update.

## Count Validation

If scenarios = `S`:

- Features = `S`
- Stories = `S`
- Sub-tasks = `15 * S`

Return expected vs actual counts and list failed keys/actions if any.
