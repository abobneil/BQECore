# BQE Core App Setup for Python Exports

This guide is based on the BQE Core docs at `https://api-explorer.bqecore.com/docs/getting-started`, starting from **Add Your Application** and continuing through the OAuth flow and first API call.

The goal is to set up a BQE Core app so the Python exporter in this repo can authenticate, connect, and export data.

## What this repo expects

The exporter in `scripts/export_bqe_core.py` uses OAuth 2.0 Authorization Code flow and can store tokens in a local cache.

- Authorization endpoint: `https://api-identity.bqecore.com/idp/connect/authorize`
- Token endpoint: `https://api-identity.bqecore.com/idp/connect/token`
- Default API base URL: `https://api.bqecore.com/api`
- Token cache: `%USERPROFILE%\.bqe_core_export_tokens.json`

Because this exporter uses a `client_secret`, the safest app type for this repo is **Regular Web App**.

## 1. Add your application in the Developer Portal

Per the BQE docs, start in the Developer Portal and create an application entry for your script.

1. Sign in to the BQE Core **Developer Portal**.
2. On the **Dashboard**, select **Add New Application**.
3. Enter the application details:
   - **Application Name**: any name you want, such as `BQE Core Exporter`
   - **Application Type**: `Regular Web App`
   - **Redirect URI**: add at least one callback URL
   - **Description**: optional but helpful
   - **Post Logout Redirect URI**: optional
4. Click **Create**.
5. Copy and save the generated **Client Secret** immediately.
6. Open the app details and copy the **Client ID**.

## 2. Pick a redirect URI you can use locally

The docs say the `redirect_uri` used during authorization must exactly match one of the Redirect URIs registered for the app.

For this repo, a practical local value is:

- `http://localhost:8400/callback`

Important rules from the docs:

- Scheme, host, path, trailing slash, and case must match exactly.
- Extra query parameters can be appended at runtime, but the base URI must still match.
- If the registered URI and runtime URI do not match, authorization fails.

Recommended approach:

- Register a simple URI with no query string.
- Reuse that exact value everywhere: in the portal, environment variables, and command-line arguments.

### Local callback note

This exporter does **not** start a local web server. After login and consent, BQE redirects the browser to your callback URL with a `code` query parameter.

If nothing is listening on `localhost:8400`, the browser may show a connection error. That is usually fine. Copy the **full URL from the browser address bar** and paste it into the terminal when the script asks for it.

## 3. Choose the scopes for export access

From the docs:

- Your app must request at least one basic scope such as `read:core` or `readwrite:core`.
- Add `offline_access` if you want a `refresh_token`.
- `refresh_token` lets the script renew access without making you log in every time.

For read-only exports, use:

- `read:core offline_access`

The Python exporter in this repo also supports setting scope explicitly with `--scope` or `BQE_CORE_SCOPE`.

## 4. Set your local environment variables

In PowerShell, set the values you copied from the Developer Portal:

```powershell
$env:BQE_CORE_CLIENT_ID = "<your-client-id>"
$env:BQE_CORE_CLIENT_SECRET = "<your-client-secret>"
$env:BQE_CORE_REDIRECT_URI = "http://localhost:8400/callback"
$env:BQE_CORE_SCOPE = "read:core offline_access"
```

Optional:

```powershell
$env:BQE_CORE_TOKEN_CACHE = "$HOME\.bqe_core_export_tokens.json"
$env:BQE_CORE_API_BASE_URL = "https://api.bqecore.com/api"
```

You can also copy `.env.example` to `.env`, fill in your values, and load that file into your PowerShell session.

For convenience, you can use the helper script:

```powershell
.\scripts\load-env.ps1
```

The export wrapper now auto-loads `.env` from the repo root if that file exists, so in the common case you can just run:

```powershell
.\scripts\run-bqe-core-export.ps1
```

If you saved those values in a local `.env` file, load them into your current PowerShell session with:

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s]' } | ForEach-Object { $name, $value = $_ -split '=', 2; $value = $value.Trim().Trim('"'); Set-Item -Path ("Env:" + $name.Trim()) -Value $value }
```

Notes:

- The exporter normally learns the correct API base URL from the token response `endpoint` field.
- If your tenant returns a different data-center-specific `endpoint`, the exporter will use that value automatically after login.

## 5. Run the first interactive authorization

Use the Python script once interactively to seed the token cache and verify that your app is configured correctly.

From the repo root:

```powershell
python scripts/export_bqe_core.py `
  --client-id $env:BQE_CORE_CLIENT_ID `
  --client-secret $env:BQE_CORE_CLIENT_SECRET `
  --redirect-uri $env:BQE_CORE_REDIRECT_URI `
  --scope $env:BQE_CORE_SCOPE `
  --endpoint company `
  --output-dir exports\bqe-core-auth-test
```

If you are loading credentials from `.env`, you can run the same first-time authorization as a single PowerShell command:

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s]' } | ForEach-Object { $name, $value = $_ -split '=', 2; $value = $value.Trim().Trim('"'); Set-Item -Path ("Env:" + $name.Trim()) -Value $value }; python scripts/export_bqe_core.py --client-id $env:BQE_CORE_CLIENT_ID --client-secret $env:BQE_CORE_CLIENT_SECRET --redirect-uri $env:BQE_CORE_REDIRECT_URI --scope $env:BQE_CORE_SCOPE --endpoint company --output-dir exports\bqe-core-auth-test
```

What happens next:

1. The script builds the BQE authorization URL.
2. Your browser opens to the BQE login page.
3. Sign in with your CORE company credentials.
4. Review and approve the consent screen.
5. After redirect, copy the full callback URL from the browser.
6. Paste that URL into the terminal.
7. The script exchanges the authorization code for tokens and saves them locally.

If successful, you should end up with:

- a token cache file at `%USERPROFILE%\.bqe_core_export_tokens.json` unless you changed the path
- an export folder such as `exports\bqe-core-auth-test`

## 6. What the token exchange is doing

Per the docs, after you receive the authorization code, your app sends a `POST` to the token endpoint with:

- `code`
- `redirect_uri`
- `grant_type=authorization_code`
- `client_id`
- `client_secret`

The successful token response includes:

- `access_token`
- `refresh_token` when `offline_access` was granted
- `endpoint` for your API base URL
- `expires_in`

This repo stores those values and reuses them for later exports.

## 7. Run exports after the first login

After the token cache exists, you can use the wrapper script for repeatable exports.

### Option A: use the PowerShell wrapper

```powershell
.\scripts\run-bqe-core-export.ps1
```

If you are using `.env`, you can load the values and run the wrapper in one command:

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s]' } | ForEach-Object { $name, $value = $_ -split '=', 2; $value = $value.Trim().Trim('"'); Set-Item -Path ("Env:" + $name.Trim()) -Value $value }; .\scripts\run-bqe-core-export.ps1
```

This wrapper:

- uses `scripts\bqe-core-endpoints.txt`
- writes output under `exports\bqe-core-<timestamp>`
- writes logs under `exports\logs`
- reuses the cached tokens when possible

Useful examples:

```powershell
.\scripts\run-bqe-core-export.ps1 -DownloadDocumentFiles
```

```powershell
.\scripts\run-bqe-core-export.ps1 -FailFast
```

```powershell
.\scripts\run-bqe-core-export.ps1 -PageBatchSize 5
```

`-PageBatchSize` controls how many pages the exporter requests concurrently for each endpoint. The API still returns one page per HTTP request, but the exporter can now fetch multiple pages in parallel to speed up large exports.

Adaptive throttling is enabled by default when `-PageBatchSize` is greater than `1`. The exporter starts conservatively, watches page response times, and automatically reduces concurrency if it encounters `429` retries.

```powershell
.\scripts\run-bqe-core-export.ps1 -PageBatchSize 5 -TargetRequestsPerMinute 60
```

```powershell
.\scripts\run-bqe-core-export.ps1 -PageBatchSize 5 -NoAdaptivePageBatching
```

### Incremental exports after the first run

The exporter now supports checkpoint-based incremental exports.

- Most endpoints use `lastUpdated` as the watermark field.
- Incremental runs save checkpoints in `exports\bqe-core-incremental-state.json` by default.
- Incremental runs also add the `deletedhistory` endpoint automatically so you can track deletes.
- The CRM list endpoints (`crm/lists/leadsource`, `crm/lists/region`, and `crm/lists/score`) do not expose a documented timestamp field, so they still run as full exports unless you override the behavior.

To seed the checkpoint file from a full export and use it for later runs:

```powershell
.\scripts\run-bqe-core-export.ps1 -Incremental
```

Run the same command again later and the exporter requests only records changed since the saved checkpoint, with a small overlap window to avoid missing edge-case updates.

Useful incremental examples:

```powershell
.\scripts\run-bqe-core-export.ps1 -Incremental -IncrementalOverlapSeconds 600
```

```powershell
.\scripts\run-bqe-core-export.ps1 -Incremental -IncrementalStart 2026-03-01T00:00:00
```

```powershell
.\scripts\run-bqe-core-export.ps1 -Incremental -IncrementalField customlist=createdOn
```

### Option B: run the Python exporter directly

```powershell
python scripts/export_bqe_core.py `
  --endpoints-file scripts/bqe-core-endpoints.txt `
  --output-dir exports\manual-run
```

```powershell
python scripts/export_bqe_core.py `
  --endpoints-file scripts/bqe-core-endpoints.txt `
  --page-batch-size 5 `
  --output-dir exports\manual-run
```

```powershell
python scripts/export_bqe_core.py `
  --endpoints-file scripts/bqe-core-endpoints.txt `
  --page-batch-size 5 `
  --target-requests-per-minute 60 `
  --output-dir exports\manual-run
```

You can also limit the export to a few endpoints:

```powershell
python scripts/export_bqe_core.py `
  --endpoint client `
  --endpoint project `
  --endpoint invoice `
  --output-dir exports\sample-export
```

Incremental examples with the Python exporter:

```powershell
python scripts/export_bqe_core.py `
  --incremental `
  --endpoint invoice `
  --output-dir exports\invoice-delta
```

```powershell
python scripts/export_bqe_core.py `
  --incremental `
  --incremental-start 2026-03-01T00:00:00 `
  --endpoint timeentry `
  --output-dir exports\timeentry-delta
```

```powershell
python scripts/export_bqe_core.py `
  --incremental `
  --incremental-field customlist=createdOn `
  --endpoint customlist `
  --output-dir exports\customlist-delta
```

## 8. Curate exports for Power BI

After a raw export completes, use the curation step to turn the JSON snapshot into stable Power BI-ready tables.

The curation script in this repo is:

- `scripts\curate_bqe_core_powerbi.py`

The PowerShell wrapper is:

- `scripts\run-bqe-core-curation.ps1`

### Recommended output shape

Use multiple curated files, not one giant combined file.

Recommended pattern:

- one folder per curated table
- one `current.csv` per table by default
- one stable root such as `exports\current`

This matches the reporting plan and works better for Power BI because each table keeps its own grain and relationships.

Examples:

- `exports\current\stg_client\current.csv`
- `exports\current\stg_project\current.csv`
- `exports\current\stg_employee\current.csv`
- `exports\current\stg_activity\current.csv`
- `exports\current\stg_timeentry\current.csv`
- `exports\current\stg_payment\current.csv`
- `exports\current\stg_invoice\current.csv`
- `exports\current\stg_bill\current.csv`
- `exports\current\stg_check\current.csv`
- `exports\current\stg_document\current.csv`
- `exports\current\stg_crm_prospect\current.csv`
- `exports\current\stg_crm_leadsource\current.csv`
- `exports\current\stg_crm_region\current.csv`
- `exports\current\stg_crm_score\current.csv`

If you need a single upload artifact for transport or handoff, keep the curated output as multiple table files and use the optional zip file instead of flattening everything into one CSV.

### Run the curation wrapper

Use the latest export automatically:

```powershell
.\scripts\run-bqe-core-curation.ps1
```

Point at a specific raw export folder:

```powershell
.\scripts\run-bqe-core-curation.ps1 `
  -SourceDir exports\bqe-core-20260311-132503 `
  -OutputDir exports\current
```

Build a zip archive after the curated files are created:

```powershell
.\scripts\run-bqe-core-curation.ps1 `
  -SourceDir exports\bqe-core-20260311-132503 `
  -OutputDir exports\current `
  -ZipOutput
```

Limit the run to a few tables:

```powershell
.\scripts\run-bqe-core-curation.ps1 `
  -SourceDir exports\bqe-core-20260311-132503 `
  -OutputDir exports\current `
  -Tables stg_client,stg_project,stg_timeentry
```

Split very large tables into multiple CSV parts:

```powershell
.\scripts\run-bqe-core-curation.ps1 `
  -SourceDir exports\bqe-core-20260311-132503 `
  -OutputDir exports\current `
  -RowsPerPart 250000
```

When `-RowsPerPart` is set, the script writes files such as `part-00001.csv`, `part-00002.csv`, and so on for only the tables that need splitting.

### Run the Python curation script directly

```powershell
python scripts/curate_bqe_core_powerbi.py `
  --source-dir exports\bqe-core-20260311-132503 `
  --output-dir exports\current `
  --zip-output
```

Useful options:

- `--tables` to build only selected curated tables
- `--rows-per-part` to split large outputs into multiple CSV files
- `--max-rows-per-table` for a quick sample or smoke test
- `--zip-output` to package the curated folder as a zip archive

### What the curation step does

- keeps only report-friendly columns from the raw export
- normalizes IDs and blank zero GUID values
- casts dates, booleans, whole numbers, and decimals into stable CSV values
- preserves business keys needed for Power BI relationships
- writes a `manifest.json` file under the curated output root
- records endpoint failures from `export_summary.json` so the downstream process can see incomplete runs

Recommended refresh order:

1. run the raw export
2. rebuild the curated output
3. point Power BI to `exports\current`
4. refresh the Power BI dataset

## 9. How API calls work after login

The docs say all API requests must include:

- `Authorization: Bearer <access_token>`
- the base URL from the token response `endpoint` field

The exporter already does this for you. If you want to verify the connection manually in Python, a minimal example looks like this:

```python
import requests

access_token = "<your-access-token>"
base_url = "https://api.bqecore.com/api"

response = requests.get(
    f"{base_url}/company",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    },
    timeout=120,
)

response.raise_for_status()
print(response.json())
```

If your token response returned a different `endpoint`, use that value instead of the default base URL.

For paged collection endpoints, the exporter sends the `page` query parameter as `<page number>,<page size>`. When you set `--page-batch-size` or `-PageBatchSize`, it sends several of those page requests concurrently and still writes the results in page order. By default it also adapts the live batch size based on observed page durations and backs off when the API starts returning `429` retries.

## 10. Troubleshooting

### Redirect URI mismatch

Symptoms:

- BQE shows an error before returning to your callback URL.

Fix:

- Make sure the value in the Developer Portal exactly matches the value you pass to `--redirect-uri`.
- Check scheme, host, path, trailing slash, and case.

### `invalid_scope`

Symptoms:

- Authorization fails during login or token exchange.

Fix:

- Start with `read:core offline_access` for export use.
- Request `readwrite:core` only if you really need write access.

### `invalid_client`

Symptoms:

- Token exchange fails.

Fix:

- Re-copy the Client ID and Client Secret from the Developer Portal.
- Confirm the app was created as a `Regular Web App`.
- If you rotated the secret, update your local environment variable.

### No authorization code found

Symptoms:

- The script says no authorization code was found in the callback value.

Fix:

- Paste the full redirected URL, not just the code.
- Make sure the URL contains `?code=...` and ideally `&state=...`.

### Export wrapper says no auth material found

Symptoms:

- `run-bqe-core-export.ps1` fails before starting.

Fix:

- Run the interactive Python command in Step 5 once to create the token cache.
- Or provide `BQE_CORE_ACCESS_TOKEN` explicitly.

### Need to sign in again with a different BQE account

Symptoms:

- The exporter keeps reusing the old cached login.
- You changed the BQE account used for API access and want a fresh sign-in.

Fix:

- Remove the cached token file:

```powershell
Remove-Item "$HOME\.bqe_core_export_tokens.json" -Force -ErrorAction SilentlyContinue
```

- Remove any manually set access token override:

```powershell
Remove-Item Env:BQE_CORE_ACCESS_TOKEN -ErrorAction SilentlyContinue
```

- Then run the interactive authorization command again:

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s]' } | ForEach-Object { $name, $value = $_ -split '=', 2; $value = $value.Trim().Trim('"'); Set-Item -Path ("Env:" + $name.Trim()) -Value $value }; python scripts/export_bqe_core.py --client-id $env:BQE_CORE_CLIENT_ID --client-secret $env:BQE_CORE_CLIENT_SECRET --redirect-uri $env:BQE_CORE_REDIRECT_URI --scope $env:BQE_CORE_SCOPE --endpoint company --output-dir exports\bqe-core-auth-test
```

- If the browser still lands on the old account automatically, sign out of BQE first or use an InPrivate browser window before pasting the callback URL.

## 11. Recommended first-run checklist

- App type is `Regular Web App`
- Redirect URI is registered and copied exactly
- Client ID and Client Secret are saved locally
- Scope includes `read:core offline_access`
- First interactive Python run completes successfully
- Token cache is created
- Wrapper script runs and writes files under `exports`
- Curation script builds `exports\current` for Power BI

Once those steps are complete, your Python exporter is set up to connect to BQE Core and export data.
