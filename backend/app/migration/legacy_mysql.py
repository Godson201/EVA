"""Non-destructive MySQL to PostgreSQL migration helpers.

The command reads legacy data and writes idempotent V2 rows keyed by stable
UUIDs and `legacy_id`. It never updates or deletes a MySQL row.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from pathlib import Path

import mysql.connector
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.db.session import close_database, initialize_database
from app.models import Attachment, Transcription, User

MIGRATION_NAMESPACE = uuid.UUID("727a8eed-0952-4aa4-b5a7-f148d49bfe3c")
ROLE_MAP = {"director": "ADMIN", "admin": "ADMIN", "manager": "ADMIN"}


def stable_uuid(table: str, legacy_id: int) -> uuid.UUID:
    return uuid.uuid5(MIGRATION_NAMESPACE, f"{table}:{legacy_id}")


@dataclass
class MigrationReport:
    dry_run: bool
    source_counts: dict[str, int]
    written_counts: dict[str, int]
    skipped_counts: dict[str, int]
    warnings: list[str]


class LegacyReader:
    def __init__(self, settings: Settings):
        self.connection = mysql.connector.connect(
            host=settings.legacy_mysql_host,
            port=settings.legacy_mysql_port,
            user=settings.legacy_mysql_user,
            password=settings.legacy_mysql_password,
            database=settings.legacy_mysql_database,
        )

    def table_exists(self, table: str) -> bool:
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s", (table,))
        exists = cursor.fetchone()[0] == 1
        cursor.close()
        return exists

    def rows(self, table: str) -> list[dict[str, Any]]:
        if not self.table_exists(table):
            return []
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM `{table}`")
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def close(self) -> None:
        self.connection.close()


async def migrate(settings: Settings, dry_run: bool = True) -> MigrationReport:
    reader = LegacyReader(settings)
    report = MigrationReport(dry_run, {}, {}, {}, [])
    try:
        users = reader.rows("users")
        audio_records = reader.rows("audio_records")
        speech_records = reader.rows("speech_recordings")
        report.source_counts = {
            "users": len(users), "audio_records": len(audio_records), "speech_recordings": len(speech_records)
        }
        if dry_run:
            return report

        engine = initialize_database(settings)
        async with engine.begin() as connection:
            for row in users:
                values = {
                    "id": stable_uuid("users", row["id"]), "legacy_id": row["id"],
                    "username": row["username"], "email": row["email"],
                    "password_hash": row.get("password_hash"), "full_name": row.get("full_name"),
                    "role": ROLE_MAP.get(str(row.get("role", "user")).lower(), "USER"),
                    "provider": row.get("provider") or "email", "is_active": bool(row.get("is_active", True)),
                }
                statement = insert(User).values(**values).on_conflict_do_update(
                    index_elements=[User.legacy_id],
                    set_={key: value for key, value in values.items() if key not in {"id", "legacy_id"}},
                )
                await connection.execute(statement)
                report.written_counts["users"] = report.written_counts.get("users", 0) + 1

            for source_table, rows, source_name in (
                ("audio_records", audio_records, "upload"),
                ("speech_recordings", speech_records, "browser_recording"),
            ):
                for row in rows:
                    if not row.get("user_id"):
                        report.skipped_counts[source_table] = report.skipped_counts.get(source_table, 0) + 1
                        report.warnings.append(f"{source_table}:{row['id']} has no owner")
                        continue
                    attachment_id = None
                    file_path = row.get("file_path") or row.get("audio_path")
                    if file_path:
                        attachment_id = stable_uuid(f"{source_table}_attachment", row["id"])
                        attachment_values = {
                            "id": attachment_id, "legacy_source": source_table, "legacy_id": row["id"],
                            "user_id": stable_uuid("users", row["user_id"]),
                            "object_key": f"legacy/{source_table}/{row['id']}",
                            "original_filename": row.get("filename") or Path(file_path).name,
                            "content_type": "audio/unknown", "size_bytes": int(row.get("file_size") or 0),
                        }
                        await connection.execute(insert(Attachment).values(**attachment_values).on_conflict_do_nothing(
                            index_elements=[Attachment.legacy_source, Attachment.legacy_id]
                        ))
                    key_points = row.get("key_points") or []
                    if isinstance(key_points, str):
                        try:
                            key_points = json.loads(key_points)
                        except json.JSONDecodeError:
                            key_points = [key_points]
                    values = {
                        "id": stable_uuid(source_table, row["id"]), "legacy_source": source_table,
                        "legacy_id": row["id"],
                        "user_id": stable_uuid("users", row["user_id"]), "attachment_id": attachment_id,
                        "source": source_name, "language": row.get("language_detected") or row.get("language"),
                        "raw_text": row.get("original_text") or row.get("text"),
                        "corrected_text": row.get("original_text") or row.get("text"),
                        "summary": row.get("summary_text") or row.get("summary"), "key_points": key_points,
                        "duration_seconds": row.get("duration") if isinstance(row.get("duration"), (int, float)) else None,
                        "status": "completed",
                    }
                    await connection.execute(insert(Transcription).values(**values).on_conflict_do_update(
                        index_elements=[Transcription.legacy_source, Transcription.legacy_id],
                        set_={key: value for key, value in values.items() if key not in {"id", "legacy_source", "legacy_id"}},
                    ))
                    report.written_counts[source_table] = report.written_counts.get(source_table, 0) + 1
        return report
    finally:
        reader.close()
        await close_database()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy EVA MySQL data without modifying the source")
    parser.add_argument("--apply", action="store_true", help="write to PostgreSQL; default is a dry run")
    parser.add_argument("--report", help="optional JSON report path")
    args = parser.parse_args()
    report = asyncio.run(migrate(Settings(), dry_run=not args.apply))
    output = json.dumps(asdict(report), indent=2)
    print(output)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")


if __name__ == "__main__":
    main()
