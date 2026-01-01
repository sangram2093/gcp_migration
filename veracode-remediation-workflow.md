# Veracode Remediation Workflow

This workflow standardizes how to scan and remediate Veracode findings using DbSaicle for build artifacts.

## Prerequisites

- `veracode_pipeline_scan` is configured (API ID + API Key).
- A build artifact is available or can be assembled from build outputs.

## Step 1: Collect Inputs

Ask the user for:
- `artifact_path` (path to the artifact to scan)
- `output_json_path` (where to save raw findings JSON)

Example tool input:
```json
{
  "artifact_path": "dist/app.jar",
  "output_json_path": "veracode-findings.json"
}
```

## Step 2: Ensure Artifact Size Is Within 200 MB

If the artifact is larger than 200 MB:
1. Inspect the current directory for build outputs.
2. For Java projects, prefer `target/classes` (or module `*/target/classes`).
3. For other project types, use the most relevant build output:
   - UI: `dist/`, `build/`
   - Python: `build/`, `dist/`, or a package folder containing compiled assets
   - Other: choose the directory with compiled binaries or runtime assets
4. Zip the selected folder(s) and use the zip file as `artifact_path`.

Windows (PowerShell) example:
```powershell
Compress-Archive -Path target\\classes\\* -DestinationPath artifact.zip
```

macOS/Linux example:
```bash
zip -r artifact.zip target/classes
```

Then update the tool input:
```json
{
  "artifact_path": "artifact.zip",
  "output_json_path": "veracode-findings.json"
}
```

## Step 3: Run Veracode Pipeline Scan

Run the tool:
- Tool name: `veracode_pipeline_scan`
- Inputs: `artifact_path`, `output_json_path`

After completion:
- Present a summary to the user (scan ID, total findings, severity counts).
- Show the findings in a readable Markdown format.
- Confirm the `output_json_path` where raw JSON is saved.

## Step 4: Remediate High and Critical Findings

1. Fix all High and Critical findings first.
2. Build **without tests** to validate compilation and packaging.

Common commands:
- Maven: `mvn -DskipTests clean package`
- Gradle: `./gradlew build -x test`
- npm: `npm run build`

If the build fails, fix and retry until it succeeds.

## Step 5: Re-scan and Confirm

Re-run `veracode_pipeline_scan` with the updated artifact.
Repeat remediation until high and critical findings are resolved and the build passes without tests.
