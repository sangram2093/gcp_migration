#!/usr/bin/env python3
"""
Generate Jira health status report for an Epic or a Feature.

Scope:
- Epic mode:
  Epic -> Features -> Stories -> Subtasks
- Feature mode:
  Feature -> Stories -> Subtasks

Report outputs:
- Detailed markdown report with per-issue health
- Mermaid diagrams (status distribution + hierarchy graph)
- Rich HTML report with interactive visuals
- JSON payload for downstream processing

Example:
  python scripts/jira_health_status.py \
    --jira-url https://your-jira.example.com \
    --jira-email your.user@example.com \
    --jira-token <token> \
    --jira-auth-mode basic \
    --epic-key NTS-50000
"""

from __future__ import annotations

import argparse
import base64
import math
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from requests.auth import HTTPBasicAuth


DEFAULT_SETTINGS: Dict[str, Any] = {
    "issueTypeAliases": {
        "epic": ["epic"],
        "feature": ["feature", "new feature"],
        "story": ["story", "user story"],
        "subtask": ["sub-task", "subtask", "technical sub-task"],
    },
    "targetDateFieldNames": [
        "Planned End",
        "Target End",
        "Target End Date",
        "Target Date",
        "Due Date",
    ],
    "doneStatusCategories": ["Done"],
    "doneStatusNames": ["Done", "Closed", "Resolved"],
    "linkTypeHintsForFeatureStory": ["Consists of", "is part of", "Relates to"],
    "health": {
        "amberDaysToTarget": 7,
        "redDaysPastTarget": 0,
        "staleDaysAmber": 7,
        "staleDaysRed": 14,
        "staleDaysAmberWithoutTarget": 14,
        "staleDaysRedWithoutTarget": 30,
    },
    "rollup": {
        "anyRedMakesParentRed": True,
        "anyAmberMakesParentAmber": True,
        "redIssueRatioThreshold": 0.2,
        "amberIssueRatioThreshold": 0.4,
    },
    "fetch": {
        "maxCommentsPerIssue": 200,
        "maxWorklogsPerIssue": 200,
    },
    "diagram": {
        "maxNodes": 250,
    },
}


def sanitize_text(value: Any, multiline: bool = True) -> str:
    if value is None:
        return ""
    text = str(value)
    text = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
    )
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    text = text.replace('\\"', '"').replace("\\'", "'")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()

    while len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'", "`"):
        text = text[1:-1].strip()

    if multiline:
        lines = [ln.rstrip() for ln in text.split("\n")]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    else:
        text = re.sub(r"\s+", " ", text).strip()
    return text


def sanitize_key(value: Any) -> str:
    text = sanitize_text(value, multiline=False)
    text = re.sub(r"[.,;:]+$", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", sanitize_text(value, multiline=False).lower())


def parse_jira_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    s = sanitize_text(value, multiline=False)
    if not s:
        return None

    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    patterns = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for pattern in patterns:
        try:
            dt = datetime.strptime(s, pattern)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    try:
        dt2 = datetime.fromisoformat(s)
        if dt2.tzinfo is None:
            return dt2.replace(tzinfo=timezone.utc)
        return dt2.astimezone(timezone.utc)
    except ValueError:
        return None


def to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def format_display_datetime(value: Any) -> str:
    dt = parse_jira_datetime(value)
    if not dt:
        return "-"
    return dt.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def format_display_date(value: Any) -> str:
    dt = parse_jira_datetime(value)
    if not dt:
        return "-"
    return dt.astimezone(timezone.utc).strftime("%d %b %Y")


def format_now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Jira health status for an Epic or Feature.",
    )
    parser.add_argument("--epic-key", default="", help="Epic issue key (e.g. NTS-50001)")
    parser.add_argument("--feature-key", default="", help="Feature issue key (e.g. NTS-50002)")
    parser.add_argument("--settings", default="", help="Path to JSON settings override")
    parser.add_argument("--output-dir", default="jira_health_output", help="Output directory")

    parser.add_argument("--jira-url", default=os.getenv("JIRA_URL", ""), help="Jira base URL")
    parser.add_argument("--jira-email", default=os.getenv("JIRA_EMAIL", ""), help="Jira email/username")
    parser.add_argument("--jira-token", default=os.getenv("JIRA_API_TOKEN", ""), help="Jira API token")
    parser.add_argument(
        "--jira-auth-mode",
        default=os.getenv("JIRA_AUTH_MODE", "bearer"),
        choices=["basic", "bearer", "auto"],
        help="Jira auth mode",
    )
    parser.add_argument(
        "--jira-api-version",
        default=os.getenv("JIRA_API_VERSION", "2"),
        choices=["2", "3"],
        help="Jira API version",
    )
    parser.add_argument("--auth-debug", action="store_true", help="Print safe auth diagnostics")
    parser.add_argument("--max-retries", type=int, default=5, help="API retry count")
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.5, help="Retry backoff base")
    return parser.parse_args()


class JiraClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        token: str,
        auth_mode: str,
        api_version: str,
        max_retries: int,
        backoff: float,
    ) -> None:
        normalized_base = sanitize_text(base_url, multiline=False)
        if not re.match(r"^https?://", normalized_base, flags=re.IGNORECASE):
            normalized_base = f"https://{normalized_base}"
        normalized_base = re.sub(
            r"/rest/api/[23]/?$",
            "",
            normalized_base,
            flags=re.IGNORECASE,
        )
        self.base_url = normalized_base.rstrip("/")
        self.auth_mode = sanitize_text(auth_mode, multiline=False).lower() or "bearer"
        self.api_version = sanitize_text(api_version, multiline=False) or "2"
        self.api_prefix = f"/rest/api/{self.api_version}"

        self.email = sanitize_text(email, multiline=False)
        self.token = sanitize_text(token, multiline=False)
        self.auth: Optional[HTTPBasicAuth] = None
        self.auth_header: Optional[str] = None
        if self.auth_mode == "basic":
            self.auth = HTTPBasicAuth(self.email, self.token)
            payload = f"{self.email}:{self.token}".encode("utf-8")
            self.auth_header = f"Basic {base64.b64encode(payload).decode('ascii')}"
        elif self.auth_mode == "bearer":
            self.auth_header = f"Bearer {self.token}"
        else:  # auto
            self.auth_header = f"Bearer {self.token}"

        self.max_retries = max_retries
        self.backoff = backoff
        self.session = requests.Session()
        self._fields_cache: Optional[List[Dict[str, Any]]] = None

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json")
        if self.auth_header:
            headers.setdefault("Authorization", self.auth_header)
        if "json" in kwargs:
            headers.setdefault("Content-Type", "application/json")

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    auth=self.auth,
                    headers=headers,
                    timeout=60,
                    **kwargs,
                )

                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"{response.status_code} {response.text}"
                    time.sleep(self.backoff * attempt)
                    continue

                if response.status_code == 401 and self.auth_mode == "auto" and self.email:
                    if headers.get("Authorization", "").startswith("Bearer "):
                        payload = f"{self.email}:{self.token}".encode("utf-8")
                        headers["Authorization"] = (
                            f"Basic {base64.b64encode(payload).decode('ascii')}"
                        )
                        response = self.session.request(
                            method=method,
                            url=url,
                            auth=None,
                            headers=headers,
                            timeout=60,
                            **kwargs,
                        )

                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Jira API error {response.status_code} {path}: {response.text}",
                    )

                if response.status_code == 204 or not response.text:
                    return {}
                return response.json()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(self.backoff * attempt)
                    continue
                raise RuntimeError(
                    f"Jira API request failed after retries: {method} {path} :: {last_error}",
                ) from exc
        raise RuntimeError(f"Jira API request failed: {method} {path} :: {last_error}")

    def get_fields(self) -> List[Dict[str, Any]]:
        if self._fields_cache is None:
            data = self._request("GET", f"{self.api_prefix}/field")
            self._fields_cache = data if isinstance(data, list) else []
        return self._fields_cache

    def get_field_id(self, field_name: str) -> Optional[str]:
        wanted = sanitize_text(field_name, multiline=False).lower()
        for item in self.get_fields():
            if sanitize_text(item.get("name"), multiline=False).lower() == wanted:
                return sanitize_text(item.get("id"), multiline=False)
        return None

    def get_issue(self, issue_key: str, fields: List[str], expand: str = "") -> Dict[str, Any]:
        params: Dict[str, Any] = {"fields": ",".join(fields)}
        if expand:
            params["expand"] = expand
        return self._request("GET", f"{self.api_prefix}/issue/{sanitize_key(issue_key)}", params=params)

    def search_jql(self, jql: str, fields: List[str], page_size: int = 100) -> List[Dict[str, Any]]:
        all_issues: List[Dict[str, Any]] = []
        start_at = 0
        while True:
            params = {
                "jql": jql,
                "fields": ",".join(fields),
                "startAt": start_at,
                "maxResults": page_size,
            }
            payload = self._request("GET", f"{self.api_prefix}/search", params=params)
            issues = payload.get("issues", []) if isinstance(payload, dict) else []
            total = int(payload.get("total", 0)) if isinstance(payload, dict) else len(issues)
            all_issues.extend(issues)
            if not issues or len(all_issues) >= total:
                break
            start_at += len(issues)
        return all_issues

    def get_comments(self, issue_key: str, max_results: int) -> List[Dict[str, Any]]:
        payload = self._request(
            "GET",
            f"{self.api_prefix}/issue/{sanitize_key(issue_key)}/comment",
            params={"maxResults": max_results},
        )
        return payload.get("comments", []) if isinstance(payload, dict) else []

    def get_worklogs(self, issue_key: str, max_results: int) -> List[Dict[str, Any]]:
        payload = self._request(
            "GET",
            f"{self.api_prefix}/issue/{sanitize_key(issue_key)}/worklog",
            params={"maxResults": max_results},
        )
        return payload.get("worklogs", []) if isinstance(payload, dict) else []


@dataclass
class IssueHealth:
    key: str
    summary: str
    assignee: str
    issue_type: str
    jira_status: str
    status_category: str
    health: str
    reason: str
    target_date: Optional[str]
    target_source: Optional[str]
    inherited_target: bool
    parent_key: Optional[str]
    children: List[str]
    comment_count: int
    worklog_count: int
    last_comment_at: Optional[str]
    last_worklog_at: Optional[str]
    last_activity_at: Optional[str]
    days_to_target: Optional[int]
    days_since_activity: Optional[int]


class HealthAnalyzer:
    def __init__(self, client: JiraClient, settings: Dict[str, Any]) -> None:
        self.client = client
        self.settings = settings
        self.issue_cache: Dict[str, Dict[str, Any]] = {}
        self.target_field_map: Dict[str, str] = self._resolve_target_fields()

        self.type_aliases = settings["issueTypeAliases"]
        self.epic_aliases = {normalize_token(x) for x in self.type_aliases.get("epic", [])}
        self.feature_aliases = {normalize_token(x) for x in self.type_aliases.get("feature", [])}
        self.story_aliases = {normalize_token(x) for x in self.type_aliases.get("story", [])}
        self.subtask_aliases = {normalize_token(x) for x in self.type_aliases.get("subtask", [])}

    def _resolve_target_fields(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for name in self.settings.get("targetDateFieldNames", []):
            normalized = sanitize_text(name, multiline=False)
            if not normalized:
                continue
            if normalize_token(normalized) in {"duedate", "duedatefield", "duedatebuiltin"}:
                out[normalized] = "duedate"
                continue
            field_id = self.client.get_field_id(normalized)
            if field_id:
                out[normalized] = field_id
        if "Due Date" not in out:
            out["Due Date"] = "duedate"
        return out

    def _base_fields(self) -> List[str]:
        fields = [
            "summary",
            "status",
            "issuetype",
            "parent",
            "subtasks",
            "issuelinks",
            "duedate",
            "updated",
            "created",
            "assignee",
            "priority",
        ]
        for field_id in self.target_field_map.values():
            if field_id != "duedate":
                fields.append(field_id)
        return sorted(set(fields))

    def get_issue_cached(self, issue_key: str) -> Dict[str, Any]:
        key = sanitize_key(issue_key)
        if key not in self.issue_cache:
            self.issue_cache[key] = self.client.get_issue(key, self._base_fields())
        return self.issue_cache[key]

    @staticmethod
    def issue_type_name(issue: Dict[str, Any]) -> str:
        return sanitize_text(issue.get("fields", {}).get("issuetype", {}).get("name"), multiline=False)

    def _is_type(self, issue: Dict[str, Any], aliases: Set[str]) -> bool:
        return normalize_token(self.issue_type_name(issue)) in aliases

    def _query_children_by_parent(self, parent_key: str) -> List[Dict[str, Any]]:
        jql = f'parent = "{sanitize_key(parent_key)}" ORDER BY created ASC'
        return self.client.search_jql(jql, self._base_fields())

    def _features_for_epic(self, epic_key: str) -> List[str]:
        candidates: Dict[str, Dict[str, Any]] = {}

        queries = [
            f'"Epic Link" = "{sanitize_key(epic_key)}" ORDER BY created ASC',
            f'parent = "{sanitize_key(epic_key)}" ORDER BY created ASC',
        ]
        for jql in queries:
            try:
                issues = self.client.search_jql(jql, self._base_fields())
                for issue in issues:
                    candidates[sanitize_key(issue.get("key"))] = issue
            except Exception:
                continue

        feature_keys: List[str] = []
        for key, issue in candidates.items():
            if self._is_type(issue, self.feature_aliases):
                feature_keys.append(key)

        if not feature_keys:
            for key, issue in candidates.items():
                if not self._is_type(issue, self.story_aliases) and not self._is_type(issue, self.subtask_aliases):
                    feature_keys.append(key)

        feature_keys.sort()
        return feature_keys

    def _stories_for_feature(self, feature_key: str) -> List[str]:
        feature_issue = self.get_issue_cached(feature_key)
        keys: Set[str] = set()

        for link in feature_issue.get("fields", {}).get("issuelinks", []) or []:
            inward = link.get("inwardIssue")
            outward = link.get("outwardIssue")
            if inward and inward.get("key"):
                keys.add(sanitize_key(inward["key"]))
            if outward and outward.get("key"):
                keys.add(sanitize_key(outward["key"]))

        for child in self._query_children_by_parent(feature_key):
            keys.add(sanitize_key(child.get("key")))

        stories: List[str] = []
        for key in sorted(keys):
            try:
                issue = self.get_issue_cached(key)
                if self._is_type(issue, self.story_aliases):
                    stories.append(key)
            except Exception:
                continue
        return stories

    def _subtasks_for_story(self, story_key: str) -> List[str]:
        story_issue = self.get_issue_cached(story_key)
        keys: Set[str] = set()

        for sub in story_issue.get("fields", {}).get("subtasks", []) or []:
            if sub.get("key"):
                keys.add(sanitize_key(sub["key"]))

        if not keys:
            for child in self._query_children_by_parent(story_key):
                keys.add(sanitize_key(child.get("key")))

        subtasks: List[str] = []
        for key in sorted(keys):
            try:
                issue = self.get_issue_cached(key)
                if self._is_type(issue, self.subtask_aliases):
                    subtasks.append(key)
            except Exception:
                continue
        return subtasks

    def build_hierarchy(
        self,
        epic_key: str = "",
        feature_key: str = "",
    ) -> Tuple[str, str, Dict[str, List[str]], Dict[str, Optional[str]]]:
        root_key = sanitize_key(epic_key or feature_key)
        root_issue = self.get_issue_cached(root_key)
        root_type = self.issue_type_name(root_issue)
        scope = "epic" if epic_key else "feature"

        edges: Dict[str, List[str]] = {}
        parent_by_child: Dict[str, Optional[str]] = {root_key: None}

        if scope == "epic":
            features = self._features_for_epic(root_key)
        else:
            features = [root_key]

        if scope == "epic":
            edges[root_key] = features
            for feature in features:
                parent_by_child[feature] = root_key

        for feature in features:
            stories = self._stories_for_feature(feature)
            edges[feature] = stories
            for story in stories:
                parent_by_child[story] = feature
                subtasks = self._subtasks_for_story(story)
                edges[story] = subtasks
                for subtask in subtasks:
                    parent_by_child[subtask] = story

        return root_key, root_type, edges, parent_by_child

    def _target_date_for_issue(
        self,
        issue: Dict[str, Any],
    ) -> Tuple[Optional[datetime], Optional[str]]:
        fields = issue.get("fields", {})
        for field_name in self.settings.get("targetDateFieldNames", []):
            field_id = self.target_field_map.get(field_name)
            if not field_id:
                continue
            value = fields.get(field_id)
            dt = parse_jira_datetime(value)
            if dt:
                return dt, field_name
        return None, None

    @staticmethod
    def _latest_activity(
        issue: Dict[str, Any],
        comments: List[Dict[str, Any]],
        worklogs: List[Dict[str, Any]],
    ) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
        issue_updated = parse_jira_datetime(issue.get("fields", {}).get("updated"))
        latest_comment = None
        latest_worklog = None

        for comment in comments:
            dt = parse_jira_datetime(comment.get("updated") or comment.get("created"))
            if dt and (latest_comment is None or dt > latest_comment):
                latest_comment = dt

        for log in worklogs:
            dt = parse_jira_datetime(log.get("started") or log.get("updated") or log.get("created"))
            if dt and (latest_worklog is None or dt > latest_worklog):
                latest_worklog = dt

        latest = issue_updated
        for dt in (latest_comment, latest_worklog):
            if dt and (latest is None or dt > latest):
                latest = dt
        return latest, latest_comment, latest_worklog

    def _is_done(self, issue: Dict[str, Any]) -> bool:
        fields = issue.get("fields", {})
        status_name = sanitize_text(fields.get("status", {}).get("name"), multiline=False)
        status_category = sanitize_text(
            fields.get("status", {}).get("statusCategory", {}).get("name"),
            multiline=False,
        )

        if status_category in self.settings.get("doneStatusCategories", []):
            return True
        return status_name in self.settings.get("doneStatusNames", [])

    def _evaluate_health(
        self,
        issue: Dict[str, Any],
        target_date: Optional[datetime],
        last_activity: Optional[datetime],
    ) -> Tuple[str, str, Optional[int], Optional[int]]:
        now = datetime.now(timezone.utc)

        if self._is_done(issue):
            return "green", "Issue is in Done status category", None, None

        days_to_target: Optional[int] = None
        if target_date:
            days_to_target = (target_date.date() - now.date()).days

        days_since_activity: Optional[int] = None
        if last_activity:
            days_since_activity = max((now.date() - last_activity.date()).days, 0)

        if days_since_activity is None:
            return "amber", "No activity detected", days_to_target, None

        if days_since_activity <= 6:
            return (
                "green",
                f"Recent activity within {days_since_activity} day(s)",
                days_to_target,
                days_since_activity,
            )
        if 7 <= days_since_activity <= 14:
            return (
                "amber",
                f"No activity for {days_since_activity} day(s)",
                days_to_target,
                days_since_activity,
            )

        return (
            "red",
            f"No activity for {days_since_activity} day(s)",
            days_to_target,
            days_since_activity,
        )

    @staticmethod
    def _collect_descendants(start_key: str, edges: Dict[str, List[str]]) -> List[str]:
        descendants: List[str] = []
        stack: List[str] = list(edges.get(start_key, []))
        seen: Set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            descendants.append(node)
            for child in edges.get(node, []):
                stack.append(child)
        return descendants

    def _feature_target_date(
        self,
        feature_key: str,
        root_key: str,
        root_issue: Dict[str, Any],
        health_map: Dict[str, IssueHealth],
    ) -> Tuple[Optional[datetime], Optional[str], bool]:
        if feature_key != root_key and self._is_type(root_issue, self.epic_aliases):
            root_item = health_map.get(root_key)
            epic_target = parse_jira_datetime(root_item.target_date) if root_item else None
            if epic_target:
                return epic_target - timedelta(days=15), "Epic target - 15 days", True

        feature_item = health_map.get(feature_key)
        feature_target = parse_jira_datetime(feature_item.target_date) if feature_item else None
        if feature_target:
            return feature_target, feature_item.target_source, feature_item.inherited_target

        return None, None, False

    def _apply_feature_rollups(
        self,
        root_key: str,
        edges: Dict[str, List[str]],
        health_map: Dict[str, IssueHealth],
    ) -> None:
        now = datetime.now(timezone.utc)
        root_issue = self.get_issue_cached(root_key)

        for key, item in health_map.items():
            issue = self.get_issue_cached(key)
            if not self._is_type(issue, self.feature_aliases):
                continue

            target_dt, target_src, inherited = self._feature_target_date(
                feature_key=key,
                root_key=root_key,
                root_issue=root_issue,
                health_map=health_map,
            )
            if target_dt:
                item.target_date = to_iso(target_dt)
                item.target_source = target_src
                item.inherited_target = inherited
                item.days_to_target = (target_dt.date() - now.date()).days

            reasons: List[str] = []
            if "block" in normalize_token(item.jira_status):
                reasons.append("Feature status is Blocked")

            if target_dt and target_dt.date() < now.date():
                overdue_days = (now.date() - target_dt.date()).days
                reasons.append(f"Feature is overdue by {overdue_days} day(s)")

            descendants = self._collect_descendants(key, edges)
            has_red_subtask = False
            for descendant_key in descendants:
                descendant = health_map.get(descendant_key)
                if not descendant:
                    continue
                descendant_issue = self.get_issue_cached(descendant_key)
                if self._is_type(descendant_issue, self.subtask_aliases) and descendant.health == "red":
                    has_red_subtask = True
                    break
            if has_red_subtask:
                reasons.append("At least one sub-task under this feature is RED")

            if reasons:
                base_reason = sanitize_text(item.reason, multiline=False)
                joined = "; ".join(reasons)
                if base_reason:
                    item.reason = f"{base_reason}; {joined}"
                else:
                    item.reason = joined
                item.health = "red"

    def calculate_health(
        self,
        root_key: str,
        edges: Dict[str, List[str]],
        parent_by_child: Dict[str, Optional[str]],
    ) -> Dict[str, IssueHealth]:
        issue_keys: Set[str] = {root_key}
        for parent, children in edges.items():
            issue_keys.add(parent)
            for child in children:
                issue_keys.add(child)

        lineage_target: Dict[str, Tuple[Optional[datetime], Optional[str]]] = {}
        out: Dict[str, IssueHealth] = {}

        def inherited_target_for(key: str) -> Tuple[Optional[datetime], Optional[str], bool]:
            parent = parent_by_child.get(key)
            while parent:
                if parent in lineage_target and lineage_target[parent][0]:
                    dt, src = lineage_target[parent]
                    return dt, src, True
                parent = parent_by_child.get(parent)
            return None, None, False

        ordered_keys = sorted(
            issue_keys,
            key=lambda k: (0 if k == root_key else 1, k),
        )

        for key in ordered_keys:
            issue = self.get_issue_cached(key)
            comments = self.client.get_comments(key, int(self.settings["fetch"]["maxCommentsPerIssue"]))
            worklogs = self.client.get_worklogs(key, int(self.settings["fetch"]["maxWorklogsPerIssue"]))

            target_dt, target_src = self._target_date_for_issue(issue)
            inherited = False
            if target_dt is None:
                inherited_dt, inherited_src, inherited = inherited_target_for(key)
                target_dt = inherited_dt
                target_src = f"{inherited_src} (inherited)" if inherited_src and inherited else inherited_src

            lineage_target[key] = (target_dt, target_src)

            last_activity, last_comment, last_worklog = self._latest_activity(issue, comments, worklogs)
            health, reason, days_to_target, days_since_activity = self._evaluate_health(
                issue,
                target_dt,
                last_activity,
            )

            fields = issue.get("fields", {})
            summary = sanitize_text(fields.get("summary"), multiline=False)
            assignee_obj = fields.get("assignee") or {}
            assignee = sanitize_text(
                assignee_obj.get("displayName") or assignee_obj.get("name") or assignee_obj.get("emailAddress"),
                multiline=False,
            )
            issue_type = self.issue_type_name(issue)
            jira_status = sanitize_text(fields.get("status", {}).get("name"), multiline=False)
            status_category = sanitize_text(
                fields.get("status", {}).get("statusCategory", {}).get("name"),
                multiline=False,
            )
            parent_key = sanitize_key(fields.get("parent", {}).get("key")) if fields.get("parent") else parent_by_child.get(key)
            children = edges.get(key, [])

            out[key] = IssueHealth(
                key=key,
                summary=summary,
                assignee=assignee or "-",
                issue_type=issue_type,
                jira_status=jira_status,
                status_category=status_category,
                health=health,
                reason=reason,
                target_date=to_iso(target_dt),
                target_source=target_src,
                inherited_target=inherited,
                parent_key=parent_key,
                children=children,
                comment_count=len(comments),
                worklog_count=len(worklogs),
                last_comment_at=to_iso(last_comment),
                last_worklog_at=to_iso(last_worklog),
                last_activity_at=to_iso(last_activity),
                days_to_target=days_to_target,
                days_since_activity=days_since_activity,
            )

        self._apply_feature_rollups(root_key=root_key, edges=edges, health_map=out)
        return out


def rollup_status(issues: Dict[str, IssueHealth], settings: Dict[str, Any]) -> Tuple[str, Dict[str, int]]:
    counts = {"green": 0, "amber": 0, "red": 0}
    for item in issues.values():
        if item.health not in counts:
            continue
        counts[item.health] += 1

    total = max(len(issues), 1)
    red_ratio = counts["red"] / total
    amber_ratio = counts["amber"] / total
    rollup = settings["rollup"]

    if rollup.get("anyRedMakesParentRed", True) and counts["red"] > 0:
        return "red", counts
    if red_ratio >= float(rollup.get("redIssueRatioThreshold", 0.2)):
        return "red", counts
    if rollup.get("anyAmberMakesParentAmber", True) and counts["amber"] > 0:
        return "amber", counts
    if amber_ratio >= float(rollup.get("amberIssueRatioThreshold", 0.4)):
        return "amber", counts
    return "green", counts


def status_emoji(status: str) -> str:
    if status == "green":
        return "G"
    if status == "amber":
        return "A"
    if status == "red":
        return "R"
    return "?"


def status_color(status: str) -> str:
    if status == "green":
        return "#16a34a"
    if status == "amber":
        return "#d97706"
    if status == "red":
        return "#dc2626"
    return "#64748b"


def make_mermaid_id(issue_key: str) -> str:
    return f"K_{re.sub(r'[^A-Za-z0-9_]', '_', issue_key)}"


def escape_mermaid_label(value: str) -> str:
    text = sanitize_text(value, multiline=False)
    text = text.replace('"', "'")
    return text[:90]


def build_node_order(root_key: str, edges: Dict[str, List[str]]) -> List[Tuple[str, int]]:
    ordered: List[Tuple[str, int]] = []
    seen: Set[str] = set()
    stack: List[Tuple[str, int]] = [(root_key, 0)]

    while stack:
        node, depth = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        ordered.append((node, depth))
        children = edges.get(node, [])
        for child in reversed(children):
            stack.append((child, depth + 1))

    return ordered


def build_donut_svg(counts: Dict[str, int]) -> str:
    values = [
        ("green", counts.get("green", 0)),
        ("amber", counts.get("amber", 0)),
        ("red", counts.get("red", 0)),
    ]
    total = sum(v for _, v in values)
    if total <= 0:
        total = 1
    radius = 68
    circumference = 2 * math.pi * radius
    start = 0.0
    parts: List[str] = []
    for status, value in values:
        if value <= 0:
            continue
        length = (value / total) * circumference
        parts.append(
            f'<circle cx="95" cy="95" r="{radius}" fill="none" '
            f'stroke="{status_color(status)}" stroke-width="24" '
            f'stroke-dasharray="{length:.3f} {circumference:.3f}" '
            f'stroke-dashoffset="{-start:.3f}" stroke-linecap="butt" '
            f'transform="rotate(-90 95 95)"></circle>'
        )
        start += length

    return (
        '<svg width="190" height="190" viewBox="0 0 190 190" role="img" aria-label="Health donut">'
        '<circle cx="95" cy="95" r="68" fill="none" stroke="#e2e8f0" stroke-width="24"></circle>'
        + "".join(parts)
        + f'<text x="95" y="92" text-anchor="middle" font-size="30" fill="#0f172a" font-weight="700">{sum(counts.values())}</text>'
        + '<text x="95" y="115" text-anchor="middle" font-size="12" fill="#64748b">Issues</text>'
        + "</svg>"
    )


def build_feature_rows(
    scope: str,
    root_key: str,
    edges: Dict[str, List[str]],
    health_map: Dict[str, IssueHealth],
) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    root_item = health_map.get(root_key)
    root_target_dt = parse_jira_datetime(root_item.target_date) if root_item else None

    feature_keys: List[str] = []
    if scope == "epic":
        for key in edges.get(root_key, []):
            if key in health_map:
                feature_keys.append(key)
    elif root_key in health_map:
        feature_keys.append(root_key)

    rows: List[Dict[str, Any]] = []
    for key in feature_keys:
        item = health_map.get(key)
        if not item:
            continue

        feature_target_dt = parse_jira_datetime(item.target_date)
        target_source = item.target_source or "-"
        if scope == "epic" and root_target_dt:
            feature_target_dt = root_target_dt - timedelta(days=15)
            target_source = "Epic target - 15 days"

        days_to_epic: Optional[int] = None
        if root_target_dt:
            days_to_epic = (root_target_dt.date() - now.date()).days

        rows.append(
            {
                "key": item.key,
                "summary": item.summary,
                "assignee": item.assignee,
                "jira_status": item.jira_status or "-",
                "health": item.health,
                "target_date": to_iso(feature_target_dt) if feature_target_dt else item.target_date,
                "target_date_display": format_display_date(feature_target_dt) if feature_target_dt else format_display_date(item.target_date),
                "target_source": target_source,
                "days_to_epic": days_to_epic,
                "days_since_activity": item.days_since_activity,
                "days_to_target": item.days_to_target,
            },
        )

    rows.sort(
        key=lambda r: (
            {"red": 0, "amber": 1, "green": 2}.get(str(r.get("health", "")).lower(), 3),
            -(int(r.get("days_since_activity") or 0)),
            str(r.get("key", "")),
        ),
    )
    return rows


def build_feature_days_svg(feature_rows: List[Dict[str, Any]]) -> str:
    if not feature_rows:
        return '<div class="sub">No feature data available.</div>'

    activity_values = [int(row["days_since_activity"]) for row in feature_rows if row["days_since_activity"] is not None]
    x_max = max(20, (max(activity_values) if activity_values else 0) + 2)

    tick_step = 5 if x_max > 25 else 2
    ticks: List[str] = []
    for value in range(0, x_max + 1, tick_step):
        pct = (value / x_max) * 100
        ticks.append(
            "<div class='wf-tick'>"
            f"<span class='wf-tick-line' style='left:{pct:.2f}%'></span>"
            f"<span class='wf-tick-label' style='left:{pct:.2f}%'>{value}d</span>"
            "</div>"
        )

    rows_html: List[str] = []
    for row in feature_rows:
        age = max(int(row["days_since_activity"] or 0), 0)
        pct = min((age / x_max) * 100, 100)
        health = str(row["health"])
        key = html_escape(str(row["key"]))
        summary = html_escape(sanitize_text(row["summary"], multiline=False)[:56] or "-")
        jira_status = html_escape(str(row["jira_status"]))
        status = html_escape(health.upper())
        target = html_escape(str(row["target_date_display"]))
        days_to_epic = row["days_to_epic"]
        days_to_epic_text = "-" if days_to_epic is None else f"{int(days_to_epic)}d"
        assignee = html_escape(str(row["assignee"] or "-"))

        title = (
            f"{row['key']} | {sanitize_text(row['summary'], multiline=False)} | "
            f"Health: {str(row['health']).upper()} | Jira: {row['jira_status']} | "
            f"Target: {row['target_date_display']} | Inactive: {age} day(s) | "
            f"Days to Epic: {days_to_epic_text} | Assignee: {row['assignee']}"
        )
        rows_html.append(
            f"<div class='wf-row' title='{html_escape(title)}'>"
            f"<div class='wf-label'><div class='wf-key'>{key}</div><div class='wf-summary'>{summary}</div></div>"
            "<div class='wf-track-wrap'>"
            "<div class='wf-track-zones'>"
            "<span class='wf-zone green' style='width:30%'></span>"
            "<span class='wf-zone amber' style='width:40%'></span>"
            "<span class='wf-zone red' style='width:30%'></span>"
            "</div>"
            f"<div class='wf-progress {health}' style='width:{pct:.2f}%'></div>"
            f"<div class='wf-marker {health}' style='left:{pct:.2f}%'></div>"
            f"<div class='wf-age' style='left:min(calc({pct:.2f}% + 10px), calc(100% - 84px))'>{age}d inactive</div>"
            "</div>"
            "<div class='wf-meta'>"
            f"<span class='chip {health}'>{status}</span>"
            f"<span>{jira_status}</span>"
            f"<span>T:{target}</span>"
            f"<span>Epic T-{days_to_epic_text}</span>"
            f"<span>{assignee}</span>"
            "</div>"
            "</div>"
        )

    return (
        "<div class='wf-chart'>"
        "<div class='wf-axis-note'>Waterfall axis: days since last activity (0-6 Green, 7-14 Amber, 15+ Red)</div>"
        "<div class='wf-axis'>"
        f"{''.join(ticks)}"
        "</div>"
        f"{''.join(rows_html)}"
        "</div>"
    )


def compute_type_health_stats(health_map: Dict[str, IssueHealth]) -> List[Dict[str, Any]]:
    stats: Dict[str, Dict[str, int]] = {}
    for item in health_map.values():
        key = item.issue_type or "Unknown"
        if key not in stats:
            stats[key] = {"green": 0, "amber": 0, "red": 0, "total": 0}
        if item.health in ("green", "amber", "red"):
            stats[key][item.health] += 1
        stats[key]["total"] += 1

    rows = [
        {
            "type": issue_type,
            "green": values["green"],
            "amber": values["amber"],
            "red": values["red"],
            "total": values["total"],
        }
        for issue_type, values in stats.items()
    ]
    rows.sort(key=lambda x: (-x["total"], x["type"]))
    return rows


def build_mermaid_pie(counts: Dict[str, int]) -> str:
    return "\n".join(
        [
            "```mermaid",
            "pie title Jira Health Distribution",
            f'  "Green" : {counts.get("green", 0)}',
            f'  "Amber" : {counts.get("amber", 0)}',
            f'  "Red" : {counts.get("red", 0)}',
            "```",
        ],
    )


def build_mermaid_hierarchy(
    root_key: str,
    edges: Dict[str, List[str]],
    health_map: Dict[str, IssueHealth],
    max_nodes: int,
) -> str:
    ordered: List[str] = [root_key]
    seen: Set[str] = {root_key}
    for parent in list(ordered):
        for child in edges.get(parent, []):
            if child not in seen:
                seen.add(child)
                ordered.append(child)
    if len(ordered) > max_nodes:
        ordered = ordered[:max_nodes]
        seen = set(ordered)

    lines = ["```mermaid", "flowchart TD"]
    for key in ordered:
        item = health_map.get(key)
        if not item:
            continue
        node_id = make_mermaid_id(key)
        label = f"{escape_mermaid_label(item.key)}\\n{escape_mermaid_label(item.issue_type)}\\n{item.health.upper()}"
        lines.append(f'  {node_id}["{label}"]')

    for parent, children in edges.items():
        if parent not in seen:
            continue
        for child in children:
            if child not in seen:
                continue
            lines.append(f"  {make_mermaid_id(parent)} --> {make_mermaid_id(child)}")

    lines.extend(
        [
            "  classDef green fill:#dcfce7,stroke:#16a34a,color:#14532d;",
            "  classDef amber fill:#fef3c7,stroke:#d97706,color:#78350f;",
            "  classDef red fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;",
        ],
    )
    for key in ordered:
        item = health_map.get(key)
        if not item:
            continue
        lines.append(f"  class {make_mermaid_id(key)} {item.health};")
    lines.append("```")
    return "\n".join(lines)


def render_markdown_report(
    scope: str,
    root_key: str,
    root_type: str,
    overall_status: str,
    counts: Dict[str, int],
    edges: Dict[str, List[str]],
    health_map: Dict[str, IssueHealth],
    settings: Dict[str, Any],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    rows = sorted(
        health_map.values(),
        key=lambda x: (x.key != root_key, x.issue_type, x.key),
    )

    md: List[str] = []
    md.append(f"# Jira Health Report: {root_key}")
    md.append("")
    md.append(f"- Scope: **{scope.upper()}**")
    md.append(f"- Root Type: **{root_type or 'Unknown'}**")
    md.append(f"- Generated At (UTC): `{now}`")
    md.append(f"- Overall Health: **{status_emoji(overall_status)} {overall_status.upper()}**")
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append(f"- Total Issues: **{len(health_map)}**")
    md.append(f"- Green: **{counts['green']}**, Amber: **{counts['amber']}**, Red: **{counts['red']}**")
    md.append("")
    md.append(build_mermaid_pie(counts))
    md.append("")
    md.append("## Hierarchy Diagram")
    md.append("")
    md.append(
        build_mermaid_hierarchy(
            root_key=root_key,
            edges=edges,
            health_map=health_map,
            max_nodes=int(settings["diagram"]["maxNodes"]),
        ),
    )
    md.append("")
    md.append("## Detailed Issue Health")
    md.append("")
    md.append(
        "| Key | Type | Jira Status | Health | Target Date | Last Activity | Days To Target | Days Since Activity | Comments | Worklogs | Reason |",
    )
    md.append(
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
    )

    for row in rows:
        md.append(
            "| "
            + " | ".join(
                [
                    row.key,
                    row.issue_type or "-",
                    row.jira_status or "-",
                    f"{status_emoji(row.health)} {row.health.upper()}",
                    row.target_date or "-",
                    row.last_activity_at or "-",
                    str(row.days_to_target) if row.days_to_target is not None else "-",
                    str(row.days_since_activity) if row.days_since_activity is not None else "-",
                    str(row.comment_count),
                    str(row.worklog_count),
                    sanitize_text(row.reason, multiline=False) or "-",
                ],
            )
            + " |",
        )

    return "\n".join(md)


def render_html_report(
    scope: str,
    root_key: str,
    root_type: str,
    overall_status: str,
    counts: Dict[str, int],
    edges: Dict[str, List[str]],
    health_map: Dict[str, IssueHealth],
) -> str:
    generated_at = format_now_utc()
    ordered_nodes = build_node_order(root_key, edges)
    donut_svg = build_donut_svg(counts)
    feature_rows = build_feature_rows(scope=scope, root_key=root_key, edges=edges, health_map=health_map)
    feature_graph_svg = build_feature_days_svg(feature_rows)

    table_rows: List[str] = []
    for key, depth in ordered_nodes:
        item = health_map.get(key)
        if not item:
            continue
        indent = depth * 20
        status_chip = f"<span class='chip {item.health}'>{item.health.upper()}</span>"
        parent_key = sanitize_key(item.parent_key) if item.parent_key else ""
        issue_type_token = normalize_token(item.issue_type)
        is_feature_or_story = ("feature" in issue_type_token) or ("story" in issue_type_token)
        has_children = bool(item.children)
        collapsible = has_children and is_feature_or_story
        toggle_html = (
            "<button type='button' class='tree-toggle' aria-label='Toggle children' aria-expanded='true'>▾</button>"
            if collapsible
            else "<span class='tree-spacer'></span>"
        )
        row_class = "tree-row collapsible-row" if collapsible else "tree-row"
        table_rows.append(
            f"<tr class='{row_class}' data-key='{html_escape(item.key)}' data-parent='{html_escape(parent_key)}' data-depth='{depth}' data-collapsed='0'>"
            f"<td><div class='key-cell' style='padding-left:{indent}px'>{toggle_html}<div class='key-content'><strong>{html_escape(item.key)}</strong><div class='summary'>{html_escape(item.summary or '')}</div></div></div></td>"
            f"<td>{html_escape(item.issue_type or '-')}</td>"
            f"<td>{html_escape(item.assignee or '-')}</td>"
            f"<td>{html_escape(item.jira_status or '-')}</td>"
            f"<td>{status_chip}</td>"
            f"<td>{html_escape(format_display_date(item.target_date))}</td>"
            f"<td>{html_escape(format_display_datetime(item.last_activity_at))}</td>"
            f"<td>{item.days_to_target if item.days_to_target is not None else '-'}</td>"
            f"<td>{item.days_since_activity if item.days_since_activity is not None else '-'}</td>"
            f"<td>{item.comment_count}</td>"
            f"<td>{item.worklog_count}</td>"
            f"<td>{html_escape(item.reason or '-')}</td>"
            "</tr>"
        )

    feature_rows_html: List[str] = []
    for row in feature_rows:
        status_text = str(row["health"]).upper()
        days_to_epic = row["days_to_epic"]
        days_to_epic_text = "-" if days_to_epic is None else f"{days_to_epic} day(s)"
        feature_rows_html.append(
            "<div class='feature-meta-row'>"
            f"<div><strong>{html_escape(str(row['key']))}</strong> - {html_escape(str(row['summary'] or '-'))}</div>"
            f"<div>Target: {html_escape(str(row['target_date_display']))}</div>"
            f"<div>Status: <span class='chip {html_escape(str(row['health']))}'>{html_escape(status_text)}</span></div>"
            f"<div>Jira Status: {html_escape(str(row['jira_status']))}</div>"
            f"<div>Days to Epic Target: {html_escape(days_to_epic_text)}</div>"
            f"<div>Assignee: {html_escape(str(row['assignee'] or '-'))}</div>"
            "</div>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Jira Health Report - {html_escape(root_key)}</title>
  <style>
    :root {{
      --green:#16a34a; --amber:#d97706; --red:#dc2626;
      --bg:#f8fafc; --surface:#ffffff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0;
    }}
    body {{ margin:0; font-family:Segoe UI, system-ui, sans-serif; background:var(--bg); color:var(--text); }}
    .wrap {{ max-width:1400px; margin:0 auto; padding:24px; }}
    .header {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:20px; }}
    .sub {{ color:var(--muted); font-size:13px; }}
    .status {{ font-size:22px; font-weight:700; margin-top:8px; color:{status_color(overall_status)}; }}
    .grid {{ display:grid; grid-template-columns: 280px 1fr; gap:16px; margin-top:16px; }}
    .card {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:16px; }}
    .legend {{ display:flex; gap:12px; font-size:12px; color:var(--muted); margin-top:6px; }}
    .dot {{ width:10px; height:10px; display:inline-block; border-radius:99px; margin-right:5px; }}
    .wf-chart {{ margin-top:10px; border:1px solid var(--line); border-radius:12px; padding:10px; background:#fcfdff; }}
    .wf-axis-note {{ font-size:12px; color:#475569; margin-bottom:10px; }}
    .wf-axis {{ position:relative; height:26px; margin:0 0 8px 240px; }}
    .wf-tick-line {{ position:absolute; top:4px; bottom:12px; width:1px; background:#e2e8f0; }}
    .wf-tick-label {{ position:absolute; top:12px; transform:translateX(-50%); font-size:10px; color:#64748b; }}
    .wf-row {{ display:grid; grid-template-columns: 230px minmax(260px, 1fr) 280px; gap:10px; align-items:center; padding:7px 0; border-top:1px solid #f1f5f9; }}
    .wf-row:first-of-type {{ border-top:none; }}
    .wf-label {{ min-width:0; }}
    .wf-key {{ font-size:12px; font-weight:700; color:#0f172a; }}
    .wf-summary {{ font-size:11px; color:#64748b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .wf-track-wrap {{ position:relative; height:20px; border-radius:999px; overflow:visible; background:#f8fafc; border:1px solid #e2e8f0; }}
    .wf-track-zones {{ position:absolute; inset:0; display:flex; border-radius:999px; overflow:hidden; }}
    .wf-zone.green {{ background:#dcfce7; }}
    .wf-zone.amber {{ background:#fef3c7; }}
    .wf-zone.red {{ background:#fee2e2; }}
    .wf-progress {{ position:absolute; inset:0 auto 0 0; border-radius:999px; opacity:0.9; }}
    .wf-progress.green {{ background:#16a34a; }}
    .wf-progress.amber {{ background:#d97706; }}
    .wf-progress.red {{ background:#dc2626; }}
    .wf-marker {{ position:absolute; top:-3px; width:8px; height:24px; border-radius:8px; transform:translateX(-50%); border:2px solid #fff; box-shadow:0 0 0 1px rgba(15,23,42,0.18); }}
    .wf-marker.green {{ background:#16a34a; }}
    .wf-marker.amber {{ background:#d97706; }}
    .wf-marker.red {{ background:#dc2626; }}
    .wf-age {{ position:absolute; top:-18px; font-size:10px; color:#334155; white-space:nowrap; font-weight:600; }}
    .wf-meta {{ display:flex; gap:6px; align-items:center; flex-wrap:wrap; font-size:10.5px; color:#334155; }}
    .feature-meta {{ margin-top:8px; max-height:290px; overflow:auto; border-top:1px solid var(--line); padding-top:10px; }}
    .feature-meta-row {{ display:grid; grid-template-columns: 1.7fr 0.9fr 0.8fr 0.9fr 1fr 0.9fr; gap:8px; align-items:center; font-size:12px; padding:8px 0; border-bottom:1px solid #f1f5f9; }}
    .table-wrap {{ margin-top:16px; background:var(--surface); border:1px solid var(--line); border-radius:14px; overflow:auto; }}
    table {{ border-collapse:collapse; width:100%; min-width:1320px; }}
    th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:13px; }}
    th {{ background:#f1f5f9; position:sticky; top:0; z-index:1; }}
    .key-cell {{ display:flex; align-items:flex-start; gap:7px; min-width:0; }}
    .key-content {{ min-width:0; }}
    .key-cell .summary {{ margin-top:3px; font-size:12px; color:var(--muted); }}
    .tree-toggle {{ border:none; background:#eef2ff; color:#334155; border-radius:5px; width:18px; height:18px; line-height:18px; font-size:11px; cursor:pointer; padding:0; flex:0 0 18px; }}
    .tree-toggle:hover {{ background:#e2e8f0; }}
    .tree-spacer {{ width:18px; height:18px; flex:0 0 18px; }}
    .chip {{ padding:4px 8px; border-radius:999px; font-size:11px; font-weight:700; }}
    .chip.green {{ background:#dcfce7; color:#14532d; }}
    .chip.amber {{ background:#fef3c7; color:#78350f; }}
    .chip.red {{ background:#fee2e2; color:#7f1d1d; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1 style="margin:0;">Jira Health Report - {html_escape(root_key)}</h1>
      <div class="sub">Scope: {html_escape(scope.upper())} | Root Type: {html_escape(root_type or "Unknown")} | Generated (UTC): {html_escape(generated_at)}</div>
      <div class="status">{overall_status.upper()}</div>
    </div>

    <div class="grid">
      <div class="card">
        <h3 style="margin:0 0 8px 0;">Overall Distribution</h3>
        {donut_svg}
        <div class="legend">
          <span><span class="dot" style="background:var(--green)"></span>Green ({counts.get("green", 0)})</span>
          <span><span class="dot" style="background:var(--amber)"></span>Amber ({counts.get("amber", 0)})</span>
          <span><span class="dot" style="background:var(--red)"></span>Red ({counts.get("red", 0)})</span>
        </div>
      </div>
      <div class="card">
        <h3 style="margin:0 0 4px 0;">Feature Health Waterfall</h3>
        <div class="sub">Each row shows feature key/name, inactivity aging, status, target end date, and days remaining to epic target.</div>
        {feature_graph_svg}
        <div class="feature-meta">
          {''.join(feature_rows_html) if feature_rows_html else '<div class="sub">No feature data available.</div>'}
        </div>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Issue</th><th>Type</th><th>Assignee</th><th>Jira Status</th><th>Health</th>
            <th>Target Date</th><th>Last Activity</th><th>Days To Target</th>
            <th>Days Since Activity</th><th>Comments</th><th>Worklogs</th><th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </div>
  </div>
  <script>
    (() => {{
      const rows = Array.from(document.querySelectorAll("tbody tr.tree-row"));
      if (!rows.length) return;

      const rowByKey = new Map(rows.map((row) => [row.dataset.key, row]));
      const hasCollapsedAncestor = (row) => {{
        let parentKey = row.dataset.parent || "";
        while (parentKey) {{
          const parentRow = rowByKey.get(parentKey);
          if (!parentRow) break;
          if (parentRow.dataset.collapsed === "1") return true;
          parentKey = parentRow.dataset.parent || "";
        }}
        return false;
      }};

      const refresh = () => {{
        rows.forEach((row) => {{
          const isRoot = row.dataset.depth === "0";
          row.style.display = !isRoot && hasCollapsedAncestor(row) ? "none" : "";
          const btn = row.querySelector(".tree-toggle");
          if (!btn) return;
          const collapsed = row.dataset.collapsed === "1";
          btn.textContent = collapsed ? "▸" : "▾";
          btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
        }});
      }};

      rows.forEach((row) => {{
        const btn = row.querySelector(".tree-toggle");
        if (!btn) return;
        btn.addEventListener("click", (ev) => {{
          ev.preventDefault();
          row.dataset.collapsed = row.dataset.collapsed === "1" ? "0" : "1";
          refresh();
        }});
      }});

      refresh();
    }})();
  </script>
</body>
</html>"""


def load_settings(path: str) -> Dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    if not path:
        return settings
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")
    override = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(override, dict):
        raise ValueError("Settings file must contain a JSON object")
    return deep_merge(settings, override)


def validate_scope(epic_key: str, feature_key: str) -> Tuple[str, str]:
    epic = sanitize_key(epic_key)
    feature = sanitize_key(feature_key)
    if bool(epic) == bool(feature):
        raise ValueError("Provide exactly one of --epic-key or --feature-key")
    if epic:
        return "epic", epic
    return "feature", feature


def build_output_paths(output_dir: str, scope: str, root_key: str) -> Tuple[Path, Path, Path]:
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"jira_health_{scope}_{sanitize_key(root_key)}_{stamp}"
    return (
        out_dir / f"{base}.json",
        out_dir / f"{base}.md",
        out_dir / f"{base}.html",
    )


def main() -> int:
    args = parse_args()
    scope, root_key = validate_scope(args.epic_key, args.feature_key)
    settings = load_settings(args.settings)

    jira_url = sanitize_text(args.jira_url, multiline=False)
    jira_email = sanitize_text(args.jira_email, multiline=False)
    jira_token = sanitize_text(args.jira_token, multiline=False)
    if not jira_url or not jira_token:
        raise ValueError("Missing Jira credentials: --jira-url and --jira-token are required")
    if args.jira_auth_mode == "basic" and not jira_email:
        raise ValueError("--jira-email is required for basic auth mode")

    if args.auth_debug:
        print(
            json.dumps(
                {
                    "jiraUrl": jira_url,
                    "authMode": args.jira_auth_mode,
                    "apiVersion": args.jira_api_version,
                    "emailProvided": bool(jira_email),
                    "tokenLength": len(jira_token),
                },
                indent=2,
            ),
        )

    client = JiraClient(
        base_url=jira_url,
        email=jira_email,
        token=jira_token,
        auth_mode=args.jira_auth_mode,
        api_version=args.jira_api_version,
        max_retries=args.max_retries,
        backoff=args.retry_backoff_seconds,
    )

    analyzer = HealthAnalyzer(client, settings)
    epic_arg = root_key if scope == "epic" else ""
    feature_arg = root_key if scope == "feature" else ""
    root_key, root_type, edges, parent_by_child = analyzer.build_hierarchy(
        epic_key=epic_arg,
        feature_key=feature_arg,
    )
    health_map = analyzer.calculate_health(
        root_key=root_key,
        edges=edges,
        parent_by_child=parent_by_child,
    )
    overall_status, counts = rollup_status(health_map, settings)

    report_json = {
        "scope": scope,
        "rootKey": root_key,
        "rootIssueType": root_type,
        "overallHealth": overall_status,
        "counts": counts,
        "settingsUsed": settings,
        "edges": edges,
        "issues": {k: asdict(v) for k, v in health_map.items()},
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
    }

    json_path, md_path, html_path = build_output_paths(args.output_dir, scope, root_key)
    json_path.write_text(json.dumps(report_json, indent=2), encoding="utf-8")
    markdown = render_markdown_report(
        scope=scope,
        root_key=root_key,
        root_type=root_type,
        overall_status=overall_status,
        counts=counts,
        edges=edges,
        health_map=health_map,
        settings=settings,
    )
    md_path.write_text(markdown, encoding="utf-8")
    html_report = render_html_report(
        scope=scope,
        root_key=root_key,
        root_type=root_type,
        overall_status=overall_status,
        counts=counts,
        edges=edges,
        health_map=health_map,
    )
    html_path.write_text(html_report, encoding="utf-8")

    print(f"Overall health: {overall_status.upper()} ({counts})")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(f"HTML report: {html_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
