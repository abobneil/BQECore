#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


IDENTITY_BASE_URL = "https://api-identity.bqecore.com/idp"
DEFAULT_API_BASE_URL = "https://api.bqecore.com/api"
DEFAULT_SCOPE = "read:core offline_access"
DEFAULT_PAGE_SIZE = 1000
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_USER_AGENT = "bqe-core-exporter/1.0"
DEFAULT_TOKEN_CACHE = Path.home() / ".bqe_core_export_tokens.json"
DEFAULT_INCREMENTAL_STATE_FILE = Path("exports") / "bqe-core-incremental-state.json"
DEFAULT_INCREMENTAL_OVERLAP_SECONDS = 300
DEFAULT_INCREMENTAL_FIELD = "lastUpdated"
DELETED_HISTORY_ENDPOINT = "deletedhistory"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_ENDPOINTS = [
    "activity",
    "allocation",
    "bill",
    "check",
    "client",
    "company",
    "document",
    "employee",
    "feeschedule",
    "invoice",
    "payment",
    "project",
    "resourceschedule",
    "timeentry",
    "hr/benefit",
    "hr/employeebenefit",
    "hr/employeebenefitusage",
    "hr/journal",
    "hr/journaltype",
    "hr/question",
    "hr/review",
    "hr/reviewtemplate",
    "crm/lists/leadsource",
    "crm/prospect",
    "crm/lists/region",
    "crm/lists/score",
]
NON_INCREMENTAL_DEFAULT_ENDPOINTS = {
    "crm/lists/leadsource",
    "crm/lists/region",
    "crm/lists/score",
}
DEFAULT_INCREMENTAL_FIELDS: dict[str, str | None] = {
    endpoint: DEFAULT_INCREMENTAL_FIELD
    for endpoint in DEFAULT_ENDPOINTS
    if endpoint not in NON_INCREMENTAL_DEFAULT_ENDPOINTS
}
for _endpoint in NON_INCREMENTAL_DEFAULT_ENDPOINTS:
    DEFAULT_INCREMENTAL_FIELDS[_endpoint] = None
DEFAULT_INCREMENTAL_FIELDS[DELETED_HISTORY_ENDPOINT] = "deletedOn"


class ExportError(RuntimeError):
    pass


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    endpoint: str | None = None
    scope: str | None = None
    expires_in: int | None = None
    expires_at: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OAuthTokens":
        expires_in = payload.get("expires_in")
        expires_at = payload.get("expires_at")
        if expires_at is None and expires_in is not None:
            try:
                expires_at = time.time() + int(expires_in)
            except (TypeError, ValueError):
                expires_at = None
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            token_type=payload.get("token_type") or "Bearer",
            endpoint=payload.get("endpoint"),
            scope=payload.get("scope"),
            expires_in=_maybe_int(expires_in),
            expires_at=expires_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def authorization_header(self) -> str:
        return f"{self.token_type} {self.access_token}".strip()

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= (self.expires_at - buffer_seconds)


@dataclass
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8")


class TokenStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> OAuthTokens | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not payload or "access_token" not in payload:
            return None
        return OAuthTokens.from_dict(payload)

    def save(self, tokens: OAuthTokens) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(tokens.to_dict(), indent=2), encoding="utf-8")


class IncrementalStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        default_state = {
            "version": 1,
            "updatedAt": None,
            "endpoints": {},
        }
        if not self.path.exists():
            return default_state
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ExportError(f"Incremental state file must contain a JSON object: {self.path}")
        endpoints = payload.get("endpoints")
        if not isinstance(endpoints, dict):
            endpoints = {}
        return {
            "version": 1,
            "updatedAt": payload.get("updatedAt"),
            "endpoints": endpoints,
        }

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")


@dataclass
class EndpointExportOptions:
    fields: str | None
    where: str | None
    order_by: str | None
    expand: str | None
    incremental_summary: dict[str, Any] | None = None


class JsonArrayWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w", encoding="utf-8", newline="\n")
        self.handle.write("[")
        self.first_record = True

    def write_records(self, records: list[Any]) -> None:
        for record in records:
            if self.first_record:
                self.handle.write("\n")
                self.first_record = False
            else:
                self.handle.write(",\n")
            json.dump(record, self.handle, ensure_ascii=False)

    def close(self) -> None:
        if not self.handle.closed:
            if not self.first_record:
                self.handle.write("\n")
            self.handle.write("]\n")
            self.handle.close()


class BQEHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: int,
        user_agent: str,
        get_authorization_header: callable,
        refresh_tokens: callable | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.get_authorization_header = get_authorization_header
        self.refresh_tokens = refresh_tokens

    def get_json(self, url: str, query: dict[str, str] | None = None) -> HttpResponse:
        return self._request("GET", url, query=query)

    def get_text(self, url: str, query: dict[str, str] | None = None) -> str:
        response = self._request("GET", url, query=query)
        text = response.text().strip()
        if not text:
            return text
        if text.startswith('"'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text

    def post_form(self, url: str, form_data: dict[str, str], include_auth: bool = False) -> HttpResponse:
        payload = urllib.parse.urlencode(form_data).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return self._request("POST", url, data=payload, extra_headers=headers, include_auth=include_auth)

    def download_file(self, url: str, destination: Path) -> None:
        response = self._request("GET", url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.body)

    def _request(
        self,
        method: str,
        url: str,
        *,
        query: dict[str, str] | None = None,
        data: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        include_auth: bool = True,
        allow_refresh: bool = True,
    ) -> HttpResponse:
        request_url = _build_url(url, query)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        }
        if include_auth:
            authorization = self.get_authorization_header()
            if authorization:
                headers["Authorization"] = authorization
        if extra_headers:
            headers.update(extra_headers)

        request = urllib.request.Request(request_url, data=data, method=method, headers=headers)

        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return HttpResponse(
                        status_code=response.getcode(),
                        headers=dict(response.headers.items()),
                        body=response.read(),
                    )
            except urllib.error.HTTPError as error:
                response = HttpResponse(
                    status_code=error.code,
                    headers=dict(error.headers.items()),
                    body=error.read(),
                )
                if response.status_code == 401 and include_auth and allow_refresh and self.refresh_tokens is not None:
                    refreshed = self.refresh_tokens()
                    if refreshed:
                        return self._request(
                            method,
                            url,
                            query=query,
                            data=data,
                            extra_headers=extra_headers,
                            include_auth=include_auth,
                            allow_refresh=False,
                        )
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < 3:
                    self._sleep_before_retry(response.headers, attempt)
                    continue
                if response.status_code == 204:
                    return response
                raise ExportError(_format_http_error(method, request_url, response)) from error
            except urllib.error.URLError as error:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise ExportError(f"Request failed for {method} {request_url}: {error}") from error
        raise ExportError(f"Request failed for {method} {request_url}")

    def _sleep_before_retry(self, headers: dict[str, str], attempt: int) -> None:
        retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                time.sleep(max(1, int(retry_after)))
                return
            except ValueError:
                pass
        time.sleep(2 ** attempt)


class BQECoreExporter:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.output_dir = Path(args.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.token_store = TokenStore(Path(args.token_cache))
        self.incremental_state_store = IncrementalStateStore(Path(args.incremental_state_file))
        self.tokens: OAuthTokens | None = None
        self.document_downloads: list[dict[str, Any]] = []
        self.incremental_state = self.incremental_state_store.load()
        self.incremental_field_map = _build_incremental_field_map(args)
        self.auto_added_endpoints = set(getattr(args, "auto_added_endpoints", []))
        self.client = BQEHttpClient(
            timeout_seconds=args.request_timeout,
            user_agent=DEFAULT_USER_AGENT,
            get_authorization_header=self._get_authorization_header,
            refresh_tokens=self._refresh_tokens_if_possible,
        )
        self.tokens = self._load_tokens()

    def export_all(self, endpoints: list[str]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "startedAt": _utc_now(),
            "outputDir": str(self.output_dir.resolve()),
            "pageSize": self.args.page_size,
            "downloadDocumentFiles": self.args.download_document_files,
            "endpoints": [],
        }
        if self.args.incremental:
            summary["incremental"] = {
                "enabled": True,
                "stateFile": str(self.incremental_state_store.path.resolve()),
                "overlapSeconds": self.args.incremental_overlap_seconds,
                "autoDeletedHistory": not self.args.no_incremental_deletes,
            }

        for endpoint in endpoints:
            try:
                endpoint_summary = self._export_endpoint(endpoint)
            except Exception as error:
                endpoint_summary = {
                    "endpoint": endpoint,
                    "status": "failed",
                    "error": str(error),
                }
                if self.args.fail_fast:
                    summary["endpoints"].append(endpoint_summary)
                    summary["finishedAt"] = _utc_now()
                    self._write_summary(summary)
                    raise
            summary["endpoints"].append(endpoint_summary)

        if self.document_downloads:
            downloads_path = self.output_dir / "document_downloads.json"
            downloads_path.write_text(json.dumps(self.document_downloads, indent=2), encoding="utf-8")
            summary["documentDownloads"] = {
                "file": downloads_path.name,
                "count": len(self.document_downloads),
            }

        summary["finishedAt"] = _utc_now()
        summary["successCount"] = sum(1 for item in summary["endpoints"] if item.get("status") == "completed")
        summary["failureCount"] = sum(1 for item in summary["endpoints"] if item.get("status") == "failed")
        self._write_summary(summary)
        return summary

    def _export_endpoint(self, endpoint: str) -> dict[str, Any]:
        file_name = f"{_endpoint_to_file_name(endpoint)}.json"
        destination = self.output_dir / file_name
        writer = JsonArrayWriter(destination)
        page_number = 1
        total_records = 0
        pages_fetched = 0
        export_options = self._build_endpoint_export_options(endpoint)
        max_watermark_value: str | None = None
        try:
            while True:
                query = self._build_query(page_number, export_options)
                response = self.client.get_json(_join_url(self._api_base_url(), endpoint), query=query)
                if response.status_code == 204:
                    break
                payload = response.json()
                records, is_collection = _extract_records(payload)
                if not records:
                    break
                writer.write_records(records)
                total_records += len(records)
                pages_fetched += 1
                max_watermark_value = self._max_endpoint_watermark(
                    max_watermark_value,
                    records,
                    export_options.incremental_summary,
                )
                if self.args.download_document_files and endpoint == "document":
                    self._download_documents(records)
                if not is_collection or len(records) < self.args.page_size:
                    break
                page_number += 1
        finally:
            writer.close()

        endpoint_summary: dict[str, Any] = {
            "endpoint": endpoint,
            "status": "completed",
            "file": file_name,
            "records": total_records,
            "pages": pages_fetched,
        }
        if endpoint in self.auto_added_endpoints:
            endpoint_summary["autoAdded"] = True
        if export_options.incremental_summary:
            incremental_summary = dict(export_options.incremental_summary)
            checkpoint_value = self._update_incremental_checkpoint(
                endpoint,
                incremental_summary,
                max_watermark_value,
            )
            if checkpoint_value:
                incremental_summary["savedWatermark"] = checkpoint_value
            endpoint_summary["incremental"] = incremental_summary
        return endpoint_summary

    def _build_query(self, page_number: int, options: EndpointExportOptions) -> dict[str, str]:
        query = {"page": f"{page_number},{self.args.page_size}"}
        if options.fields:
            query["fields"] = options.fields
        if options.where:
            query["where"] = options.where
        if options.order_by:
            query["orderBy"] = options.order_by
        if options.expand:
            query["expand"] = options.expand
        return query

    def _build_endpoint_export_options(self, endpoint: str) -> EndpointExportOptions:
        fields = self.args.fields
        where = self.args.where
        order_by = self.args.order_by
        expand = self.args.expand

        if endpoint in self.auto_added_endpoints:
            fields = None
            where = None
            order_by = None
            expand = None

        if not self.args.incremental:
            return EndpointExportOptions(fields=fields, where=where, order_by=order_by, expand=expand)

        incremental_field = self._get_incremental_field(endpoint)
        if not incremental_field:
            return EndpointExportOptions(
                fields=fields,
                where=where,
                order_by=order_by,
                expand=expand,
                incremental_summary={
                    "enabled": False,
                    "mode": "full",
                    "reason": "No incremental watermark field is configured for this endpoint.",
                },
            )

        state_entry = self.incremental_state.get("endpoints", {}).get(endpoint, {})
        previous_watermark = state_entry.get("watermarkValue") or self.args.incremental_start
        query_watermark = None
        mode = "full"
        reason = "No saved checkpoint found; exporting the full endpoint to seed incremental state."
        if previous_watermark:
            shifted_watermark = _shift_watermark(previous_watermark, self.args.incremental_overlap_seconds)
            query_watermark = shifted_watermark or previous_watermark
            where = _combine_where_clause(where, f"{incremental_field} >= '{query_watermark}'")
            mode = "incremental"
            reason = None
        if not order_by:
            order_by = f"{incremental_field} asc"

        incremental_summary: dict[str, Any] = {
            "enabled": True,
            "mode": mode,
            "field": incremental_field,
            "stateFile": str(self.incremental_state_store.path.resolve()),
        }
        if previous_watermark:
            incremental_summary["previousWatermark"] = previous_watermark
        if query_watermark:
            incremental_summary["queryWatermark"] = query_watermark
        if reason:
            incremental_summary["reason"] = reason

        return EndpointExportOptions(
            fields=fields,
            where=where,
            order_by=order_by,
            expand=expand,
            incremental_summary=incremental_summary,
        )

    def _get_incremental_field(self, endpoint: str) -> str | None:
        normalized_endpoint = endpoint.strip().strip("/")
        if normalized_endpoint in self.incremental_field_map:
            return self.incremental_field_map[normalized_endpoint]
        return self.args.incremental_default_field

    def _max_endpoint_watermark(
        self,
        current_value: str | None,
        records: list[Any],
        incremental_summary: dict[str, Any] | None,
    ) -> str | None:
        if not incremental_summary or not incremental_summary.get("enabled"):
            return current_value
        field = incremental_summary.get("field")
        if not field:
            return current_value
        max_value = current_value
        for record in records:
            if not isinstance(record, dict):
                continue
            watermark_value = _normalize_watermark_value(record.get(field))
            max_value = _later_watermark(max_value, watermark_value)
        return max_value

    def _update_incremental_checkpoint(
        self,
        endpoint: str,
        incremental_summary: dict[str, Any],
        max_watermark_value: str | None,
    ) -> str | None:
        if not incremental_summary.get("enabled"):
            return None
        field = incremental_summary.get("field")
        if not field:
            return None
        previous_watermark = incremental_summary.get("previousWatermark")
        checkpoint_value = _later_watermark(previous_watermark, max_watermark_value)
        if checkpoint_value is None:
            checkpoint_value = _format_bqe_datetime(datetime.now(timezone.utc))
        completed_at = _utc_now()
        endpoints = self.incremental_state.setdefault("endpoints", {})
        endpoints[endpoint] = {
            "watermarkField": field,
            "watermarkValue": checkpoint_value,
            "updatedAt": completed_at,
        }
        self.incremental_state["updatedAt"] = completed_at
        self.incremental_state_store.save(self.incremental_state)
        return checkpoint_value

    def _download_documents(self, records: list[Any]) -> None:
        document_dir = self.output_dir / "document_files"
        for record in records:
            if not isinstance(record, dict):
                continue
            document_id = record.get("id")
            if document_id is None:
                continue
            try:
                uri = self.client.get_text(_join_url(self._api_base_url(), f"document/uri/{document_id}"))
                if not uri:
                    self.document_downloads.append(
                        {"id": document_id, "status": "skipped", "reason": "empty uri"}
                    )
                    continue
                target_name = _document_file_name(document_id, uri)
                target_path = document_dir / target_name
                self.client.download_file(uri, target_path)
                self.document_downloads.append(
                    {"id": document_id, "status": "downloaded", "file": str(target_path.relative_to(self.output_dir))}
                )
            except Exception as error:
                self.document_downloads.append(
                    {"id": document_id, "status": "failed", "error": str(error)}
                )

    def _load_tokens(self) -> OAuthTokens | None:
        if self.args.access_token:
            return OAuthTokens(
                access_token=self.args.access_token,
                endpoint=_normalize_base_url(self.args.api_base_url),
            )

        cached_tokens = self.token_store.load()
        if cached_tokens is not None and not cached_tokens.is_expired():
            return cached_tokens
        if cached_tokens is not None and cached_tokens.refresh_token and self.args.client_id and self.args.client_secret:
            self.tokens = cached_tokens
            refreshed = self._refresh_tokens_if_possible()
            if refreshed:
                return self.tokens
        return self._authorize_interactively()

    def _authorize_interactively(self) -> OAuthTokens:
        missing = [
            name
            for name, value in (
                ("client_id", self.args.client_id),
                ("client_secret", self.args.client_secret),
                ("redirect_uri", self.args.redirect_uri),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ExportError(
                "Authentication requires either --access-token or OAuth app settings. "
                f"Missing: {joined}."
            )

        state = secrets.token_urlsafe(24)
        authorize_url = _build_url(
            f"{IDENTITY_BASE_URL}/connect/authorize",
            {
                "client_id": self.args.client_id,
                "response_type": "code",
                "scope": self.args.scope,
                "redirect_uri": self.args.redirect_uri,
                "state": state,
            },
        )

        print("Open this URL to authorize the export:", file=sys.stderr)
        print(authorize_url, file=sys.stderr)
        if not self.args.no_browser:
            webbrowser.open(authorize_url)

        callback_value = input("Paste the full redirect URL here: ").strip()
        code, returned_state = _parse_callback_value(callback_value)
        if not code:
            raise ExportError("No authorization code found in the callback URL.")
        if returned_state and returned_state != state:
            raise ExportError("Returned OAuth state did not match the original authorization request.")

        response = self.client.post_form(
            f"{IDENTITY_BASE_URL}/connect/token",
            {
                "code": code,
                "redirect_uri": self.args.redirect_uri,
                "grant_type": "authorization_code",
                "client_id": self.args.client_id,
                "client_secret": self.args.client_secret,
            },
            include_auth=False,
        )
        tokens = OAuthTokens.from_dict(response.json())
        if not tokens.endpoint:
            tokens.endpoint = _normalize_base_url(self.args.api_base_url)
        self.token_store.save(tokens)
        return tokens

    def _refresh_tokens_if_possible(self) -> bool:
        if self.tokens is None:
            return False
        if not self.tokens.refresh_token:
            return False
        if not self.args.client_id or not self.args.client_secret:
            return False
        response = self.client.post_form(
            f"{IDENTITY_BASE_URL}/connect/token",
            {
                "refresh_token": self.tokens.refresh_token,
                "grant_type": "refresh_token",
                "client_id": self.args.client_id,
                "client_secret": self.args.client_secret,
            },
            include_auth=False,
        )
        refreshed_tokens = OAuthTokens.from_dict(response.json())
        if not refreshed_tokens.endpoint:
            refreshed_tokens.endpoint = self.tokens.endpoint or _normalize_base_url(self.args.api_base_url)
        self.tokens = refreshed_tokens
        self.token_store.save(refreshed_tokens)
        return True

    def _get_authorization_header(self) -> str | None:
        if self.tokens is None:
            return None
        if self.tokens.is_expired() and self.tokens.refresh_token:
            self._refresh_tokens_if_possible()
        return self.tokens.authorization_header()

    def _api_base_url(self) -> str:
        if self.tokens and self.tokens.endpoint:
            return _normalize_base_url(self.tokens.endpoint)
        return _normalize_base_url(self.args.api_base_url)

    def _write_summary(self, summary: dict[str, Any]) -> None:
        summary_path = self.output_dir / "export_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export BQE Core data to JSON files.",
    )
    parser.add_argument("--client-id", default=os.getenv("BQE_CORE_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.getenv("BQE_CORE_CLIENT_SECRET"))
    parser.add_argument("--redirect-uri", default=os.getenv("BQE_CORE_REDIRECT_URI"))
    parser.add_argument("--scope", default=os.getenv("BQE_CORE_SCOPE", DEFAULT_SCOPE))
    parser.add_argument("--access-token", default=os.getenv("BQE_CORE_ACCESS_TOKEN"))
    parser.add_argument("--api-base-url", default=os.getenv("BQE_CORE_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--token-cache", default=os.getenv("BQE_CORE_TOKEN_CACHE", str(DEFAULT_TOKEN_CACHE)))
    parser.add_argument("--endpoint", action="append", default=[])
    parser.add_argument("--endpoints-file")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--request-timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--fields")
    parser.add_argument("--where")
    parser.add_argument("--order-by")
    parser.add_argument("--expand")
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument(
        "--incremental-state-file",
        default=os.getenv("BQE_CORE_INCREMENTAL_STATE_FILE", str(DEFAULT_INCREMENTAL_STATE_FILE)),
    )
    parser.add_argument("--incremental-start")
    parser.add_argument(
        "--incremental-overlap-seconds",
        type=int,
        default=DEFAULT_INCREMENTAL_OVERLAP_SECONDS,
    )
    parser.add_argument(
        "--incremental-default-field",
        default=DEFAULT_INCREMENTAL_FIELD,
    )
    parser.add_argument("--incremental-field", action="append", default=[])
    parser.add_argument("--no-incremental-deletes", action="store_true")
    parser.add_argument("--download-document-files", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=str(Path("exports") / f"bqe-core-{datetime.now().strftime('%Y%m%d-%H%M%S')}"),
    )
    return parser


def _load_endpoints(args: argparse.Namespace) -> list[str]:
    endpoints: list[str] = []
    if args.endpoints_file:
        raw_text = Path(args.endpoints_file).read_text(encoding="utf-8")
        stripped = raw_text.strip()
        if stripped.startswith("["):
            loaded = json.loads(stripped)
            if not isinstance(loaded, list):
                raise ExportError("Endpoints file must contain a JSON array or one endpoint per line.")
            endpoints.extend(str(item).strip() for item in loaded if str(item).strip())
        else:
            endpoints.extend(line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#"))
    endpoints.extend(item.strip() for item in args.endpoint if item.strip())
    if not endpoints:
        endpoints.extend(DEFAULT_ENDPOINTS)
    unique_endpoints: list[str] = []
    seen: set[str] = set()
    for endpoint in endpoints:
        normalized = endpoint.strip().strip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_endpoints.append(normalized)
    return unique_endpoints


def _apply_incremental_endpoint_defaults(args: argparse.Namespace, endpoints: list[str]) -> list[str]:
    if not args.incremental or args.no_incremental_deletes:
        setattr(args, "auto_added_endpoints", [])
        return endpoints
    auto_added_endpoints: list[str] = []
    if DELETED_HISTORY_ENDPOINT not in endpoints:
        endpoints = [*endpoints, DELETED_HISTORY_ENDPOINT]
        auto_added_endpoints.append(DELETED_HISTORY_ENDPOINT)
    setattr(args, "auto_added_endpoints", auto_added_endpoints)
    return endpoints


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _build_incremental_field_map(args: argparse.Namespace) -> dict[str, str | None]:
    field_map = dict(DEFAULT_INCREMENTAL_FIELDS)
    for item in args.incremental_field:
        endpoint, field = _parse_incremental_field_override(item)
        field_map[endpoint] = field
    return field_map


def _parse_incremental_field_override(value: str) -> tuple[str, str | None]:
    for separator in ("=", ":"):
        if separator in value:
            endpoint, field = value.split(separator, 1)
            normalized_endpoint = endpoint.strip().strip("/")
            normalized_field = field.strip()
            if not normalized_endpoint:
                break
            if normalized_field.lower() in {"", "none", "off", "disabled"}:
                return normalized_endpoint, None
            return normalized_endpoint, normalized_field
    raise ExportError(
        "--incremental-field values must use endpoint=field syntax, for example invoice=lastUpdated."
    )


def _join_url(base_url: str, path: str) -> str:
    return f"{_normalize_base_url(base_url)}/{path.lstrip('/')}"


def _build_url(base_url: str, query: dict[str, str] | None = None) -> str:
    if not query:
        return base_url
    return f"{base_url}?{urllib.parse.urlencode(query)}"


def _extract_records(payload: Any) -> tuple[list[Any], bool]:
    if payload is None:
        return [], True
    if isinstance(payload, list):
        return payload, True
    if isinstance(payload, dict):
        for key in ("items", "value", "values", "data", "results", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return value, True
        return [payload], False
    return [payload], False


def _parse_callback_value(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    if "://" not in value and "?" not in value and "&" not in value:
        return value, None
    parsed = urllib.parse.urlparse(value)
    query = urllib.parse.parse_qs(parsed.query)
    code = _first(query.get("code"))
    state = _first(query.get("state"))
    return code, state


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]


def _format_http_error(method: str, url: str, response: HttpResponse) -> str:
    body_text = response.body.decode("utf-8", errors="replace").strip()
    message = f"HTTP {response.status_code} for {method} {url}"
    if body_text:
        message = f"{message}: {body_text}"
    return message


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _endpoint_to_file_name(endpoint: str) -> str:
    sanitized = endpoint.strip().strip("/").replace("/", "_")
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in sanitized)


def _document_file_name(document_id: Any, uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    suffix = Path(parsed.path).suffix
    if not suffix:
        suffix = ".bin"
    return f"{document_id}{suffix}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_bqe_datetime(value: datetime) -> str:
    utc_value = value.astimezone(timezone.utc).replace(microsecond=0, tzinfo=None)
    return utc_value.isoformat(timespec="seconds")


def _parse_iso_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_watermark_value(value: Any) -> str | None:
    if value is None:
        return None
    parsed = _parse_iso_datetime(str(value))
    if parsed is None:
        return None
    return _format_bqe_datetime(parsed)


def _shift_watermark(value: str, overlap_seconds: int) -> str | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    shifted = parsed - timedelta(seconds=max(0, overlap_seconds))
    return _format_bqe_datetime(shifted)


def _later_watermark(first_value: str | None, second_value: str | None) -> str | None:
    first_parsed = _parse_iso_datetime(first_value) if first_value else None
    second_parsed = _parse_iso_datetime(second_value) if second_value else None
    if first_parsed and second_parsed:
        return _format_bqe_datetime(max(first_parsed, second_parsed))
    if second_parsed:
        return _format_bqe_datetime(second_parsed)
    if first_parsed:
        return _format_bqe_datetime(first_parsed)
    return first_value or second_value


def _combine_where_clause(existing_clause: str | None, extra_clause: str) -> str:
    if existing_clause:
        return f"{existing_clause} AND {extra_clause}"
    return extra_clause


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.expand and args.page_size > 100:
        args.page_size = 100

    if args.page_size < 1:
        raise ExportError("--page-size must be greater than zero.")

    if args.incremental_overlap_seconds < 0:
        raise ExportError("--incremental-overlap-seconds must be zero or greater.")

    endpoints = _load_endpoints(args)
    endpoints = _apply_incremental_endpoint_defaults(args, endpoints)
    if not endpoints:
        raise ExportError("No endpoints were selected for export.")

    exporter = BQECoreExporter(args)
    summary = exporter.export_all(endpoints)

    print(f"Export complete: {summary['outputDir']}")
    print(f"Successful endpoints: {summary['successCount']}")
    print(f"Failed endpoints: {summary['failureCount']}")
    return 0 if summary["failureCount"] == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExportError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
