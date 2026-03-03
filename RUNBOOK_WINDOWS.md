# dbCastle Local UI - Windows User Guide

This guide explains how to install, start, and configure dbCastle UI on Windows.

## 1) Install and Launch

Prerequisite:
- Node.js 22 must be installed and available in PATH (`node -v` should show v22.x).

1. Copy the UI bundle ZIP file to `Downloads` (or another folder where you have full access).
2. Unzip the file.
3. Open PowerShell from the unzipped folder.
4. Run:
   ```powershell
   .\start.ps1
   ```
5. Open a browser and navigate to:
   ```text
   http://127.0.0.1:4173
   ```
6. dbCastle UI should open.

## 2) LLM Model Setup (VertexAI Enterprise)

1. Click **Add Chat Model** (top-left).
2. Select **Provider**: `VertexAI Enterprise`.
3. Enter:
   - **Project Id**: your GCP project id
   - **Region**: your GCP Vertex AI region
   - **Keyfile JSON Path**: full path to `keyfile.json` (without quotes)
4. Click **Add Model**.
5. Wait for success confirmation and modal close.
6. The model is saved in the active `config.yaml` used by the bundle.
7. You can now start interacting with dbCastle.

## 3) Built-In Tools and Credential Setup

- dbCastle provides **124 built-in tools**.
- Tools like Jira, Confluence, ServiceNow, OSS Vulnerability, and Veracode require credentials.

### Credential Setup Steps

1. Click **Credentials** (top-left).
2. Select the required service from the **Service** dropdown.
3. Keep **Profile** as `default` (or choose your profile standard).
4. Enter the secret in the **Value** field for the selected key.
5. Click **Save**.
6. Confirm the saved key appears in **Stored Keys**.

Secrets are stored securely in the OS secret manager.

## 4) `config.yaml` Secret Profile Reference

Add the following blocks (as needed) in your `config.yaml`:

```yaml
jira:
  domain: "https://<your-jira-domain>"
  authEmail: "<your-email>"
  secretProfile: default

confluence:
  confluenceBaseUrl: "https://<your-confluence-domain>/wiki"
  userEmail: "<your-email>"
  secretProfile: default

servicenow:
  instanceUrl: "https://<your-instance>.service-now.com"
  auth:
    type: basic
    basic:
      username: "<servicenow-username>"
  secretProfile: default

ossVulnerability:
  jfrogPlatformUrl: "https://<your-jfrog-platform-url>"
  secretProfile: default

veracode:
  apiKeyId: "<your-veracode-api-key-id>"
  baseUrl: "https://api.veracode.com"
  userAgent: "dbsaicle-veracode"
  secretProfile: default
```

Note:
- Keep secrets in **Credentials UI** (preferred), not plain text in `config.yaml`.

## 5) Sample Prompts for New Users

### General
- `Summarize this project in business terms.`
- `Create a step-by-step plan for implementing this requirement.`

### Workspace / Code
- `Read and analyze the current workspace.`
- `List key modules and potential risks in this codebase.`

### Jira
- `Get details for Jira NTS-40000.`
- `Generate a health report for Jira NTS-40000.`

### Confluence
- `Search Confluence for pages containing "WIF onboarding".`
- `Summarize this Confluence page for business stakeholders.`

### ServiceNow
- `Get incident details for INC39387538.`
- `List active incidents assigned to my team.`

### Security
- `Run OSS vulnerability scan and summarize critical findings.`
- `Run Veracode pipeline scan and provide remediation priorities.`

## 6) Stop dbCastle

In the PowerShell window running dbCastle, press:

```text
Ctrl + C
```
