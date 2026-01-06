# ServiceNow Tools Guide

This guide covers the built-in ServiceNow tools in DbSaicle and how to use them with example prompts.

## Configuration

The tools read ServiceNow credentials from your config or environment variables.

Example `config.yaml`:

```yaml
servicenow:
  instanceUrl: "https://your-instance.service-now.com"
  timeout: 30
  auth:
    type: "basic"
    basic:
      username: "your-username"
      password: "your-password"
```

Auth options:
- `basic`: username/password
- `oauth`: clientId/clientSecret (+ optional username/password, tokenUrl)
- `api_key`: apiKey (+ optional headerName)

Environment variable fallbacks:
```
SERVICENOW_INSTANCE_URL
SERVICENOW_TIMEOUT
SERVICENOW_AUTH_TYPE=basic|oauth|api_key
SERVICENOW_USERNAME
SERVICENOW_PASSWORD
SERVICENOW_CLIENT_ID
SERVICENOW_CLIENT_SECRET
SERVICENOW_TOKEN_URL
SERVICENOW_API_KEY
SERVICENOW_API_KEY_HEADER
```

## Usage Notes

- You can just describe what you want in plain English; DbSaicle selects the tool.
- Some tools accept a **number** or a **sys_id**. If unsure, fetch the record first.
- For list tools, `query` generally accepts ServiceNow `sysparm_query` syntax.
- For incident listing, you can also use specialized filters like assignee email, cost center, and location.
- For `servicenow_list_incidents`, if you pass an email in `assigned_to`, it is treated as `assigned_to.email`.

## Incident Management Tools

### `servicenow_create_incident`
Required: `short_description`
Optional: `description`, `caller_id`, `category`, `subcategory`, `priority`, `impact`, `urgency`, `assigned_to`, `assignment_group`

Example prompts:
- "Create an incident: VPN access is down for APAC. Priority 2, impact high."
- "Open a new incident for user onboarding failure and assign to Network Ops."

### `servicenow_update_incident`
Required: `incident_id` (number or sys_id)
Optional: `short_description`, `description`, `state`, `category`, `subcategory`, `priority`, `impact`, `urgency`, `assigned_to`, `assignment_group`, `work_notes`, `close_notes`, `close_code`

Example prompts:
- "Update incident INC0012345 to state 2 and add work notes about the rollback."
- "Change priority and assign INC0012345 to jane.doe."

### `servicenow_add_comment`
Required: `incident_id`, `comment`
Optional: `is_work_note` (true to write work_notes instead of comments)

Example prompts:
- "Add a comment to INC0012345: We identified a misconfigured proxy."
- "Add a work note to INC0012345 that the fix is in testing."

### `servicenow_resolve_incident`
Required: `incident_id`, `resolution_code`, `resolution_notes`

Example prompts:
- "Resolve INC0012345 with resolution code 'Solved (Permanently)' and notes."

### `servicenow_list_incidents`
Optional filters: `state`, `assigned_to`, `assigned_to_email`, `assigned_to_name`,
`assigned_to_cost_center`, `assigned_to_cost_center_name`,
`assigned_to_location`, `assigned_to_location_name`,
`assignment_group`, `assignment_group_name`, `category`, `query`, `active`,
`sysparm_query`, plus `limit`/`offset`.

Example prompts:
- "List active incidents assigned to jane.doe@company.com."
- "Show incidents assigned to group name 'Network Ops' with state 2."
- "List incidents for cost center name 'Trading' and location name 'NYC'."
- "List incidents where short description mentions VPN."
- "List incidents assigned_to john.doe@company.com."

### `servicenow_get_incident`
Required: `incident_id` (number or sys_id)
Optional: `fields`, `display_value`, `exclude_reference_link`

Example prompts:
- "Get incident details for INC0012345 with display values."

### `servicenow_search_incident_logs`
Required: `query`
Optional: `incident_id`, `elements`, `limit`, `offset`, `include_incidents`,
`max_incidents`, `incident_state`, `incident_active`, `assignment_group`,
`assignment_group_name`, `sysparm_query`, `fields`, `incident_fields`

Example prompts:
- "Search incident logs for 'control-m' and include matching incident summaries."
- "Search logs for job ABC123 in resolved incidents for assignment group RTB."
- "Search incident logs for 'timeout' only in work_notes."

### `servicenow_get_incident_logs`
Required: `incident_id` (number or sys_id)
Optional: `elements`, `limit`, `offset`, `order_by`, `order`,
`include_incident`, `sysparm_query`, `fields`

Example prompts:
- "Get incident logs for INC0012345."
- "Get work_notes only for INC0012345 in descending order."

## Service Catalog Tools

### `servicenow_list_catalog_items`
Optional: `category`, `query`, `active`, `limit`, `offset`

Example prompts:
- "List active catalog items in category 6f1d... with 'laptop' in the name."

### `servicenow_get_catalog_item`
Required: `item_id` (sys_id)

Example prompts:
- "Get catalog item 2dfc... and show its variables."

### `servicenow_list_catalog_categories`
Optional: `query`, `active`, `limit`, `offset`

Example prompts:
- "List catalog categories with name containing 'IT'."

### `servicenow_create_catalog_category`
Required: `title`
Optional: `description`, `parent`, `icon`, `active`, `order`

Example prompts:
- "Create a catalog category 'Database Access' under parent 1a2b..."

### `servicenow_update_catalog_category`
Required: `category_id` (sys_id)
Optional: `title`, `description`, `parent`, `icon`, `active`, `order`

Example prompts:
- "Deactivate catalog category 1a2b... and set order to 500."

### `servicenow_move_catalog_items`
Required: `item_ids` (array), `target_category_id`

Example prompts:
- "Move catalog items [a1, b2, c3] to category 9f8e..."

### `servicenow_create_catalog_item_variable`
Required: `catalog_item_id`, `name`, `type`, `label`
Optional: `mandatory`, `help_text`, `default_value`, `description`, `order`,
`reference_table`, `reference_qualifier`, `max_length`, `min`, `max`

Example prompts:
- "Add a mandatory text variable 'cost_center' to item 2dfc..."

### `servicenow_list_catalog_item_variables`
Required: `catalog_item_id`
Optional: `include_details`, `limit`, `offset`

Example prompts:
- "List variables for catalog item 2dfc... with details."

### `servicenow_update_catalog_item_variable`
Required: `variable_id`
Optional: `label`, `mandatory`, `help_text`, `default_value`, `description`,
`order`, `reference_qualifier`, `max_length`, `min`, `max`

Example prompts:
- "Update variable 7abc... to make it mandatory and set label to 'Cost Center'."

### `servicenow_list_catalogs`
Optional: `query`, `active`, `limit`, `offset`

Example prompts:
- "List active catalogs."

## Knowledge Base Tools

### `servicenow_list_kb_articles`
Optional filters: `kb_number`, `kb_base`, `kb_base_name`, `kb_category`,
`kb_category_name`, `author`, `author_email`, `author_name`, `workflow_state`,
`active`, `query`, `sysparm_query`, plus `limit`/`offset`.

Example prompts:
- "List KB articles with number KB0012345."
- "List active KB articles in base name 'RTB' with workflow state published."
- "Search KB articles where the description mentions latency."

### `servicenow_get_kb_article`
Required: `kb_id` (number or sys_id)
Optional: `include_content`, `fields`, `display_value`, `exclude_reference_link`

Example prompts:
- "Get KB article KB0012345 with full content."
- "Get KB article KB0012345 without content."

### `servicenow_create_kb_article`
Required: `short_description`, `text`, `kb_knowledge_base`
Optional: `kb_category`, `workflow_state`, `author`, `active`

Example prompts:
- "Create a KB article for Control-M job failure in the RTB knowledge base."

### `servicenow_update_kb_article`
Required: `kb_id` (number or sys_id)
Optional: `short_description`, `text`, `kb_knowledge_base`, `kb_category`, `workflow_state`, `author`, `active`

Example prompts:
- "Update KB0012345 with the new resolution steps."

### `servicenow_list_kb_bases`
Optional: `query`, `active`, `limit`, `offset`

Example prompts:
- "List active knowledge bases."

### `servicenow_list_kb_categories`
Optional: `query`, `active`, `limit`, `offset`

Example prompts:
- "List knowledge base categories containing 'RTB'."

### `servicenow_list_kb_topics`
Optional: `query`, `active`, `limit`, `offset`

Example prompts:
- "List knowledge base topics."

## Change Management Tools

### `servicenow_create_change_request`
Required: `short_description`, `type`
Optional: `description`, `risk`, `impact`, `category`, `requested_by`,
`assignment_group`, `start_date`, `end_date`

Example prompts:
- "Create a normal change request for database patching next Friday."

### `servicenow_update_change_request`
Required: `change_id` (sys_id)
Optional: `short_description`, `description`, `state`, `risk`, `impact`,
`category`, `assignment_group`, `start_date`, `end_date`, `work_notes`

Example prompts:
- "Update change request 9f8e... to state 'implement' and add work notes."

### `servicenow_list_change_requests`
Optional: `state`, `type`, `category`, `assignment_group`, `timeframe`,
`query`, `limit`, `offset`

Timeframe values: `upcoming`, `in-progress`, `completed`

Example prompts:
- "List upcoming change requests for assignment group 1a2b..."

### `servicenow_get_change_request_details`
Required: `change_id` (number or sys_id)

Example prompts:
- "Get details for change CHG0012345 (include tasks)."

### `servicenow_add_change_task`
Required: `change_id` (sys_id), `short_description`
Optional: `description`, `assigned_to`, `planned_start_date`, `planned_end_date`

Example prompts:
- "Add a task to change 9f8e... for staging validation."

### `servicenow_submit_change_for_approval`
Required: `change_id` (sys_id)
Optional: `approval_comments`

Example prompts:
- "Submit change 9f8e... for approval with a short note."

### `servicenow_approve_change`
Required: `change_id` (sys_id)
Optional: `approver_id`, `approval_comments`

Example prompts:
- "Approve change 9f8e... with comment 'Reviewed and approved'."

### `servicenow_reject_change`
Required: `change_id` (sys_id), `rejection_reason`
Optional: `approver_id`

Example prompts:
- "Reject change 9f8e... because the rollback plan is missing."

## Task Tools (Generic, Problem, Catalog)

These tools accept a `fields` object with any valid table fields, letting you
create or update records without a fixed schema.

### `servicenow_create_task`
Required: `fields`

Example prompts:
- "Create a task with fields: short_description 'Reboot server', assignment_group 'Network Ops'."

### `servicenow_update_task`
Required: `task_id` (number or sys_id), `fields`

Example prompts:
- "Update task TASK0001234 to state 3 and add work_notes."

### `servicenow_get_task`
Required: `task_id` (number or sys_id)
Optional: `fields`, `display_value`, `exclude_reference_link`

Example prompts:
- "Get task TASK0001234 with fields number, short_description, state."

### `servicenow_list_tasks`
Optional: `query`, `fields`, `display_value`, `exclude_reference_link`, `limit`, `offset`

Example prompts:
- "List tasks where short_description contains 'backup' and show number and state."

### `servicenow_create_problem_task`
Required: `fields`

### `servicenow_update_problem_task`
Required: `problem_task_id` (number or sys_id), `fields`

### `servicenow_get_problem_task`
Required: `problem_task_id` (number or sys_id)
Optional: `fields`, `display_value`, `exclude_reference_link`

### `servicenow_get_problem_task_logs`
Required: `problem_task_id` (number or sys_id)
Optional: `elements`, `limit`, `offset`, `order_by`, `order`, `include_problem_task`,
`fields`, `display_value`, `exclude_reference_link`, `sysparm_query`

### `servicenow_list_problem_tasks`
Optional: `query`, `fields`, `display_value`, `exclude_reference_link`, `limit`, `offset`

### `servicenow_create_sc_task`
Required: `fields`

### `servicenow_update_sc_task`
Required: `sc_task_id` (number or sys_id), `fields`

### `servicenow_get_sc_task`
Required: `sc_task_id` (number or sys_id)
Optional: `fields`, `display_value`, `exclude_reference_link`

### `servicenow_list_sc_tasks`
Optional: `query`, `fields`, `display_value`, `exclude_reference_link`, `limit`, `offset`

## Advanced Filtering Tips

- `query` for list tools uses ServiceNow `sysparm_query` syntax.
- You can dot-walk references (e.g., `assigned_to.email=...`).
- For incidents, use dedicated filters like `assigned_to_email`,
  `assigned_to_location_name`, or `assignment_group_name` instead of raw query.

Examples:
- "List incidents with query `state=2^priority=1`."
- "List tasks with query `assignment_group.nameLIKEOps^state=1`."
