# -*- coding: utf-8 -*-
"""AVA Persistent Long-Running Task Engine.

* MySQL-backed (ava_tasks / ava_task_steps / ava_task_logs)
* real action registry with validation, timeout, permission and verification
* one background worker -> no duplicate execution
* checkpoint after every step; auto-resume after a crash/restart
* approval gate for destructive / overwrite actions
* bounded retries, cancellation, progress callbacks
* never runs arbitrary shell or SQL
"""
from __future__ import annotations

import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for _d in (os.path.abspath(os.getcwd()), _exe_dir, os.path.dirname(_exe_dir)):
        if os.path.exists(os.path.join(_d, "asif_key.txt")):
            APP_DIR = _d
            break
SANDBOX = os.path.join(APP_DIR, "test_area")

STATES = ("CREATED", "PLANNING", "READY", "RUNNING", "WAITING_FOR_APPROVAL",
          "PAUSED", "RETRYING", "VERIFYING", "COMPLETED", "FAILED", "CANCELLED")

MAX_RETRIES = 2
_worker_thread: threading.Thread | None = None
_worker_stop = threading.Event()
_worker_lock = threading.Lock()
_schema_ready = False
_schema_lock = threading.Lock()


class TaskEngineError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Action registry
# --------------------------------------------------------------------------
@dataclass
class ActionSpec:
    name: str
    handler: Callable[[dict], object]
    permission: str = "read"          # read | write | destructive | system
    timeout: float = 30.0
    idempotent: bool = True
    requires_approval: bool = False
    validate: Callable[[dict], None] | None = None
    verify: Callable[[dict, object], bool] | None = None
    description: str = ""


REGISTRY: dict[str, ActionSpec] = {}


def register_action(name: str, handler: Callable[[dict], object], *,
                    permission: str = "read", timeout: float = 30.0,
                    idempotent: bool = True, requires_approval: bool = False,
                    validate: Callable[[dict], None] | None = None,
                    verify: Callable[[dict, object], bool] | None = None,
                    description: str = "") -> ActionSpec:
    spec = ActionSpec(name, handler, permission, timeout, idempotent,
                      requires_approval, validate, verify, description)
    REGISTRY[name] = spec
    return spec


def get_action(name: str) -> ActionSpec:
    spec = REGISTRY.get(name)
    if not spec:
        raise TaskEngineError(f"অজানা action: {name}")
    return spec


def _req_path(params: dict) -> str:
    p = params.get("path")
    if not isinstance(p, str) or not p.strip():
        raise TaskEngineError("path প্রয়োজন")
    return os.path.abspath(os.path.expanduser(p.strip()))


def _req_str(params: dict, key: str, allow_empty: bool = False) -> str:
    v = params.get(key)
    if not isinstance(v, str) or (not allow_empty and not v.strip()):
        raise TaskEngineError(f"{key} প্রয়োজন")
    return v


def _inside_sandbox(path: str) -> bool:
    real = os.path.realpath(path)
    root = os.path.realpath(SANDBOX)
    return real == root or real.startswith(root + os.sep)


def _h_list_dir(params):
    path = _req_path(params)
    if not os.path.isdir(path):
        raise TaskEngineError(f"ফোল্ডার নেই: {path}")
    return {"path": path, "entries": sorted(os.listdir(path))[:500]}


def _v_list_dir(params):
    if not os.path.isdir(_req_path(params)):
        raise TaskEngineError("ফোল্ডার নেই")


def _h_read_text(params):
    path = _req_path(params)
    limit = int(params.get("max_bytes", 20000))
    if not os.path.isfile(path):
        raise TaskEngineError(f"ফাইল নেই: {path}")
    with open(path, encoding="utf-8", errors="replace") as f:
        return {"path": path, "text": f.read(limit)}


def _v_read_text(params):
    if not os.path.isfile(_req_path(params)):
        raise TaskEngineError("ফাইল নেই")


def _h_ensure_dir(params):
    path = _req_path(params)
    os.makedirs(path, exist_ok=True)
    return {"path": path, "is_dir": os.path.isdir(path)}


def _h_write_text(params):
    path = _req_path(params)
    content = params.get("content", "")
    if not isinstance(content, str):
        raise TaskEngineError("content string হতে হবে")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": path, "bytes": len(content.encode("utf-8"))}


def _verify_write(params, result):
    path = _req_path(params)
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read() == params.get("content", "")


def _h_delete_path(params):
    path = _req_path(params)
    if not _inside_sandbox(path):
        raise TaskEngineError("নিরাপত্তা: sandbox-এর বাইরে delete নিষিদ্ধ")
    if os.path.realpath(path) == os.path.realpath(SANDBOX):
        raise TaskEngineError("sandbox root নিজে delete করা যাবে না")
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)
    return {"path": path, "deleted": True}


def _verify_delete(params, result):
    return not os.path.exists(_req_path(params))


def _h_py_compile(params):
    path = _req_path(params)
    if not os.path.isfile(path):
        raise TaskEngineError(f"ফাইল নেই: {path}")
    proc = subprocess.run([sys.executable, "-m", "py_compile", path],
                          capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise TaskEngineError((proc.stderr or proc.stdout or "py_compile failed")[:2000])
    return {"path": path, "returncode": 0}


def _h_sleep(params):
    sec = float(params.get("seconds", 0.2))
    if sec < 0 or sec > 5:
        raise TaskEngineError("seconds 0-5 এর মধ্যে হতে হবে")
    time.sleep(sec)
    return {"slept": sec}


def _h_stat(params):
    path = _req_path(params)
    exists = os.path.exists(path)
    if params.get("require_exists") and not exists:
        raise TaskEngineError(f"target নেই: {path}")
    return {"path": path, "exists": exists,
            "is_dir": os.path.isdir(path), "is_file": os.path.isfile(path),
            "size": os.path.getsize(path) if os.path.isfile(path) else None}


def _val_py_compile(params):
    p = _req_path(params)
    if not os.path.isfile(p) or not p.lower().endswith(".py"):
        raise TaskEngineError("একটি .py ফাইল দরকার")


register_action("list_dir", _h_list_dir, permission="read", validate=_v_list_dir,
                description="ফোল্ডারের ফাইল তালিকা")
register_action("read_text", _h_read_text, permission="read", validate=_v_read_text,
                description="টেক্সট ফাইল পড়া")
register_action("stat_path", _h_stat, permission="read",
                description="ফাইল/ফোল্ডার আছে কি না দেখা")
register_action("ensure_dir", _h_ensure_dir, permission="write",
                description="ফোল্ডার তৈরি (থাকলে ঠিক থাকে)")
register_action("write_text", _h_write_text, permission="write",
                verify=_verify_write, description="টেক্সট ফাইল লেখা")
register_action("delete_path", _h_delete_path, permission="destructive",
                requires_approval=True, verify=_verify_delete,
                description="ফাইল/ফোল্ডার স্থায়ীভাবে মুছে ফেলা (sandbox-only, approval)")
register_action("py_compile", _h_py_compile, permission="system", timeout=40,
                validate=_val_py_compile, description="Python ফাইল compile যাচাই")
register_action("sleep", _h_sleep, permission="read", timeout=10,
                description="ছোট বিরতি (সর্বোচ্চ ৫s)")


def _needs_approval(step: dict, spec: ActionSpec) -> bool:
    if spec.requires_approval:
        return True
    if step.get("requires_approval"):
        return True
    if spec.name == "write_text":
        p = os.path.abspath(os.path.expanduser(step.get("params", {}).get("path", "")))
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    return f.read() != step.get("params", {}).get("content", "")
            except Exception:
                return True
        if not _inside_sandbox(p):
            return False
    return False


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def _connect():
    try:
        import memory_db
        conn = memory_db.get_connection()
    except Exception as e:
        raise TaskEngineError(f"MySQL প্রয়োজন: {e}")
    return conn


DDL = [
    """CREATE TABLE IF NOT EXISTS ava_tasks (
        id VARCHAR(36) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        instruction TEXT,
        status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
        current_step INT NOT NULL DEFAULT 0,
        retry_count INT NOT NULL DEFAULT 0,
        checkpoint LONGTEXT,
        next_action TEXT,
        last_error TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS ava_task_steps (
        task_id VARCHAR(36) NOT NULL,
        step_index INT NOT NULL,
        title VARCHAR(255),
        action VARCHAR(64) NOT NULL,
        params LONGTEXT,
        status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
        idempotent TINYINT NOT NULL DEFAULT 1,
        requires_approval TINYINT NOT NULL DEFAULT 0,
        approved TINYINT NOT NULL DEFAULT 0,
        attempts INT NOT NULL DEFAULT 0,
        result LONGTEXT,
        error TEXT,
        started_at DATETIME NULL,
        finished_at DATETIME NULL,
        PRIMARY KEY (task_id, step_index),
        CONSTRAINT fk_ava_step_task FOREIGN KEY (task_id)
            REFERENCES ava_tasks(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS ava_task_logs (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        task_id VARCHAR(36) NOT NULL,
        step_index INT NULL,
        level VARCHAR(16) NOT NULL DEFAULT 'info',
        message TEXT,
        created_at DATETIME NOT NULL,
        KEY idx_task (task_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn = _connect()
        try:
            with conn.cursor() as cur:
                for ddl in DDL:
                    cur.execute(ddl)
            conn.commit()
            _schema_ready = True
        finally:
            conn.close()


def _now():
    return datetime.datetime.now()


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _pj(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return None


def _log(conn, task_id, step_index, level, message):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ava_task_logs (task_id, step_index, level, message, created_at) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (task_id, step_index, level, (message or "")[:4000], _now()))


# --------------------------------------------------------------------------
# Plan validation
# --------------------------------------------------------------------------
def _plan_path(value: str) -> str:
    """Planner paths are sandbox-relative; absolute paths must stay inside."""
    p = os.path.expanduser(str(value).strip())
    if os.path.isabs(p):
        if not _inside_sandbox(p):
            raise TaskEngineError(f"path sandbox-এর বাইরে নিষিদ্ধ: {p}")
        return os.path.abspath(p)
    return os.path.abspath(os.path.join(SANDBOX, p))


def normalize_plan(steps) -> list[dict]:
    if not isinstance(steps, list) or not steps:
        raise TaskEngineError("plan-এ অন্তত একটি step দরকার")
    clean = []
    for i, raw in enumerate(steps):
        if not isinstance(raw, dict):
            raise TaskEngineError(f"step {i}: object দরকার")
        action = raw.get("action")
        spec = get_action(action)
        params = raw.get("params") or {}
        if not isinstance(params, dict):
            raise TaskEngineError(f"step {i}: params object দরকার")
        if isinstance(params.get("path"), str):
            params = dict(params)
            params["path"] = _plan_path(params["path"])
        if spec.validate:
            spec.validate(params)
        clean.append({
            "index": i,
            "title": str(raw.get("title") or spec.description or action)[:255],
            "action": action,
            "params": params,
            "idempotent": 1 if raw.get("idempotent", spec.idempotent) else 0,
            "requires_approval": 1 if raw.get("requires_approval", spec.requires_approval) else 0,
        })
    return clean


def validate_plan(steps) -> list[dict]:
    return normalize_plan(steps)


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------
def create_task(title: str, instruction: str, steps, status: str = "CREATED") -> str:
    ensure_schema()
    plan = normalize_plan(steps)
    tid = str(uuid.uuid4())
    now = _now()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ava_tasks (id,title,instruction,status,current_step,retry_count,"
                "checkpoint,next_action,last_error,created_at,updated_at) "
                "VALUES (%s,%s,%s,%s,0,0,%s,%s,NULL,%s,%s)",
                (tid, title[:255], instruction, status,
                 _j({"completed_steps": 0, "total_steps": len(plan)}),
                 plan[0]["title"], now, now))
            for s in plan:
                cur.execute(
                    "INSERT INTO ava_task_steps (task_id,step_index,title,action,params,status,"
                    "idempotent,requires_approval,approved,attempts) "
                    "VALUES (%s,%s,%s,%s,%s,'CREATED',%s,%s,0,0)",
                    (tid, s["index"], s["title"], s["action"], _j(s["params"]),
                     s["idempotent"], s["requires_approval"]))
        conn.commit()
        _log(conn, tid, None, "info", f"task created: {title} ({len(plan)} steps)")
        conn.commit()
    finally:
        conn.close()
    return tid


def _task_row(tid):
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ava_tasks WHERE id=%s", (tid,))
            task = cur.fetchone()
            if not task:
                return None, []
            cur.execute("SELECT * FROM ava_task_steps WHERE task_id=%s ORDER BY step_index", (tid,))
            steps = cur.fetchall()
        return task, steps
    finally:
        conn.close()


def get_task(tid: str) -> dict | None:
    task, steps = _task_row(tid)
    if not task:
        return None
    task = dict(task)
    task["checkpoint"] = _pj(task.get("checkpoint")) or {}
    task["steps"] = []
    for s in steps:
        s = dict(s)
        s["params"] = _pj(s.get("params")) or {}
        s["result"] = _pj(s.get("result"))
        task["steps"].append(s)
    return task


def list_tasks(status: str | None = None, limit: int = 20) -> list[dict]:
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT id,title,status,current_step,created_at,updated_at "
                            "FROM ava_tasks WHERE status=%s ORDER BY created_at DESC LIMIT %s",
                            (status, int(limit)))
            else:
                cur.execute("SELECT id,title,status,current_step,created_at,updated_at "
                            "FROM ava_tasks ORDER BY created_at DESC LIMIT %s", (int(limit),))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def enqueue(tid: str) -> bool:
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute(
                "UPDATE ava_tasks SET status='READY', updated_at=%s "
                "WHERE id=%s AND status IN ('CREATED','PLANNING','READY','PAUSED','RETRYING')",
                (_now(), tid))
        conn.commit()
        if n:
            _log(conn, tid, None, "info", "enqueued")
            conn.commit()
        return bool(n)
    finally:
        conn.close()


def _set_task(conn, tid, **fields):
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ",".join(f"{k}=%s" for k in fields)
    vals = list(fields.values()) + [tid]
    with conn.cursor() as cur:
        cur.execute(f"UPDATE ava_tasks SET {cols} WHERE id=%s", vals)


def _set_step(conn, tid, idx, **fields):
    if not fields:
        return
    cols = ",".join(f"{k}=%s" for k in fields)
    vals = list(fields.values()) + [tid, idx]
    with conn.cursor() as cur:
        cur.execute(f"UPDATE ava_task_steps SET {cols} WHERE task_id=%s AND step_index=%s", vals)


def _advance_checkpoint(conn, task: dict, completed: int):
    total = len(task["steps"])
    next_action = task["steps"][completed]["title"] if completed < total else None
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ava_tasks SET current_step=%s, checkpoint=%s, next_action=%s, "
            "last_error=NULL, updated_at=%s, status=CASE "
            "WHEN status IN ('CANCELLED','PAUSED','WAITING_FOR_APPROVAL') THEN status "
            "WHEN %s>=%s THEN 'COMPLETED' ELSE 'RUNNING' END WHERE id=%s",
            (completed, _j({"completed_steps": completed, "total_steps": total}),
             next_action, _now(), completed, total, task["id"]))
        cur.execute("SELECT status FROM ava_tasks WHERE id=%s", (task["id"],))
        row = cur.fetchone()
    status = row["status"] if row else "RUNNING"
    return status, next_action


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------
def _run_with_timeout(spec: ActionSpec, params: dict):
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(spec.handler, params)
    try:
        return fut.result(timeout=spec.timeout)
    except concurrent.futures.TimeoutError:
        fut.cancel()
        raise TaskEngineError(f"action timeout ({spec.timeout}s): {spec.name}")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def run_task(tid: str, progress: Callable | None = None, max_retries: int = MAX_RETRIES) -> dict:
    """Execute a task synchronously from its persisted checkpoint.

    Safe to call after a restart: it never blindly re-runs a non-idempotent
    step that was interrupted mid-flight (that becomes WAITING_FOR_APPROVAL)."""
    ensure_schema()
    task = get_task(tid)
    if not task:
        return {"ok": False, "error": "task not found"}
    if task["status"] in ("COMPLETED", "CANCELLED", "FAILED"):
        return {"ok": task["status"] == "COMPLETED", "status": task["status"], "task": task}

    def emit(kind, **data):
        if progress:
            try:
                progress(kind, {**data, "task_id": tid})
            except Exception:
                pass

    conn = _connect()
    try:
        while True:
            task = get_task(tid)
            if not task:
                return {"ok": False, "error": "task disappeared"}
            if task["status"] in ("CANCELLED", "PAUSED", "WAITING_FOR_APPROVAL"):
                emit("stopped", status=task["status"])
                return {"ok": False, "status": task["status"], "task": task}
            idx = int(task["current_step"])
            steps = task["steps"]
            if idx >= len(steps):
                _set_task(conn, tid, status="COMPLETED", next_action=None)
                conn.commit()
                _log(conn, tid, None, "info", "task completed")
                conn.commit()
                emit("completed", status="COMPLETED")
                return {"ok": True, "status": "COMPLETED", "task": get_task(tid)}

            step = steps[idx]
            spec = get_action(step["action"])

            if step["status"] == "COMPLETED":
                _set_task(conn, tid, current_step=idx + 1, updated_at=_now())
                conn.commit()
                continue

            if _needs_approval(step, spec) and not step.get("approved"):
                _set_step(conn, tid, idx, status="WAITING_FOR_APPROVAL")
                _set_task(conn, tid, status="WAITING_FOR_APPROVAL",
                          next_action=f"approval: {step['title']}")
                conn.commit()
                _log(conn, tid, idx, "warn",
                     f"approval required for {spec.name}: {step['title']}")
                conn.commit()
                emit("approval_required", step=idx, title=step["title"])
                return {"ok": False, "status": "WAITING_FOR_APPROVAL",
                        "step": idx, "task": get_task(tid)}

            _set_step(conn, tid, idx, status="RUNNING", started_at=_now())
            _set_task(conn, tid, status="RUNNING", next_action=step["title"])
            conn.commit()
            _log(conn, tid, idx, "info", f"step {idx} start: {step['title']}")
            conn.commit()
            emit("step_start", step=idx, title=step["title"])

            try:
                result = _run_with_timeout(spec, step["params"])
                if spec.verify and not spec.verify(step["params"], result):
                    raise TaskEngineError("verification failed")
            except Exception as e:
                attempts = int(step.get("attempts") or 0) + 1
                err = f"{type(e).__name__}: {e}"
                if step["idempotent"] and attempts <= max_retries:
                    _set_step(conn, tid, idx, status="RETRYING", attempts=attempts, error=err)
                    _set_task(conn, tid, status="RETRYING", last_error=err,
                              retry_count=int(task.get("retry_count") or 0) + 1)
                    conn.commit()
                    _log(conn, tid, idx, "warn",
                         f"step {idx} retry {attempts}/{max_retries}: {err}")
                    conn.commit()
                    emit("retry", step=idx, attempt=attempts, error=err)
                    time.sleep(min(1.5, 0.3 * attempts))
                    continue
                _set_step(conn, tid, idx, status="FAILED", attempts=attempts,
                          error=err, finished_at=_now())
                _set_task(conn, tid, status="FAILED", last_error=err,
                          next_action=f"failed: {step['title']}")
                conn.commit()
                _log(conn, tid, idx, "error", f"step {idx} failed: {err}")
                conn.commit()
                emit("failed", step=idx, error=err)
                return {"ok": False, "status": "FAILED", "step": idx,
                        "error": err, "task": get_task(tid)}

            _set_step(conn, tid, idx, status="COMPLETED", result=_j(result),
                      error=None, attempts=int(step.get("attempts") or 0),
                      finished_at=_now())
            new_status, next_action = _advance_checkpoint(conn, task, idx + 1)
            conn.commit()
            _log(conn, tid, idx, "info", f"step {idx} done: {step['title']}")
            conn.commit()
            emit("step_done", step=idx, title=step["title"], status=new_status)
            if new_status == "COMPLETED":
                emit("completed", status="COMPLETED")
                return {"ok": True, "status": "COMPLETED", "task": get_task(tid)}
    finally:
        conn.close()


def start_worker(progress: Callable | None = None) -> str:
    """Start exactly one background worker. Returns a status string."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return "worker ইতিমধ্যে চলছে"
        _worker_stop.clear()
        _worker_thread = threading.Thread(target=_worker_loop, args=(progress,),
                                          daemon=True, name="ava-task-worker")
        _worker_thread.start()
        return "task worker চালু"


def stop_worker() -> None:
    _worker_stop.set()


def _claim_next() -> str | None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ava_tasks WHERE status IN ('READY','RETRYING') "
                        "ORDER BY created_at ASC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            tid = row["id"]
            n = cur.execute("UPDATE ava_tasks SET status='RUNNING', updated_at=%s "
                            "WHERE id=%s AND status IN ('READY','RETRYING')",
                            (_now(), tid))
        conn.commit()
        return tid if n else None
    finally:
        conn.close()


def _worker_loop(progress):
    while not _worker_stop.is_set():
        try:
            tid = _claim_next()
            if tid:
                run_task(tid, progress)
            else:
                time.sleep(0.4)
        except Exception as e:
            print(f"⚠️  task worker: {type(e).__name__}: {e}")
            time.sleep(2.0)


# --------------------------------------------------------------------------
# Control
# --------------------------------------------------------------------------
def approve(tid: str, step_index: int | None = None) -> bool:
    task = get_task(tid)
    if not task:
        return False
    idx = int(task["current_step"]) if step_index is None else int(step_index)
    if idx < 0 or idx >= len(task["steps"]):
        return False
    conn = _connect()
    try:
        _set_step(conn, tid, idx, approved=1, status="READY", error=None)
        _set_task(conn, tid, status="READY", next_action=task["steps"][idx]["title"])
        conn.commit()
        _log(conn, tid, idx, "info", f"approved step {idx}")
        conn.commit()
        return True
    finally:
        conn.close()


def cancel(tid: str) -> bool:
    conn = _connect()
    try:
        n = 0
        with conn.cursor() as cur:
            n = cur.execute("UPDATE ava_tasks SET status='CANCELLED', updated_at=%s "
                            "WHERE id=%s AND status NOT IN ('COMPLETED','FAILED','CANCELLED')",
                            (_now(), tid))
        conn.commit()
        if n:
            _log(conn, tid, None, "warn", "cancelled by user")
            conn.commit()
        return bool(n)
    finally:
        conn.close()


def pause(tid: str) -> bool:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute("UPDATE ava_tasks SET status='PAUSED', updated_at=%s "
                            "WHERE id=%s AND status IN ('READY','RUNNING','RETRYING')",
                            (_now(), tid))
        conn.commit()
        return bool(n)
    finally:
        conn.close()


def resume_pending(progress: Callable | None = None) -> list[str]:
    """After a restart: recover unfinished tasks from their checkpoint.

    * interrupted idempotent step -> re-run safely
    * interrupted non-idempotent step -> WAITING_FOR_APPROVAL (never blind repeat)
    * completed steps -> advance checkpoint
    """
    ensure_schema()
    resumed = []
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ava_tasks WHERE status IN "
                        "('RUNNING','READY','RETRYING','VERIFYING')")
            ids = [r["id"] for r in cur.fetchall()]
        for tid in ids:
            task = get_task(tid)
            if not task:
                continue
            idx = int(task["current_step"])
            steps = task["steps"]
            if idx >= len(steps):
                _set_task(conn, tid, status="COMPLETED", next_action=None)
                conn.commit()
                continue
            step = steps[idx]
            if step["status"] == "RUNNING":
                if step["idempotent"]:
                    _set_step(conn, tid, idx, status="READY", error="resumed after restart")
                    _set_task(conn, tid, status="READY", next_action=step["title"])
                    _log(conn, tid, idx, "warn", "resumed idempotent step")
                    resumed.append(tid)
                else:
                    _set_step(conn, tid, idx, status="WAITING_FOR_APPROVAL")
                    _set_task(conn, tid, status="WAITING_FOR_APPROVAL",
                              next_action=f"approval after restart: {step['title']}")
                    _log(conn, tid, idx, "warn",
                         "non-idempotent step interrupted; approval required")
            elif step["status"] == "COMPLETED":
                _advance_checkpoint(conn, task, idx + 1)
                _set_task(conn, tid, status="READY", updated_at=_now())
                resumed.append(tid)
            else:
                _set_step(conn, tid, idx, status="READY")
                _set_task(conn, tid, status="READY", next_action=step["title"])
                resumed.append(tid)
        conn.commit()
    finally:
        conn.close()
    if progress:
        try:
            progress("resume", {"task_ids": resumed})
        except Exception:
            pass
    return resumed


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def status_text(tid: str | None = None) -> str:
    if tid:
        t = get_task(tid)
        if not t:
            return "❌ টাস্ক পাওয়া যায়নি।"
        done = sum(1 for s in t["steps"] if s["status"] == "COMPLETED")
        lines = [f"📋 {t['title']}", f"স্ট্যাটাস: {t['status']}",
                 f"ধাপ: {done}/{len(t['steps'])} সম্পন্ন",
                 f"পরবর্তী: {t.get('next_action') or '—'}"]
        if t.get("last_error"):
            lines.append(f"ত্রুটি: {str(t['last_error'])[:160]}")
        cur = t["steps"][min(int(t["current_step"]), len(t["steps"]) - 1)]
        lines.append(f"বর্তমান ধাপ: {cur['title']} ({cur['status']})")
        return "\n".join(lines)
    rows = list_tasks(limit=10)
    if not rows:
        return "কোনো টাস্ক নেই।"
    lines = ["📋 সাম্প্রতিক টাস্ক:"]
    for r in rows:
        lines.append(f"• {r['id'][:8]} — {r['title']} [{r['status']}]")
    return "\n".join(lines)


def resolve_task_id(token: str) -> str | None:
    """Full UUID or unique short prefix -> task id."""
    token = (token or "").strip().lower()
    if not token:
        return None
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ava_tasks WHERE id=%s", (token,))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute("SELECT id FROM ava_tasks WHERE id LIKE %s LIMIT 2",
                        (token + "%",))
            rows = cur.fetchall()
            return rows[0]["id"] if len(rows) == 1 else None
    finally:
        conn.close()


PLANNER_ACTIONS = """\
- ensure_dir      {"path": "<abs path under sandbox>"}
- write_text      {"path": "<abs path>", "content": "<text>"}
- read_text       {"path": "<abs path>", "max_bytes": 20000}
- list_dir        {"path": "<abs dir>"}
- stat_path       {"path": "<abs path>", "require_exists": true}
- py_compile      {"path": "<abs .py>"}
- sleep           {"seconds": 0.2}
- delete_path     {"path": "<abs path inside sandbox>"}   (needs user approval)
"""


def planner_spec() -> str:
    return (f"Allowed actions (use ONLY these, exact names):\n{PLANNER_ACTIONS}\n"
            f"Sandbox root: {SANDBOX}\n"
            "Every params.path MUST be RELATIVE to the sandbox (for example "
            "planner_test/report.txt). Never use a drive letter. Never use shell, "
            "SQL, network or any other action. Produce 2-12 concrete steps and keep "
            "file content exactly as the user asked. Reply with JSON only: "
            '{"steps":[{"title":"...","action":"...","params":{...}}]}')


def planner_schema() -> dict:
    return {
        "type": "object",
        "properties": {"steps": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "action": {"type": "string", "enum": list(REGISTRY.keys())},
                "params": {"type": "object", "additionalProperties": True},
            },
            "required": ["title", "action", "params"],
        }}},
        "required": ["steps"],
    }


def parse_plan_json(text: str) -> list[dict]:
    if not isinstance(text, str) or not text.strip():
        raise TaskEngineError("planner খালি উত্তর দিয়েছে")
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise TaskEngineError("planner JSON পায়নি")
    try:
        data = json.loads(raw[start:end + 1])
    except Exception as e:
        raise TaskEngineError(f"planner JSON ভুল: {e}")
    steps = data.get("steps") if isinstance(data, dict) else data
    return normalize_plan(steps)


def summary(tid: str) -> dict:
    t = get_task(tid)
    if not t:
        return {"error": "not found"}
    done = sum(1 for s in t["steps"] if s["status"] == "COMPLETED")
    failed = sum(1 for s in t["steps"] if s["status"] == "FAILED")
    return {"id": tid, "title": t["title"], "status": t["status"],
            "steps": len(t["steps"]), "completed": done, "failed": failed,
            "retries": t.get("retry_count", 0), "next_action": t.get("next_action"),
            "last_error": t.get("last_error")}
