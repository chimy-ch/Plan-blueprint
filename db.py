"""PlanFlow 数据访问层（SQLite，标准库自带，无第三方依赖）。"""

from __future__ import annotations

import calendar as _calendar
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

import paths

DEFAULT_DB = paths.DB_PATH

PRIORITIES = ("高", "中", "低")
STATUSES = ("未开始", "进行中", "已完成", "已搁置")
ORDER_OPTIONS = ("截止日期", "优先级", "最近更新", "创建时间", "标题")

REPEAT_OPTIONS = ("不重复", "每天", "每周", "每月")

REMIND_CHOICES = (
    ("不提醒", -1),
    ("当天", 0),
    ("提前 1 天", 1),
    ("提前 3 天", 3),
    ("提前 7 天", 7),
)
REMIND_LABELS = {value: label for label, value in REMIND_CHOICES}
REMIND_LABEL_TO_VALUE = {label: value for label, value in REMIND_CHOICES}


def remind_label(value: Any) -> str:
    try:
        return REMIND_LABELS.get(int(value), "不提醒")
    except (TypeError, ValueError):
        return "不提醒"


def shift_date(iso: str, rule: str) -> Optional[str]:
    """按重复规则推进日期；无法推进时返回 None。"""
    if not iso:
        return None
    try:
        current = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None
    if rule == "每天":
        nxt = current + timedelta(days=1)
    elif rule == "每周":
        nxt = current + timedelta(days=7)
    elif rule == "每月":
        month = current.month + 1
        year = current.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        day = min(current.day, _calendar.monthrange(year, month)[1])
        nxt = date(year, month, day)
    else:
        return None
    return nxt.isoformat()

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
    repeat_rule TEXT    NOT NULL DEFAULT '不重复',
    remind_days INTEGER NOT NULL DEFAULT -1,
    notified_at TEXT,
    deleted_at  TEXT,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    title      TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    position   INTEGER NOT NULL DEFAULT 0,
    due_date   TEXT,
    priority   TEXT    NOT NULL DEFAULT '中',
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

# 旧版数据库升级用：列名 -> 建列语句
_MIGRATIONS = {
    "plans": {
        "repeat_rule": "ALTER TABLE plans ADD COLUMN repeat_rule TEXT NOT NULL DEFAULT '不重复'",
        "remind_days": "ALTER TABLE plans ADD COLUMN remind_days INTEGER NOT NULL DEFAULT -1",
        "notified_at": "ALTER TABLE plans ADD COLUMN notified_at TEXT",
        "deleted_at": "ALTER TABLE plans ADD COLUMN deleted_at TEXT",
    },
    "tasks": {
        "due_date": "ALTER TABLE tasks ADD COLUMN due_date TEXT",
        "priority": "ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT '中'",
    },
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


class Database:
    """所有持久化操作的唯一入口。"""

    _PLAN_FIELDS = {
        "title", "description", "category", "priority", "status",
        "start_date", "due_date", "progress",
        "repeat_rule", "remind_days", "notified_at", "deleted_at",
    }

    _TASK_FIELDS = {"title", "done", "position", "due_date", "priority"}

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
        self._migrate()
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plans_alive ON plans(deleted_at)"
        )
        self.conn.commit()

    def _migrate(self) -> None:
        """为旧版数据库补齐新增列（幂等）。"""
        for table, columns in _MIGRATIONS.items():
            existing = {
                row["name"]
                for row in self.conn.execute(f"PRAGMA table_info({table})")
            }
            for name, sql in columns.items():
                if name not in existing:
                    self.conn.execute(sql)

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
                start_date, due_date, progress, repeat_rule, remind_days,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title,
                fields.get("description", ""),
                fields.get("category", "默认"),
                fields.get("priority", "中"),
                fields.get("status", "未开始"),
                fields.get("start_date"),
                fields.get("due_date"),
                int(fields.get("progress", 0)),
                fields.get("repeat_rule", "不重复"),
                int(fields.get("remind_days", -1)),
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
        """真正删除（回收站里的「彻底删除」走这里）。"""
        self.conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # 回收站（软删除）
    # ------------------------------------------------------------------
    def trash_plan(self, plan_id: int) -> None:
        self.conn.execute(
            "UPDATE plans SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (_now(), _now(), plan_id),
        )
        self.conn.commit()

    def restore_plan(self, plan_id: int) -> None:
        self.conn.execute(
            "UPDATE plans SET deleted_at = NULL, updated_at = ? WHERE id = ?",
            (_now(), plan_id),
        )
        self.conn.commit()

    def list_trash(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT plans.*,
                          (SELECT COUNT(*) FROM tasks WHERE tasks.plan_id = plans.id) AS task_count
                   FROM plans WHERE deleted_at IS NOT NULL
                   ORDER BY deleted_at DESC, id DESC"""
            ).fetchall()
        )

    def trash_count(self) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM plans WHERE deleted_at IS NOT NULL"
            ).fetchone()[0]
        )

    def last_trashed(self) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM plans WHERE deleted_at IS NOT NULL
               ORDER BY deleted_at DESC, id DESC LIMIT 1"""
        ).fetchone()

    def empty_trash(self) -> int:
        cur = self.conn.execute("DELETE FROM plans WHERE deleted_at IS NOT NULL")
        self.conn.commit()
        return int(cur.rowcount or 0)

    def purge_plan(self, plan_id: int) -> None:
        self.conn.execute(
            "DELETE FROM plans WHERE id = ? AND deleted_at IS NOT NULL", (plan_id,)
        )
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
        due: str = "",
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM plans WHERE deleted_at IS NULL"
        args: list[Any] = []

        if search:
            like = f"%{search}%"
            sql += (
                " AND (title LIKE ? OR description LIKE ? OR category LIKE ?"
                " OR EXISTS (SELECT 1 FROM logs WHERE logs.plan_id = plans.id"
                "            AND logs.content LIKE ?)"
                " OR EXISTS (SELECT 1 FROM tasks WHERE tasks.plan_id = plans.id"
                "            AND tasks.title LIKE ?))"
            )
            args += [like, like, like, like, like]

        if category and category != "全部":
            sql += " AND category = ?"
            args.append(category)

        if due:
            sql += " AND due_date = ?"
            args.append(due)

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

    def plans_due_on(self, day: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT * FROM plans WHERE deleted_at IS NULL AND due_date = ?
                   ORDER BY CASE priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END,
                            status ASC, id ASC""",
                (day,),
            ).fetchall()
        )

    def due_counts(self, start: str, end: str) -> dict[str, int]:
        """返回 [start, end] 区间内每天的到期计划数（供月历使用）。"""
        rows = self.conn.execute(
            """SELECT due_date, COUNT(*) AS n FROM plans
               WHERE deleted_at IS NULL AND due_date IS NOT NULL AND due_date != ''
                 AND due_date >= ? AND due_date <= ?
               GROUP BY due_date""",
            (start, end),
        ).fetchall()
        return {r["due_date"]: int(r["n"]) for r in rows}

    def list_categories(self) -> list[str]:
        rows = self.conn.execute(
            """SELECT DISTINCT category FROM plans
               WHERE category != '' AND deleted_at IS NULL ORDER BY category"""
        ).fetchall()
        return [r["category"] for r in rows]

    # ------------------------------------------------------------------
    # 子任务
    # ------------------------------------------------------------------
    def add_task(
        self,
        plan_id: int,
        title: str,
        due_date: Optional[str] = None,
        priority: str = "中",
    ) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS pos FROM tasks WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        cur = self.conn.execute(
            """INSERT INTO tasks
               (plan_id, title, done, position, due_date, priority, created_at)
               VALUES (?, ?, 0, ?, ?, ?, ?)""",
            (plan_id, title, row["pos"], due_date or None, priority, _now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def task(self, task_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

    def update_task(self, task_id: int, **fields: Any) -> None:
        fields = {k: v for k, v in fields.items() if k in self._TASK_FIELDS}
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ?",
            [*fields.values(), task_id],
        )
        self.conn.commit()

    def tasks_for(self, plan_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM tasks WHERE plan_id = ? ORDER BY done ASC, position ASC, id ASC",
                (plan_id,),
            ).fetchall()
        )

    def move_task(self, task_id: int, offset: int) -> bool:
        """在未完成子任务中上/下移动一位，成功返回 True。"""
        row = self.task(task_id)
        if row is None:
            return False
        siblings = [
            t for t in self.tasks_for(row["plan_id"]) if not t["done"]
        ]
        order = [t["id"] for t in siblings]
        if task_id not in order:
            return False
        index = order.index(task_id)
        target = index + offset
        if target < 0 or target >= len(order):
            return False
        order.insert(target, order.pop(index))
        self.reorder_tasks(row["plan_id"], order)
        return True

    def reorder_tasks(self, plan_id: int, ordered_ids: list[int]) -> None:
        for position, task_id in enumerate(ordered_ids):
            self.conn.execute(
                "UPDATE tasks SET position = ? WHERE id = ? AND plan_id = ?",
                (position, task_id, plan_id),
            )
        self.conn.commit()

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
                   WHERE plans.deleted_at IS NULL
                   ORDER BY logs.created_at DESC, logs.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        )

    # ------------------------------------------------------------------
    # 提醒
    # ------------------------------------------------------------------
    def reminder_candidates(self) -> list[sqlite3.Row]:
        """所有开启了提醒、未完成且未删除的计划。"""
        return list(
            self.conn.execute(
                """SELECT * FROM plans
                   WHERE deleted_at IS NULL
                     AND status != '已完成'
                     AND due_date IS NOT NULL AND due_date != ''
                     AND remind_days >= 0"""
            ).fetchall()
        )

    def mark_notified(self, plan_id: int, due_date: Optional[str]) -> None:
        self.conn.execute(
            "UPDATE plans SET notified_at = ? WHERE id = ?",
            (due_date or "", plan_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # 重复计划
    # ------------------------------------------------------------------
    def repeat_plan(self, plan_id: int, due_date: str) -> Optional[int]:
        """按重复规则生成下一期计划（子任务重置为未完成），返回新计划 id。"""
        row = self.get_plan(plan_id)
        if row is None:
            return None
        delta = 0
        if row["due_date"]:
            try:
                delta = (
                    date.fromisoformat(str(due_date)[:10])
                    - date.fromisoformat(str(row["due_date"])[:10])
                ).days
            except ValueError:
                delta = 0
        new_id = self.add_plan(
            row["title"],
            description=row["description"],
            category=row["category"],
            priority=row["priority"],
            status="未开始",
            due_date=due_date,
            progress=0,
            repeat_rule=row["repeat_rule"],
            remind_days=row["remind_days"],
        )
        for task in self.tasks_for(plan_id):
            task_due = task["due_date"]
            if task_due and delta:
                try:
                    task_due = (
                        date.fromisoformat(str(task_due)[:10])
                        + timedelta(days=delta)
                    ).isoformat()
                except ValueError:
                    pass
            self.add_task(new_id, task["title"], task_due, task["priority"])
        self.add_log(new_id, f"由重复计划 #{plan_id} 自动生成")
        return new_id

    # ------------------------------------------------------------------
    # 备份 / 导入
    # ------------------------------------------------------------------
    def backup_to(self, directory: str, keep: int = 10) -> str:
        """用 SQLite 在线备份 API 生成快照，返回备份文件路径。"""
        os.makedirs(directory, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = os.path.join(directory, f"planflow-{stamp}.db")
        dest = sqlite3.connect(target)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        backups = sorted(
            (
                os.path.join(directory, name)
                for name in os.listdir(directory)
                if name.startswith("planflow-") and name.endswith(".db")
            ),
            key=os.path.getmtime,
            reverse=True,
        )
        for old in backups[max(keep, 1):]:
            try:
                os.remove(old)
            except OSError:
                pass
        return target

    def import_json(self, path: str) -> int:
        """导入 export_json 生成的备份文件，返回新增的计划条数。"""
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        plans = payload.get("plans") if isinstance(payload, dict) else payload
        if not isinstance(plans, list):
            raise ValueError("文件格式无法识别")
        added = 0
        for item in plans:
            if not isinstance(item, dict):
                continue
            try:
                new_id = self.add_plan(
                    str(item.get("title") or "未命名计划"),
                    description=str(item.get("description") or ""),
                    category=str(item.get("category") or "默认"),
                    priority=str(item.get("priority") or "中"),
                    status=str(item.get("status") or "未开始"),
                    start_date=item.get("start_date") or None,
                    due_date=item.get("due_date") or None,
                    progress=int(item.get("progress") or 0),
                    repeat_rule=str(item.get("repeat_rule") or "不重复"),
                    remind_days=int(item.get("remind_days") or -1),
                )
            except (TypeError, ValueError):
                continue
            for task in item.get("tasks") or []:
                if not isinstance(task, dict):
                    continue
                task_id = self.add_task(
                    new_id,
                    str(task.get("title") or ""),
                    task.get("due_date") or None,
                    str(task.get("priority") or "中"),
                )
                if task.get("done"):
                    self.update_task(task_id, done=1)
            for log in item.get("logs") or []:
                if isinstance(log, dict) and log.get("content"):
                    self.add_log(new_id, str(log["content"]))
            added += 1
        return added

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
               FROM plans WHERE deleted_at IS NULL"""
        ).fetchone()
        total = row["total"] or 0
        done = row["done"] or 0
        overdue = self.conn.execute(
            """SELECT COUNT(*) FROM plans
               WHERE deleted_at IS NULL
                 AND due_date IS NOT NULL AND due_date != ''
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
            "trash": self.trash_count(),
        }

    def category_stats(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT category,
                          COUNT(*) AS n,
                          SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) AS done,
                          AVG(progress) AS avg_progress
                   FROM plans WHERE deleted_at IS NULL
                   GROUP BY category ORDER BY n DESC, category ASC"""
            ).fetchall()
        )

    def export_json(self, path: str) -> int:
        plans = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM plans WHERE deleted_at IS NULL ORDER BY id"
            )
        ]
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
