"""PlanFlow 数据访问层（SQLite，标准库自带，无第三方依赖）。"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime
from typing import Any, Optional

import paths

DEFAULT_DB = paths.DB_PATH

PRIORITIES = ("高", "中", "低")
STATUSES = ("未开始", "进行中", "已完成", "已搁置")
ORDER_OPTIONS = ("截止日期", "优先级", "最近更新", "创建时间", "标题")

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT '默认',
    priority    TEXT    NOT NULL DEFAULT '中',
    status      TEXT    NOT NULL DEFAULT '未开始',
    start_date  TEXT,
    due_date    TEXT,
    progress    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    title      TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    position   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id);
CREATE INDEX IF NOT EXISTS idx_logs_plan  ON logs(plan_id);
CREATE INDEX IF NOT EXISTS idx_plans_due  ON plans(due_date);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


class Database:
    """所有持久化操作的唯一入口。"""

    _PLAN_FIELDS = {
        "title", "description", "category", "priority", "status",
        "start_date", "due_date", "progress",
    }

    _ORDER = {
        "截止日期": "CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC",
        "优先级": "CASE priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, due_date ASC",
        "最近更新": "updated_at DESC",
        "创建时间": "created_at DESC",
        "标题": "title COLLATE NOCASE ASC",
    }

    def __init__(self, path: str = DEFAULT_DB) -> None:
        self.path = path
        paths.ensure_config_dir()
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()

    # ------------------------------------------------------------------
    # 计划
    # ------------------------------------------------------------------
    def add_plan(self, title: str = "新计划", **fields: Any) -> int:
        now = _now()
        cur = self.conn.execute(
            """INSERT INTO plans
               (title, description, category, priority, status,
                start_date, due_date, progress, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title,
                fields.get("description", ""),
                fields.get("category", "默认"),
                fields.get("priority", "中"),
                fields.get("status", "未开始"),
                fields.get("start_date"),
                fields.get("due_date"),
                int(fields.get("progress", 0)),
                now,
                now,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_plan(self, plan_id: int, **fields: Any) -> None:
        fields = {k: v for k, v in fields.items() if k in self._PLAN_FIELDS}
        if not fields:
            return
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE plans SET {assignments} WHERE id = ?",
            [*fields.values(), plan_id],
        )
        self.conn.commit()

    def delete_plan(self, plan_id: int) -> None:
        self.conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        self.conn.commit()

    def get_plan(self, plan_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()

    def list_plans(
        self,
        search: str = "",
        status: str = "全部",
        category: str = "全部",
        order: str = "截止日期",
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM plans WHERE 1 = 1"
        args: list[Any] = []

        if search:
            like = f"%{search}%"
            sql += " AND (title LIKE ? OR description LIKE ? OR category LIKE ?)"
            args += [like, like, like]

        if category and category != "全部":
            sql += " AND category = ?"
            args.append(category)

        today = _today()
        if status == "今日到期":
            sql += " AND due_date = ? AND status != '已完成'"
            args.append(today)
        elif status == "逾期":
            sql += (
                " AND due_date IS NOT NULL AND due_date != ''"
                " AND due_date < ? AND status != '已完成'"
            )
            args.append(today)
        elif status and status != "全部":
            sql += " AND status = ?"
            args.append(status)

        sql += " ORDER BY " + self._ORDER.get(order, self._ORDER["截止日期"])
        return list(self.conn.execute(sql, args).fetchall())

    def list_categories(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT category FROM plans WHERE category != '' ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]

    # ------------------------------------------------------------------
    # 子任务
    # ------------------------------------------------------------------
    def add_task(self, plan_id: int, title: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS pos FROM tasks WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        cur = self.conn.execute(
            "INSERT INTO tasks (plan_id, title, done, position, created_at) VALUES (?, ?, 0, ?, ?)",
            (plan_id, title, row["pos"], _now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def tasks_for(self, plan_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM tasks WHERE plan_id = ? ORDER BY done ASC, position ASC, id ASC",
                (plan_id,),
            ).fetchall()
        )

    def toggle_task(self, task_id: int) -> None:
        self.conn.execute(
            "UPDATE tasks SET done = CASE done WHEN 0 THEN 1 ELSE 0 END WHERE id = ?",
            (task_id,),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def clear_done_tasks(self, plan_id: int) -> None:
        self.conn.execute(
            "DELETE FROM tasks WHERE plan_id = ? AND done = 1", (plan_id,)
        )
        self.conn.commit()

    def task_progress(self, plan_id: int) -> Optional[int]:
        """按子任务完成比例计算进度；没有子任务时返回 None。"""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n, SUM(done) AS d FROM tasks WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        if row is None or not row["n"]:
            return None
        return int(round((row["d"] or 0) / row["n"] * 100))

    # ------------------------------------------------------------------
    # 进度记录
    # ------------------------------------------------------------------
    def add_log(self, plan_id: int, content: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO logs (plan_id, content, created_at) VALUES (?, ?, ?)",
            (plan_id, content, _now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def logs_for(self, plan_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM logs WHERE plan_id = ? ORDER BY created_at DESC, id DESC",
                (plan_id,),
            ).fetchall()
        )

    def delete_log(self, log_id: int) -> None:
        self.conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
        self.conn.commit()

    def recent_logs(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT logs.*, plans.title AS plan_title
                   FROM logs LEFT JOIN plans ON plans.id = logs.plan_id
                   ORDER BY logs.created_at DESC, logs.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        )

    # ------------------------------------------------------------------
    # 统计 / 导出
    # ------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(status = '进行中') AS doing,
                      SUM(status = '已完成') AS done,
                      SUM(status = '未开始') AS todo,
                      SUM(status = '已搁置') AS paused,
                      AVG(progress) AS avg_progress
               FROM plans"""
        ).fetchone()
        total = row["total"] or 0
        done = row["done"] or 0
        overdue = self.conn.execute(
            """SELECT COUNT(*) FROM plans
               WHERE due_date IS NOT NULL AND due_date != ''
                 AND due_date < ? AND status != '已完成'""",
            (_today(),),
        ).fetchone()[0]
        return {
            "total": total,
            "doing": row["doing"] or 0,
            "done": done,
            "todo": row["todo"] or 0,
            "paused": row["paused"] or 0,
            "overdue": overdue,
            "rate": (done / total * 100) if total else 0.0,
            "avg_progress": row["avg_progress"] or 0.0,
        }

    def category_stats(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT category,
                          COUNT(*) AS n,
                          SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) AS done,
                          AVG(progress) AS avg_progress
                   FROM plans GROUP BY category ORDER BY n DESC, category ASC"""
            ).fetchall()
        )

    def export_json(self, path: str) -> int:
        plans = [dict(r) for r in self.conn.execute("SELECT * FROM plans ORDER BY id")]
        for plan in plans:
            plan["tasks"] = [dict(t) for t in self.tasks_for(plan["id"])]
            plan["logs"] = [dict(l) for l in self.logs_for(plan["id"])]
        payload = {
            "app": "PlanFlow",
            "exported_at": _now(),
            "count": len(plans),
            "plans": plans,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return len(plans)
