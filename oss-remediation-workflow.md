# OSS Remediation Workflow (Maven, Gradle, npm)

This workflow standardizes how to scan and remediate OSS vulnerabilities using DbSaicle across Maven, Gradle, and npm projects.

## Prerequisites

- `oss_vulnerability_scan` is configured (JFrog platform URL and access token).
- You can run builds locally from the project root.

## Step 1: Get the Project Directory

Ask the user for the project root directory.

Use the root that contains:
- **Maven**: `pom.xml`
- **Gradle**: `build.gradle` or `build.gradle.kts`
- **npm**: `package.json`

Example tool input:
```json
{
  "project_dir": "/path/to/project-root"
}
```

## Step 2: Ensure the Current Build Succeeds (With Tests)

Run the standard build command. If it fails, fix the build and retry until it is green.

Common commands:
- **Maven**: `mvn clean verify`
- **Gradle**: `./gradlew build`
- **npm**: `npm test` and/or `npm run build` (use the project standard)

## Step 3: Run the OSS Vulnerability Scan

Call the tool and wait for the report:

- Tool name: `oss_vulnerability_scan`
- Input: `project_dir` (from Step 1)

The tool prints a Markdown report with total dependencies scanned and vulnerability summary.

## Step 4: Fix High and Critical Vulnerabilities

Read the scan report and remediate **High** and **Critical** items first.

Suggested approach:
- Identify whether the dependency is **direct** or **transitive**.
- Update the dependency or constraint to a fixed version.
- Re-run the scan to confirm the vulnerability is resolved.

Common update locations:
- **Maven**: `pom.xml` or `dependencyManagement`
- **Gradle**: `build.gradle` (dependencies or constraints)
- **npm**: `package.json` and lockfile (`package-lock.json` or `yarn.lock`)

Repeat this step until High and Critical counts are zero (or explicitly accepted).

## Step 5: Build Without Tests

Run a build without tests and fix any failures until it succeeds.

Common commands:
- **Maven**: `mvn -DskipTests clean package`
- **Gradle**: `./gradlew build -x test`
- **npm**: `npm run build` (if tests are part of build, use the project-specific flag to skip them)

If the build fails, fix the issues and retry until it is green.
