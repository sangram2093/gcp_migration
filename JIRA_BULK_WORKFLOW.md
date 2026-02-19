# Jira Bulk Workflow (Template + Metadata)

This script creates Jira Features, Stories, and Sub-tasks directly from:

1. A template Excel (`jira_board_tasks.xlsx` style)
2. A metadata JSON file

It is designed for large volume execution (1000+ issues) with retry and resume support.

## Files

- Script: `scripts/jira_bulk_from_template.py`
- Sample metadata: `scripts/jira_bulk_metadata.example.json`

## Install dependencies

```bash
python -m pip install requests openpyxl
```

## Required metadata fields

- `projectKey`
- `epicKeyForFeatures`
- `surveillanceName`
- `feeds` (array)
- `scenarios` (array)

Optional:

- `labels` (array)
- `linkType` (default: `Relates`)
- `jira` object (url/email/token/authMode)
  - `authMode`: `bearer` (default, same as built-in), `basic`, or `auto`
  - `apiVersion`: `2` (default, same as built-in) or `3`

## Run (dry run first)

```bash
python scripts/jira_bulk_from_template.py \
  --template jira_board_tasks.xlsx \
  --metadata scripts/jira_bulk_metadata.example.json \
  --jira-url https://your-company.atlassian.net \
  --jira-email your.user@company.com \
  --jira-token your_api_token \
  --state-file .jira_bulk_state.json \
  --dry-run
```

Auth debug (safe):

```bash
python scripts/jira_bulk_from_template.py \
  --template jira_board_tasks.xlsx \
  --metadata scripts/jira_bulk_metadata.example.json \
  --auth-debug \
  --dry-run
```

This prints only:
- resolved Jira URL
- auth mode
- whether email is present
- token length

Token value is never printed.

## Run (actual create)

```bash
python scripts/jira_bulk_from_template.py \
  --template jira_board_tasks.xlsx \
  --metadata scripts/jira_bulk_metadata.example.json \
  --jira-url https://your-company.atlassian.net \
  --jira-email your.user@company.com \
  --jira-token your_api_token \
  --state-file .jira_bulk_state.json
```

## Behavior

- Feed migration:
  - Creates 1 Feature (if at least one feed exists)
  - Creates 1 Story per feed
  - Creates 9 sub-tasks per feed story (based on template rows)
- Scenario migration:
  - Creates 1 Feature per scenario
  - Creates 1 Story per scenario
  - Creates 15 sub-tasks per scenario story (based on template rows)
- Stories are linked to their Feature using Jira issue links.
- Sub-tasks are created under their Story (`parentKey`).
- Acceptance criteria are written as a separate field (`Acceptance criteria` custom field), not merged into description.

## Reliability for large runs

- API retries for 429/5xx/network errors
- Text sanitization for quotes/newlines/control characters
- Checkpoint file (`--state-file`) supports resume/restart without recreating completed issues
- Link-type resolution (`name`/`inward`/`outward`) for better compatibility across Jira instances

## Notes

- Default template split is first 10 rows for feed and next 15 for scenario. Override with:
  - `--feed-rows`
  - `--scenario-rows`
- The script expects the template to contain these columns:
  - `Feature`
  - `Feature Description`
  - `Feature Acceptance Criteria`
  - `Story`
  - `Story Description`
  - `Sub-Task`
  - `Sub-Task Description`
  - `Sub-Task Acceptance Criteria`
- Credential precedence:
  - CLI args (`--jira-url`, `--jira-email`, `--jira-token`, `--jira-auth-mode`)
  - env vars (`JIRA_URL`, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_AUTH_EMAIL`, `JIRA_API_TOKEN`, `JIRA_TOKEN`, `JIRA_PAT`, `JIRA_AUTH_MODE`, `JIRA_API_VERSION`)
  - metadata `jira` object
