#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


ZERO_GUID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class FieldSpec:
    source_name: str
    output_name: str
    kind: str = "text"


@dataclass(frozen=True)
class TableSpec:
    name: str
    source_file: str
    fields: tuple[FieldSpec, ...]


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        name="stg_client",
        source_file="client.json",
        fields=(
            FieldSpec("id", "ClientId", "guid"),
            FieldSpec("name", "Client Name"),
            FieldSpec("company", "Company"),
            FieldSpec("status", "Client Status", "whole"),
            FieldSpec("type", "Client Type", "whole"),
            FieldSpec("clientSince", "Client Since", "date"),
            FieldSpec("manager", "Manager"),
            FieldSpec("managerId", "ManagerId", "guid"),
            FieldSpec("feeScheduleName", "Fee Schedule Name"),
            FieldSpec("feeScheduleId", "Fee Schedule Id", "guid"),
            FieldSpec("term", "Term"),
            FieldSpec("termId", "TermId", "guid"),
            FieldSpec("currencyId", "CurrencyId", "guid"),
            FieldSpec("mainServiceTax", "Main Service Tax", "decimal"),
            FieldSpec("mainExpenseTax", "Main Expense Tax", "decimal"),
        ),
    ),
    TableSpec(
        name="stg_project",
        source_file="project.json",
        fields=(
            FieldSpec("id", "ProjectId", "guid"),
            FieldSpec("clientId", "ClientId", "guid"),
            FieldSpec("code", "Project Code"),
            FieldSpec("name", "Project Name"),
            FieldSpec("displayName", "Project Display Name"),
            FieldSpec("status", "Project Status", "whole"),
            FieldSpec("type", "Project Type", "whole"),
            FieldSpec("manager", "Manager"),
            FieldSpec("managerId", "ManagerId", "guid"),
            FieldSpec("parentId", "Parent Project Id", "guid"),
            FieldSpec("rootProjectId", "Root Project Id", "guid"),
            FieldSpec("phaseName", "Phase Name"),
            FieldSpec("phaseDescription", "Phase Description"),
            FieldSpec("phaseOrder", "Phase Order", "whole"),
            FieldSpec("level", "Level", "whole"),
            FieldSpec("hasChild", "Has Child", "bool"),
            FieldSpec("startDate", "Start Date", "date"),
            FieldSpec("dueDate", "Due Date", "date"),
            FieldSpec("completedOn", "Completed On", "date"),
            FieldSpec("percentComplete", "Percent Complete", "decimal"),
            FieldSpec("contractAmount", "Contract Amount", "decimal"),
            FieldSpec("fixedFee", "Fixed Fee", "decimal"),
            FieldSpec("fixedFeePercentage", "Fixed Fee Percentage", "decimal"),
            FieldSpec("recurringAmount", "Recurring Amount", "decimal"),
            FieldSpec("recurringFrequency", "Recurring Frequency"),
            FieldSpec("purchaseOrderNumber", "Purchase Order Number"),
            FieldSpec("invoiceNumber", "Invoice Number"),
            FieldSpec("term", "Term"),
            FieldSpec("feeScheduleName", "Fee Schedule Name"),
            FieldSpec("principal", "Principal"),
            FieldSpec("originator", "Originator"),
        ),
    ),
    TableSpec(
        name="stg_employee",
        source_file="employee.json",
        fields=(
            FieldSpec("id", "EmployeeId", "guid"),
            FieldSpec("displayName", "Display Name"),
            FieldSpec("firstName", "First Name"),
            FieldSpec("lastName", "Last Name"),
            FieldSpec("title", "Title"),
            FieldSpec("department", "Department"),
            FieldSpec("role", "Role"),
            FieldSpec("status", "Status", "whole"),
            FieldSpec("manager", "Manager"),
            FieldSpec("managerId", "ManagerId", "guid"),
            FieldSpec("dateHired", "Date Hired", "date"),
            FieldSpec("dateReleased", "Date Released", "date"),
            FieldSpec("billRate", "Bill Rate", "decimal"),
            FieldSpec("costRate", "Cost Rate", "decimal"),
            FieldSpec("overtimeBillRate", "Overtime Bill Rate", "decimal"),
            FieldSpec("overtimeCostRate", "Overtime Cost Rate", "decimal"),
            FieldSpec("utilizationTarget", "Utilization Target", "decimal"),
            FieldSpec("dailyStandardHours", "Daily Standard Hours", "decimal"),
            FieldSpec("weeklyStandardHours", "Weekly Standard Hours", "decimal"),
        ),
    ),
    TableSpec(
        name="stg_activity",
        source_file="activity.json",
        fields=(
            FieldSpec("id", "ActivityId", "guid"),
            FieldSpec("code", "Activity Code"),
            FieldSpec("name", "Activity Name"),
            FieldSpec("description", "Description"),
            FieldSpec("billable", "Billable", "bool"),
            FieldSpec("extra", "Extra", "bool"),
            FieldSpec("isActive", "Is Active", "bool"),
            FieldSpec("billRate", "Bill Rate", "decimal"),
            FieldSpec("costRate", "Cost Rate", "decimal"),
            FieldSpec("overTimeBillRate", "Overtime Bill Rate", "decimal"),
            FieldSpec("class", "Class"),
        ),
    ),
    TableSpec(
        name="stg_timeentry",
        source_file="timeentry.json",
        fields=(
            FieldSpec("id", "TimeEntryId", "guid"),
            FieldSpec("date", "Date", "date"),
            FieldSpec("projectId", "ProjectId", "guid"),
            FieldSpec("resourceId", "ResourceId", "guid"),
            FieldSpec("activityId", "ActivityId", "guid"),
            FieldSpec("invoiceId", "InvoiceId", "guid"),
            FieldSpec("invoiceNumber", "Invoice Number"),
            FieldSpec("client", "Client"),
            FieldSpec("project", "Project"),
            FieldSpec("resource", "Resource"),
            FieldSpec("description", "Description"),
            FieldSpec("actualHours", "Actual Hours", "decimal"),
            FieldSpec("clientHours", "Client Hours", "decimal"),
            FieldSpec("billRate", "Bill Rate", "decimal"),
            FieldSpec("costRate", "Cost Rate", "decimal"),
            FieldSpec("billable", "Billable", "bool"),
            FieldSpec("billStatus", "Bill Status", "whole"),
            FieldSpec("isWrittenOff", "Is Written Off", "bool"),
            FieldSpec("overtime", "Overtime", "bool"),
            FieldSpec("classification", "Classification"),
            FieldSpec("vendorBillId", "Vendor Bill Id", "guid"),
            FieldSpec("vendorBillNumber", "Vendor Bill Number"),
            FieldSpec("tax1", "Tax1", "decimal"),
            FieldSpec("tax2", "Tax2", "decimal"),
            FieldSpec("tax3", "Tax3", "decimal"),
        ),
    ),
    TableSpec(
        name="stg_invoice",
        source_file="invoice.json",
        fields=(
            FieldSpec("id", "InvoiceId", "guid"),
            FieldSpec("invoiceNumber", "Invoice Number"),
            FieldSpec("date", "Date", "date"),
            FieldSpec("accountingDate", "Accounting Date", "date"),
            FieldSpec("dueDate", "Due Date", "date"),
            FieldSpec("voidDate", "Void Date", "date"),
            FieldSpec("invoiceTo", "Invoice To"),
            FieldSpec("invoiceFrom", "Invoice From"),
            FieldSpec("referenceNumber", "Reference Number"),
            FieldSpec("rfNumber", "RF Number"),
            FieldSpec("status", "Status", "whole"),
            FieldSpec("type", "Type", "whole"),
            FieldSpec("invoiceAmount", "Invoice Amount", "decimal"),
            FieldSpec("balance", "Balance", "decimal"),
            FieldSpec("serviceAmount", "Service Amount", "decimal"),
            FieldSpec("expenseAmount", "Expense Amount", "decimal"),
            FieldSpec("miscellaneousAmount", "Miscellaneous Amount", "decimal"),
            FieldSpec("fixedFee", "Fixed Fee", "decimal"),
            FieldSpec("serviceTaxAmount", "Service Tax Amount", "decimal"),
            FieldSpec("expenseTaxAmount", "Expense Tax Amount", "decimal"),
            FieldSpec("mainServiceTax", "Main Service Tax", "decimal"),
            FieldSpec("mainExpenseTax", "Main Expense Tax", "decimal"),
            FieldSpec("isDraft", "Is Draft", "bool"),
            FieldSpec("isVoid", "Is Void", "bool"),
            FieldSpec("isJointInvoice", "Is Joint Invoice", "bool"),
            FieldSpec("isManualInvoice", "Is Manual Invoice", "bool"),
            FieldSpec("isLateFeeInvoice", "Is Late Fee Invoice", "bool"),
        ),
    ),
    TableSpec(
        name="stg_payment",
        source_file="payment.json",
        fields=(
            FieldSpec("id", "PaymentId", "guid"),
            FieldSpec("date", "Date", "date"),
            FieldSpec("accountingDate", "Accounting Date", "date"),
            FieldSpec("clientId", "ClientId", "guid"),
            FieldSpec("projectId", "ProjectId", "guid"),
            FieldSpec("client", "Client"),
            FieldSpec("project", "Project"),
            FieldSpec("amount", "Amount", "decimal"),
            FieldSpec("method", "Method"),
            FieldSpec("reference", "Reference"),
            FieldSpec("isRetainer", "Is Retainer", "bool"),
            FieldSpec("retainerType", "Retainer Type"),
            FieldSpec("assetAccount", "Asset Account"),
            FieldSpec("liabilityAccount", "Liability Account"),
        ),
    ),
    TableSpec(
        name="stg_bill",
        source_file="bill.json",
        fields=(
            FieldSpec("id", "BillId", "guid"),
            FieldSpec("number", "Number"),
            FieldSpec("referenceNumber", "Reference Number"),
            FieldSpec("date", "Date", "date"),
            FieldSpec("accountingDate", "Accounting Date", "date"),
            FieldSpec("dueDate", "Due Date", "date"),
            FieldSpec("vendorId", "VendorId", "guid"),
            FieldSpec("vendor", "Vendor"),
            FieldSpec("amount", "Amount", "decimal"),
            FieldSpec("balance", "Balance", "decimal"),
            FieldSpec("paymentStatus", "Payment Status", "whole"),
            FieldSpec("reimbursable", "Reimbursable", "bool"),
            FieldSpec("term", "Term"),
        ),
    ),
    TableSpec(
        name="stg_check",
        source_file="check.json",
        fields=(
            FieldSpec("id", "CheckId", "guid"),
            FieldSpec("number", "Number"),
            FieldSpec("date", "Date", "date"),
            FieldSpec("accountingDate", "Accounting Date", "date"),
            FieldSpec("payeeId", "PayeeId", "guid"),
            FieldSpec("payee", "Payee"),
            FieldSpec("payeeName", "Payee Name"),
            FieldSpec("payeeType", "Payee Type", "whole"),
            FieldSpec("amount", "Amount", "decimal"),
            FieldSpec("isBillPayment", "Is Bill Payment", "bool"),
            FieldSpec("isEFT", "Is EFT", "bool"),
            FieldSpec("isVoid", "Is Void", "bool"),
            FieldSpec("printStatus", "Print Status", "whole"),
        ),
    ),
    TableSpec(
        name="stg_document",
        source_file="document.json",
        fields=(
            FieldSpec("id", "DocumentId", "guid"),
            FieldSpec("date", "Date", "date"),
            FieldSpec("name", "Name"),
            FieldSpec("description", "Description"),
            FieldSpec("entity", "Entity"),
            FieldSpec("entityId", "EntityId", "guid"),
            FieldSpec("entityType", "Entity Type", "whole"),
            FieldSpec("size", "Size", "whole"),
            FieldSpec("uri", "Uri"),
            FieldSpec("createdOn", "Created On", "datetime"),
            FieldSpec("lastUpdated", "Last Updated", "datetime"),
        ),
    ),
    TableSpec(
        name="stg_crm_prospect",
        source_file="crm_prospect.json",
        fields=(
            FieldSpec("id", "ProspectId", "guid"),
            FieldSpec("assignedDate", "Assigned Date", "date"),
            FieldSpec("clientId", "ClientId", "guid"),
            FieldSpec("company", "Company"),
            FieldSpec("name", "Name"),
            FieldSpec("title", "Title"),
            FieldSpec("status", "Status", "whole"),
            FieldSpec("type", "Type", "whole"),
            FieldSpec("assignedTo", "Assigned To"),
            FieldSpec("assignedToId", "Assigned To Id", "guid"),
            FieldSpec("manager", "Manager"),
            FieldSpec("managerId", "ManagerId", "guid"),
            FieldSpec("sourceId", "SourceId", "guid"),
            FieldSpec("regionId", "RegionId", "guid"),
            FieldSpec("scoreId", "ScoreId", "guid"),
            FieldSpec("cost", "Cost", "decimal"),
        ),
    ),
    TableSpec(
        name="stg_crm_leadsource",
        source_file="crm_lists_leadsource.json",
        fields=(
            FieldSpec("id", "SourceId", "guid"),
            FieldSpec("name", "Source Name"),
            FieldSpec("status", "Status", "whole"),
        ),
    ),
    TableSpec(
        name="stg_crm_region",
        source_file="crm_lists_region.json",
        fields=(
            FieldSpec("id", "RegionId", "guid"),
            FieldSpec("name", "Region Name"),
            FieldSpec("status", "Status", "whole"),
        ),
    ),
    TableSpec(
        name="stg_crm_score",
        source_file="crm_lists_score.json",
        fields=(
            FieldSpec("id", "ScoreId", "guid"),
            FieldSpec("name", "Score Name"),
            FieldSpec("status", "Status", "whole"),
        ),
    ),
)


TABLE_SPEC_BY_NAME = {table.name: table for table in TABLE_SPECS}


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    exports_root = repo_root / "exports"

    parser = argparse.ArgumentParser(
        description=(
            "Create curated staging CSV files from a BQE Core raw export for Power BI. "
            "The default output is one stable folder with one subfolder per table."
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Path to a raw export folder like exports/bqe-core-20260311-132503. Defaults to the latest export.",
    )
    parser.add_argument(
        "--exports-root",
        type=Path,
        default=exports_root,
        help=f"Base exports folder used to discover the latest export. Defaults to {exports_root}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=exports_root / "current",
        help=f"Stable curated output folder. Defaults to {exports_root / 'current'}.",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=sorted(TABLE_SPEC_BY_NAME),
        help="Optional subset of curated tables to build.",
    )
    parser.add_argument(
        "--rows-per-part",
        type=int,
        default=0,
        help="Optional row limit per CSV part. Use this to split very large tables. Default keeps one file per table.",
    )
    parser.add_argument(
        "--max-rows-per-table",
        type=int,
        default=0,
        help="Optional safety limit for sampling or dry runs. Default processes all rows.",
    )
    parser.add_argument(
        "--zip-output",
        action="store_true",
        help="Create a zip archive of the curated output folder after generation.",
    )
    return parser.parse_args()


def discover_latest_export(exports_root: Path) -> Path:
    candidates = sorted(
        [path for path in exports_root.glob("bqe-core-*") if path.is_dir()],
        key=lambda path: path.name,
    )
    if not candidates:
        raise FileNotFoundError(f"No raw export folders found under {exports_root}")
    return candidates[-1]


def load_export_summary(source_dir: Path) -> dict[str, Any] | None:
    summary_path = source_dir / "export_summary.json"
    if not summary_path.exists():
        return None
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_expected_record_lookup(export_summary: dict[str, Any] | None) -> dict[str, int]:
    if not export_summary:
        return {}

    expected: dict[str, int] = {}
    for endpoint in export_summary.get("endpoints", []):
        file_name = endpoint.get("file")
        if file_name:
            expected[file_name] = int(endpoint.get("records", 0) or 0)
    return expected


def iter_json_array(path: Path, chunk_size: int = 1024 * 1024) -> Iterable[dict[str, Any]]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as handle:
        buffer = ""
        position = 0
        end_of_file = False

        while True:
            if position >= len(buffer) and end_of_file:
                return

            while True:
                if position < len(buffer):
                    current = buffer[position]
                    if current.isspace() or current == ",":
                        position += 1
                        continue
                    if current == "[":
                        position += 1
                        continue
                    if current == "]":
                        return
                    break

                if end_of_file:
                    return

                chunk = handle.read(chunk_size)
                if not chunk:
                    end_of_file = True
                    continue

                if position > 0:
                    buffer = buffer[position:]
                    position = 0
                buffer += chunk

            try:
                payload, next_position = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError:
                if end_of_file:
                    raise

                chunk = handle.read(chunk_size)
                if not chunk:
                    end_of_file = True
                    continue

                if position > 0:
                    buffer = buffer[position:]
                    position = 0
                buffer += chunk
                continue

            position = next_position
            if not isinstance(payload, dict):
                raise ValueError(f"Expected objects inside {path}, found {type(payload).__name__}")
            yield payload


def normalize_guid(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if not text or text == ZERO_GUID:
        return ""
    return text


def normalize_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        if "T" in text:
            return text.split("T", 1)[0]
        return text


def normalize_datetime(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()

    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return text


def normalize_bool(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n"}:
        return "false"
    return text


def normalize_whole(value: Any) -> int | str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return 1 if value else 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value).strip()


def normalize_decimal(value: Any) -> float | int | str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return int(number)
    return number


def normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).strip()


def normalize_value(field: FieldSpec, value: Any) -> Any:
    if field.kind == "guid":
        return normalize_guid(value)
    if field.kind == "date":
        return normalize_date(value)
    if field.kind == "datetime":
        return normalize_datetime(value)
    if field.kind == "bool":
        return normalize_bool(value)
    if field.kind == "whole":
        return normalize_whole(value)
    if field.kind == "decimal":
        return normalize_decimal(value)
    return normalize_text(value)


class CsvPartitionWriter:
    def __init__(self, output_dir: Path, field_names: list[str], rows_per_part: int = 0) -> None:
        self.output_dir = output_dir
        self.field_names = field_names
        self.rows_per_part = rows_per_part
        self.part_number = 0
        self.rows_in_part = 0
        self.total_rows = 0
        self.files: list[Path] = []
        self._handle: Any | None = None
        self._writer: csv.DictWriter | None = None

    def _next_file_name(self) -> str:
        if self.rows_per_part > 0:
            return f"part-{self.part_number:05d}.csv"
        return "current.csv"

    def _open_new_part(self) -> None:
        self.close()
        self.part_number += 1
        self.rows_in_part = 0

        self.output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.output_dir / self._next_file_name()
        self._handle = file_path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=self.field_names)
        self._writer.writeheader()
        self.files.append(file_path)

    def ensure_started(self) -> None:
        if self._writer is None:
            self._open_new_part()

    def write_row(self, row: dict[str, Any]) -> None:
        if self._writer is None:
            self._open_new_part()
        elif self.rows_per_part > 0 and self.rows_in_part >= self.rows_per_part:
            self._open_new_part()

        assert self._writer is not None
        self._writer.writerow(row)
        self.rows_in_part += 1
        self.total_rows += 1

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
            self._writer = None


def transform_row(record: dict[str, Any], table_spec: TableSpec) -> dict[str, Any]:
    return {
        field.output_name: normalize_value(field, record.get(field.source_name))
        for field in table_spec.fields
    }


def process_table(
    table_spec: TableSpec,
    source_dir: Path,
    output_root: Path,
    expected_records: dict[str, int],
    rows_per_part: int,
    max_rows_per_table: int,
) -> dict[str, Any]:
    source_path = source_dir / table_spec.source_file
    writer = CsvPartitionWriter(
        output_dir=output_root / table_spec.name,
        field_names=[field.output_name for field in table_spec.fields],
        rows_per_part=rows_per_part,
    )

    warnings: list[str] = []
    truncated = False

    if not source_path.exists():
        warnings.append(f"Missing source file: {table_spec.source_file}")
        writer.ensure_started()
        writer.close()
        return {
            "table": table_spec.name,
            "sourceFile": table_spec.source_file,
            "expectedRecords": expected_records.get(table_spec.source_file),
            "rowsWritten": 0,
            "files": [str(path.relative_to(output_root)) for path in writer.files],
            "warnings": warnings,
            "truncated": False,
        }

    try:
        for record_index, record in enumerate(iter_json_array(source_path), start=1):
            if max_rows_per_table > 0 and record_index > max_rows_per_table:
                truncated = True
                break
            writer.write_row(transform_row(record, table_spec))
    finally:
        writer.ensure_started()
        writer.close()

    return {
        "table": table_spec.name,
        "sourceFile": table_spec.source_file,
        "expectedRecords": expected_records.get(table_spec.source_file),
        "rowsWritten": writer.total_rows,
        "files": [str(path.relative_to(output_root)) for path in writer.files],
        "warnings": warnings,
        "truncated": truncated,
    }


def replace_directory(target_dir: Path, prepared_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    prepared_dir.rename(target_dir)


def write_manifest(
    output_root: Path,
    source_dir: Path,
    export_summary: dict[str, Any] | None,
    table_results: list[dict[str, Any]],
    rows_per_part: int,
    max_rows_per_table: int,
) -> None:
    manifest = {
        "generatedAt": datetime.now().astimezone().isoformat(),
        "sourceDir": str(source_dir),
        "sourceExportSummary": str(source_dir / "export_summary.json"),
        "rowsPerPart": rows_per_part,
        "maxRowsPerTable": max_rows_per_table,
        "failedEndpoints": [
            endpoint.get("endpoint")
            for endpoint in (export_summary or {}).get("endpoints", [])
            if endpoint.get("status") != "completed"
        ],
        "tables": table_results,
    }

    manifest_path = output_root / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")


def create_zip_archive(output_root: Path) -> Path:
    archive_base = output_root.parent / output_root.name
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=output_root))
    return archive_path


def main() -> int:
    args = parse_args()
    exports_root = args.exports_root.resolve()
    source_dir = args.source_dir.resolve() if args.source_dir else discover_latest_export(exports_root).resolve()
    output_dir = args.output_dir.resolve()

    if args.rows_per_part < 0:
        raise ValueError("--rows-per-part must be zero or greater")
    if args.max_rows_per_table < 0:
        raise ValueError("--max-rows-per-table must be zero or greater")

    selected_tables = (
        [TABLE_SPEC_BY_NAME[name] for name in args.tables]
        if args.tables
        else list(TABLE_SPECS)
    )

    export_summary = load_export_summary(source_dir)
    expected_records = build_expected_record_lookup(export_summary)

    prepared_dir = output_dir.parent / f"{output_dir.name}.tmp"
    if prepared_dir.exists():
        shutil.rmtree(prepared_dir)
    prepared_dir.mkdir(parents=True, exist_ok=True)

    table_results: list[dict[str, Any]] = []

    print(f"Source export: {source_dir}")
    print(f"Curated output: {output_dir}")

    for table_spec in selected_tables:
        print(f"Building {table_spec.name} from {table_spec.source_file}...")
        result = process_table(
            table_spec=table_spec,
            source_dir=source_dir,
            output_root=prepared_dir,
            expected_records=expected_records,
            rows_per_part=args.rows_per_part,
            max_rows_per_table=args.max_rows_per_table,
        )
        table_results.append(result)
        status_parts = [f"rows={result['rowsWritten']}"]
        if result.get("expectedRecords") is not None:
            status_parts.append(f"expected={result['expectedRecords']}")
        if result.get("truncated"):
            status_parts.append("truncated=true")
        if result.get("warnings"):
            status_parts.append(f"warnings={len(result['warnings'])}")
        print(f"  -> {'; '.join(status_parts)}")

    write_manifest(
        output_root=prepared_dir,
        source_dir=source_dir,
        export_summary=export_summary,
        table_results=table_results,
        rows_per_part=args.rows_per_part,
        max_rows_per_table=args.max_rows_per_table,
    )

    replace_directory(output_dir, prepared_dir)

    if args.zip_output:
        archive_path = create_zip_archive(output_dir)
        print(f"Zip archive: {archive_path}")

    total_rows = sum(int(result["rowsWritten"]) for result in table_results)
    print(f"Finished. Tables built: {len(table_results)}; total rows written: {total_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
