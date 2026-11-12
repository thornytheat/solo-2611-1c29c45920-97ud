"""幂等模式演进：为已存在的旧库补齐校正运行所需的列与索引。

项目用 ``Base.metadata.create_all()`` 建表，它只建新表、不会给旧表加列。
本模块在启动时（create_all 之后）用 inspector 检查缺失列，按方言补 ALTER TABLE：
- MySQL 8.0：BOOLEAN -> TINYINT(1)，JSON -> JSON
- SQLite（本地/CI 测试）：BOOLEAN -> INTEGER，JSON -> TEXT

全部为加列 + 加索引，不删除/不改写既有数据；is_current 补列后做一次归一化，
保证每个漏斗至多一条「当前」运行，旧运行仍全部可查但不再充当当前结论。
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# table -> [(column, mysql_type, sqlite_type, server_default_sql_or_None)]
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str, str, str | None]]] = {
    "event_logs": [
        ("data_version_id", "INT NULL", "INTEGER", None),
    ],
    "funnel_runs": [
        ("data_version_id", "INT NULL", "INTEGER", None),
        ("baseline_run_id", "INT NULL", "INTEGER", None),
        ("config_snapshot", "JSON NOT NULL", "TEXT NOT NULL", "'{}'"),
        ("data_fingerprint", "VARCHAR(64) NOT NULL", "VARCHAR(64) NOT NULL", "''"),
        ("is_current", "TINYINT(1) NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1", None),
        ("correction_meta", "JSON NOT NULL", "TEXT NOT NULL", "'{}'"),
    ],
    "drop_reports": [
        ("is_current", "TINYINT(1) NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1", None),
        ("data_version_id", "INT NULL", "INTEGER", None),
    ],
}

# table -> [(index_name, column)]
_ADDITIVE_INDEXES: dict[str, list[tuple[str, str]]] = {
    "event_logs": [("ix_event_logs_data_version_id", "data_version_id")],
    "funnel_runs": [
        ("ix_funnel_runs_data_version_id", "data_version_id"),
        ("ix_funnel_runs_baseline_run_id", "baseline_run_id"),
        ("ix_funnel_runs_is_current", "is_current"),
    ],
    "drop_reports": [("ix_drop_reports_is_current", "is_current")],
}


def _table_names(conn) -> set[str]:
    return set(inspect(conn).get_table_names())


def _existing_columns(conn, table: str) -> set[str]:
    try:
        return {column["name"] for column in inspect(conn).get_columns(table)}
    except Exception:
        return set()


def _existing_indexes(conn, table: str) -> set[str]:
    try:
        return {index["name"] for index in inspect(conn).get_indexes(table)}
    except Exception:
        return set()


def evolve(engine: Engine) -> dict[str, int]:
    """补齐缺失列/索引并归一化 is_current；返回 {"columns_added": n, "indexes_added": n}。"""
    dialect = engine.dialect.name
    columns_added = 0
    indexes_added = 0
    with engine.begin() as conn:
        existing_tables = _table_names(conn)
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:  # 表本身还没建（create_all 会建），跳过
                continue
            present = _existing_columns(conn, table)
            for name, mysql_type, sqlite_type, server_default in columns:
                if name in present:
                    continue
                col_type = mysql_type if dialect == "mysql" else sqlite_type
                if server_default is not None and "DEFAULT" not in col_type.upper():
                    ddl = f"ALTER TABLE {table} ADD COLUMN {name} {col_type} DEFAULT {server_default}"
                else:
                    ddl = f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"
                conn.execute(text(ddl))
                columns_added += 1

        for table, indexes in _ADDITIVE_INDEXES.items():
            if table not in existing_tables:
                continue
            present_cols = _existing_columns(conn, table)
            present_indexes = _existing_indexes(conn, table)
            for index_name, column in indexes:
                if index_name in present_indexes or column not in present_cols:
                    continue
                conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({column})"))
                indexes_added += 1

        _normalize_is_current(conn, existing_tables)
    return {"columns_added": columns_added, "indexes_added": indexes_added}


def _normalize_is_current(conn, existing_tables: set[str]) -> None:
    """旧库补列后默认全为 1：每个 funnel 只保留最新一条 run 为 current。"""
    if "funnel_runs" not in existing_tables:
        return
    run_cols = _existing_columns(conn, "funnel_runs")
    if "is_current" not in run_cols or "funnel_id" not in run_cols:
        return
    conn.execute(
        text(
            """
            UPDATE funnel_runs
            SET is_current = CASE
                WHEN id IN (SELECT max_id FROM (
                    SELECT funnel_id, MAX(id) AS max_id
                    FROM funnel_runs
                    GROUP BY funnel_id
                ) latest) THEN 1
                ELSE 0
            END
            """
        )
    )
