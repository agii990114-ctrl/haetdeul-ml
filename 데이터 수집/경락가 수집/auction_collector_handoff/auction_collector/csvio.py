from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator, Mapping

from .constants import CSV_HEADERS, NATURAL_KEY_COLUMNS, NUMERIC_COLUMNS


class CsvValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidationResult:
    path: str
    encoding: str
    bom: bool
    row_count: int
    column_count: int
    min_date: str | None
    max_date: str | None
    duplicate_natural_keys: int
    grade_code_nulls: int
    sha256: str
    bytes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_utf8_bom(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(3) == b"\xef\xbb\xbf"


def _atomic_target(path: Path) -> tuple[Path, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    return Path(handle.name), handle


def write_csv_atomic(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    temp_path, handle = _atomic_target(path)
    try:
        with handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS, extrasaction="raise", lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({header: row.get(header, "") for header in CSV_HEADERS})
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def create_excel_copy(db_path: Path, excel_path: Path) -> None:
    excel_path.parent.mkdir(parents=True, exist_ok=True)
    temp = excel_path.parent / f".{excel_path.name}.{os.getpid()}.tmp"
    try:
        with db_path.open("rb") as source, temp.open("wb") as target:
            prefix = source.read(3)
            target.write(b"\xef\xbb\xbf")
            if prefix != b"\xef\xbb\xbf":
                target.write(prefix)
            shutil.copyfileobj(source, target, length=1024 * 1024)
        os.replace(temp, excel_path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def same_content_ignoring_bom(first: Path, second: Path) -> bool:
    def digest_without_bom(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            prefix = file.read(3)
            if prefix != b"\xef\xbb\xbf":
                digest.update(prefix)
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    return digest_without_bom(first) == digest_without_bom(second)


def iter_csv(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != CSV_HEADERS:
            raise CsvValidationError(f"헤더 불일치: {reader.fieldnames}")
        for row in reader:
            yield {header: row.get(header, "") for header in CSV_HEADERS}


def validate_csv(path: Path, *, require_bom: bool | None = None) -> ValidationResult:
    if not path.exists():
        raise CsvValidationError(f"CSV 파일이 없습니다: {path}")
    bom = has_utf8_bom(path)
    if require_bom is True and not bom:
        raise CsvValidationError("UTF-8 BOM이 없습니다.")
    if require_bom is False and bom:
        raise CsvValidationError("DB 적재용 CSV에 BOM이 있습니다.")

    row_count = 0
    min_date: str | None = None
    max_date: str | None = None
    previous_date: str | None = None
    duplicates = 0
    grade_code_nulls = 0
    keys: set[tuple[str, ...]] = set()
    problems: list[str] = []
    required_text = (
        "auction_date",
        "market_category",
        "wholesale_market_code",
        "wholesale_market_name",
        "item_code",
        "item_name",
        "grade_name",
        "source",
    )

    try:
        rows = iter_csv(path)
        for line_number, row in enumerate(rows, start=2):
            row_count += 1
            raw_date = row["auction_date"]
            try:
                parsed = date.fromisoformat(raw_date)
            except ValueError:
                problems.append(f"{line_number}행 날짜 오류: {raw_date}")
                parsed = None
            if parsed is not None:
                if min_date is None or raw_date < min_date:
                    min_date = raw_date
                if max_date is None or raw_date > max_date:
                    max_date = raw_date
                if previous_date is not None and raw_date < previous_date:
                    problems.append(f"{line_number}행 날짜 정렬 오류: {previous_date} 뒤에 {raw_date}")
                previous_date = raw_date

            for column in NUMERIC_COLUMNS:
                value = row[column]
                try:
                    number = Decimal(value)
                except InvalidOperation:
                    problems.append(f"{line_number}행 {column} 숫자 오류: {value}")
                    continue
                if not number.is_finite() or number <= 0:
                    problems.append(f"{line_number}행 {column}은 양수여야 합니다: {value}")
                if column == "source_trade_count" and number != number.to_integral_value():
                    problems.append(f"{line_number}행 source_trade_count는 정수여야 합니다: {value}")

            for column in required_text:
                if not row[column].strip():
                    problems.append(f"{line_number}행 {column}이 비어 있습니다.")
            if row["market_category"] not in {"가락", "지방"}:
                problems.append(f"{line_number}행 market_category 오류: {row['market_category']}")

            if not row["grade_code"]:
                grade_code_nulls += 1
            key = tuple(row[column] for column in NATURAL_KEY_COLUMNS)
            if key in keys:
                duplicates += 1
                if duplicates <= 5:
                    problems.append(f"{line_number}행 자연키 중복: {key}")
            else:
                keys.add(key)
            if len(problems) >= 20:
                break
    except UnicodeDecodeError as error:
        raise CsvValidationError(f"UTF-8 디코딩 실패: {error}") from error

    if problems:
        raise CsvValidationError("CSV 검증 실패:\n- " + "\n- ".join(problems))
    return ValidationResult(
        path=str(path),
        encoding="UTF-8",
        bom=bom,
        row_count=row_count,
        column_count=len(CSV_HEADERS),
        min_date=min_date,
        max_date=max_date,
        duplicate_natural_keys=duplicates,
        grade_code_nulls=grade_code_nulls,
        sha256=_sha256(path),
        bytes=path.stat().st_size,
    )


def merge_csv(
    base_path: Path,
    output_path: Path,
    new_rows: list[dict[str, str]],
    *,
    replace_start: str | None = None,
    replace_end: str | None = None,
) -> None:
    new_rows = sorted(
        new_rows,
        key=lambda row: (
            row["auction_date"],
            row["wholesale_market_code"],
            row["item_code"],
            row["grade_code"],
            row["grade_name"],
        ),
    )
    temp_path, handle = _atomic_target(output_path)
    inserted = False
    try:
        with handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS, lineterminator="\n")
            writer.writeheader()
            if not base_path.exists():
                writer.writerows(new_rows)
                inserted = True
            else:
                base_result = validate_csv(base_path)
                if replace_start is None:
                    if new_rows and base_result.max_date is not None and new_rows[0]["auction_date"] <= base_result.max_date:
                        raise CsvValidationError(
                            "새 데이터가 기존 최대 날짜와 겹칩니다. --replace-range를 사용하세요."
                        )
                    for row in iter_csv(base_path):
                        writer.writerow(row)
                    writer.writerows(new_rows)
                    inserted = True
                else:
                    if replace_end is None:
                        raise ValueError("replace_start와 replace_end는 함께 필요합니다.")
                    for row in iter_csv(base_path):
                        row_date = row["auction_date"]
                        if replace_start <= row_date <= replace_end:
                            continue
                        if not inserted and row_date > replace_end:
                            writer.writerows(new_rows)
                            inserted = True
                        writer.writerow(row)
            if not inserted:
                writer.writerows(new_rows)
        os.replace(temp_path, output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_manifest(
    path: Path,
    db_result: ValidationResult,
    excel_result: ValidationResult,
    *,
    generated_from: str,
) -> None:
    payload = {
        "dataset": "건고추·양파·배추·무·마늘 일별 시장·등급별 경매 낙찰가",
        "generatedFrom": generated_from,
        "sourcePolicy": {
            "2015": "농림축산식품 공공데이터포털 원천정산경락가격품목목록조회",
            "2016_onward": "공공데이터포털 전국 공영도매시장 경매원천정보",
            "incremental_collection": "data.go.kr only",
        },
        "columns": list(CSV_HEADERS),
        "naturalKey": list(NATURAL_KEY_COLUMNS),
        "nullRepresentation": "empty unquoted field",
        "dbCsv": db_result.to_dict(),
        "excelCsv": excel_result.to_dict(),
        "sameContentIgnoringBom": same_content_ignoring_bom(Path(db_result.path), Path(excel_result.path)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def create_bundle(path: Path, files: Iterable[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for file in files:
                archive.write(file, arcname=file.name)
        with zipfile.ZipFile(temp) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise CsvValidationError(f"ZIP CRC 오류: {bad}")
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
