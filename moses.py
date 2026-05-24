from __future__ import annotations

import argparse
import ast
import difflib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - handled at runtime for friendly setup.
    load_dotenv = None

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - handled at runtime for friendly setup.
    genai = None
    types = None


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEZONE = "Asia/Kolkata"


SYSTEM_INSTRUCTION = """
Your name is MOSES. You are the user's agentic personal assistant.

Operate like a capable executive assistant: clarify only when necessary, break big
requests into steps, use tools when they help, remember useful preferences, and
keep answers practical. You can manage todos, notes, reminders, lightweight
memory, dates, calculations, and workspace text files through your tools.

Important behavior:
- Be warm, concise, and useful.
- When a request implies action, use the available tool instead of only talking.
- Confirm what you changed after using a tool.
- You may read and change text files inside the configured workspace. Do not try
  to access secrets, git internals, dependency folders, or files outside the
  workspace.
- Workspace file changes require Cowork mode. If Cowork mode is off, explain
  that the user can enable it with the Cowork button in the GUI.
- In Cowork mode, file changes are staged for user review. Tell the user that
  proposed edits are waiting in the Changes tab when a change is staged.
- Treat reminders as stored reminder records, not real push notifications.
- Never claim you emailed, messaged, purchased, booked, or changed outside
  services unless an explicit external tool exists for that action.
""".strip()


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def resolve_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def parse_datetime(value: str, timezone: str) -> str:
    text = value.strip()
    if not text:
        return ""

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=resolve_timezone(timezone))
    return parsed.isoformat()


class SafeCalculator(ast.NodeVisitor):
    allowed_binary_ops = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a**b,
    }
    allowed_unary_ops = {
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }
    allowed_names = {
        "e": math.e,
        "pi": math.pi,
        "tau": math.tau,
    }
    allowed_functions = {
        "abs": abs,
        "ceil": math.ceil,
        "floor": math.floor,
        "round": round,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
    }

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, int | float):
            return node.value
        raise ValueError("Only numeric values are allowed.")

    def visit_BinOp(self, node: ast.BinOp) -> float:
        op_type = type(node.op)
        if op_type not in self.allowed_binary_ops:
            raise ValueError("That math operator is not allowed.")
        return self.allowed_binary_ops[op_type](self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        op_type = type(node.op)
        if op_type not in self.allowed_unary_ops:
            raise ValueError("That unary operator is not allowed.")
        return self.allowed_unary_ops[op_type](self.visit(node.operand))

    def visit_Name(self, node: ast.Name) -> float:
        if node.id not in self.allowed_names:
            raise ValueError(f"Unknown name: {node.id}")
        return self.allowed_names[node.id]

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name) or node.func.id not in self.allowed_functions:
            raise ValueError("That function is not allowed.")
        args = [self.visit(arg) for arg in node.args]
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed.")
        return self.allowed_functions[node.func.id](*args)

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


def safe_calculate(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return SafeCalculator().visit(tree)


@dataclass
class WorkspaceAccess:
    root: Path
    cowork_enabled: bool = False
    review_required: bool = True
    max_read_chars: int = 120_000
    max_write_chars: int = 240_000
    pending_changes: list[dict[str, Any]] = field(default_factory=list)

    blocked_names = {
        ".env",
        ".git",
        ".vs",
        ".venv",
        "__pycache__",
        "node_modules",
        "data",
    }

    blocked_suffixes = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".dll",
        ".exe",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".7z",
        ".tar",
        ".gz",
        ".db",
        ".sqlite",
    }

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

    def _resolve(self, relative_path: str) -> Path:
        if not relative_path.strip():
            raise ValueError("Path is required.")

        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Path must stay inside the workspace.")

        relative_parts = candidate.relative_to(self.root).parts
        for part in relative_parts:
            if part in self.blocked_names or part.startswith("GEMINI_API_KEY"):
                raise ValueError(f"Access to {part} is blocked.")
        if candidate.suffix.lower() in self.blocked_suffixes:
            raise ValueError(f"Access to {candidate.suffix} files is blocked.")
        return candidate

    def list_files(self, directory: str = ".", pattern: str = "*", limit: int = 80) -> list[dict[str, Any]]:
        folder = self._resolve(directory)
        if not folder.exists():
            return []
        if not folder.is_dir():
            raise ValueError("Path must be a directory.")

        safe_limit = max(1, min(int(limit), 200))
        results: list[dict[str, Any]] = []
        for path in sorted(folder.glob(pattern)):
            try:
                resolved = self._resolve(str(path.relative_to(self.root)))
            except ValueError:
                continue
            relative = resolved.relative_to(self.root).as_posix()
            results.append(
                {
                    "path": relative,
                    "type": "directory" if resolved.is_dir() else "file",
                    "size": resolved.stat().st_size if resolved.is_file() else None,
                }
            )
            if len(results) >= safe_limit:
                break
        return results

    def read_text_file(self, path: str) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.exists():
            return {"path": path, "error": "File does not exist."}
        if not target.is_file():
            return {"path": path, "error": "Path is not a file."}

        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > self.max_read_chars
        if truncated:
            text = text[: self.max_read_chars]
        return {"path": target.relative_to(self.root).as_posix(), "content": text, "truncated": truncated}

    def _next_change_id(self) -> str:
        highest = 0
        for change in self.pending_changes:
            change_id = str(change.get("id", ""))
            if change_id.startswith("change-"):
                try:
                    highest = max(highest, int(change_id.split("-", 1)[1]))
                except ValueError:
                    continue
        return f"change-{highest + 1}"

    def _read_existing_text(self, target: Path) -> str:
        if not target.exists() or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8", errors="replace")

    def _build_diff(self, path: str, old_text: str, new_text: str) -> str:
        diff = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        preview = "\n".join(list(diff)[:240])
        if not preview:
            return "(No text difference.)"
        return preview

    def _stage_change(self, action: str, path: str, content: str) -> dict[str, Any]:
        target = self._resolve(path)
        if len(content) > self.max_write_chars:
            raise ValueError("Content is too large for a single change.")

        relative = target.relative_to(self.root).as_posix()
        old_text = self._read_existing_text(target)
        new_text = content if action == "write" else old_text + content
        change = {
            "id": self._next_change_id(),
            "action": action,
            "path": relative,
            "content": content,
            "created": not target.exists(),
            "bytes": len(content.encode("utf-8")),
            "status": "pending",
            "created_at": utc_now_iso(),
            "diff": self._build_diff(relative, old_text, new_text),
        }
        self.pending_changes.append(change)
        return self._public_change(change)

    def _public_change(self, change: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in change.items() if key != "content"}

    def list_pending_changes(self) -> list[dict[str, Any]]:
        return [self._public_change(change) for change in self.pending_changes if change.get("status") == "pending"]

    def apply_change(self, change_id: str) -> dict[str, Any]:
        for change in self.pending_changes:
            if change.get("id") != change_id:
                continue
            if change.get("status") != "pending":
                return {"id": change_id, "error": "Change is not pending."}

            target = self._resolve(str(change["path"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            if change.get("action") == "append":
                with target.open("a", encoding="utf-8") as file:
                    file.write(str(change["content"]))
            else:
                target.write_text(str(change["content"]), encoding="utf-8")
            change["status"] = "applied"
            change["applied_at"] = utc_now_iso()
            return self._public_change(change)
        return {"id": change_id, "error": "Change was not found."}

    def reject_change(self, change_id: str) -> dict[str, Any]:
        for change in self.pending_changes:
            if change.get("id") == change_id:
                if change.get("status") != "pending":
                    return {"id": change_id, "error": "Change is not pending."}
                change["status"] = "rejected"
                change["rejected_at"] = utc_now_iso()
                return self._public_change(change)
        return {"id": change_id, "error": "Change was not found."}

    def write_text_file(self, path: str, content: str) -> dict[str, Any]:
        if not self.cowork_enabled:
            return {
                "path": path,
                "error": "Cowork mode is off. Ask the user to enable Cowork mode before changing files.",
            }
        if self.review_required:
            change = self._stage_change("write", path, content)
            change["status"] = "pending_review"
            return change
        target = self._resolve(path)
        if len(content) > self.max_write_chars:
            raise ValueError("Content is too large for a single write.")
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content, encoding="utf-8")
        return {
            "path": target.relative_to(self.root).as_posix(),
            "created": not existed,
            "bytes": target.stat().st_size,
        }

    def append_text_file(self, path: str, content: str) -> dict[str, Any]:
        if not self.cowork_enabled:
            return {
                "path": path,
                "error": "Cowork mode is off. Ask the user to enable Cowork mode before changing files.",
            }
        if self.review_required:
            change = self._stage_change("append", path, content)
            change["status"] = "pending_review"
            return change
        target = self._resolve(path)
        if len(content) > self.max_write_chars:
            raise ValueError("Content is too large for a single append.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as file:
            file.write(content)
        return {"path": target.relative_to(self.root).as_posix(), "bytes": target.stat().st_size}


@dataclass
class AssistantStore:
    path: Path
    timezone: str = DEFAULT_TIMEZONE

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._empty_state())

    def _empty_state(self) -> dict[str, Any]:
        return {
            "memory": [],
            "todos": [],
            "notes": [],
            "reminders": [],
        }

    def _read(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                state = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            state = self._empty_state()

        for key, default in self._empty_state().items():
            state.setdefault(key, default)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, ensure_ascii=False)
            file.write("\n")

    def _next_id(self, records: list[dict[str, Any]], prefix: str) -> str:
        highest = 0
        for record in records:
            record_id = str(record.get("id", ""))
            if record_id.startswith(prefix + "-"):
                try:
                    highest = max(highest, int(record_id.split("-", 1)[1]))
                except ValueError:
                    continue
        return f"{prefix}-{highest + 1}"

    def remember(self, key: str, value: str) -> dict[str, Any]:
        state = self._read()
        now = utc_now_iso()
        existing = next((item for item in state["memory"] if item["key"].lower() == key.lower()), None)
        if existing:
            existing.update({"key": key, "value": value, "updated_at": now})
            result = existing
        else:
            result = {"id": self._next_id(state["memory"], "mem"), "key": key, "value": value, "created_at": now}
            state["memory"].append(result)
        self._write(state)
        return result

    def recall(self, query: str = "") -> list[dict[str, Any]]:
        state = self._read()
        if not query.strip():
            return state["memory"]
        needle = query.lower()
        return [
            item
            for item in state["memory"]
            if needle in item.get("key", "").lower() or needle in item.get("value", "").lower()
        ]

    def add_todo(self, task: str, due: str = "", priority: str = "normal") -> dict[str, Any]:
        state = self._read()
        todo = {
            "id": self._next_id(state["todos"], "todo"),
            "task": task,
            "due": parse_datetime(due, self.timezone) if due else "",
            "priority": priority or "normal",
            "status": "open",
            "created_at": utc_now_iso(),
        }
        state["todos"].append(todo)
        self._write(state)
        return todo

    def list_todos(self, status: str = "open") -> list[dict[str, Any]]:
        state = self._read()
        if status == "all":
            return state["todos"]
        return [todo for todo in state["todos"] if todo.get("status") == status]

    def complete_todo(self, todo_id: str) -> dict[str, Any]:
        state = self._read()
        for todo in state["todos"]:
            if todo.get("id") == todo_id:
                todo["status"] = "done"
                todo["completed_at"] = utc_now_iso()
                self._write(state)
                return todo
        return {"error": f"No todo found with id {todo_id}."}

    def add_note(self, title: str, body: str) -> dict[str, Any]:
        state = self._read()
        note = {
            "id": self._next_id(state["notes"], "note"),
            "title": title,
            "body": body,
            "created_at": utc_now_iso(),
        }
        state["notes"].append(note)
        self._write(state)
        return note

    def search_notes(self, query: str = "") -> list[dict[str, Any]]:
        state = self._read()
        if not query.strip():
            return state["notes"][-10:]
        needle = query.lower()
        return [
            note
            for note in state["notes"]
            if needle in note.get("title", "").lower() or needle in note.get("body", "").lower()
        ]

    def set_reminder(self, text: str, remind_at: str) -> dict[str, Any]:
        state = self._read()
        reminder = {
            "id": self._next_id(state["reminders"], "rem"),
            "text": text,
            "remind_at": parse_datetime(remind_at, self.timezone),
            "status": "open",
            "created_at": utc_now_iso(),
        }
        state["reminders"].append(reminder)
        self._write(state)
        return reminder

    def list_reminders(self, status: str = "open") -> list[dict[str, Any]]:
        state = self._read()
        if status == "all":
            return state["reminders"]
        return [reminder for reminder in state["reminders"] if reminder.get("status") == status]


class MosesAgent:
    def __init__(
        self,
        store: AssistantStore,
        model: str,
        system_instruction: str,
        workspace: WorkspaceAccess | None = None,
    ) -> None:
        # Initialize agent state. Gemini (google-genai) is optional — if it's
        # available and configured it will be used; otherwise the agent can
        # still route requests to local `gptoss` or `ollama_api` backends.
        self.store = store
        self.model = model
        self.system_instruction = system_instruction
        self.workspace = workspace or WorkspaceAccess(Path.cwd())
        self.client = None
        self.chat = None
        self.gemini_ready = False

        if genai is not None and types is not None:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    self.client = genai.Client(api_key=api_key)
                    self.chat = self.client.chats.create(
                        model=model,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=self._tools(),
                            temperature=0.4,
                        ),
                    )
                    self.gemini_ready = True
                except Exception:
                    self.client = None
                    self.chat = None
                    self.gemini_ready = False

    def _tools(self) -> list[Any]:
        store = self.store
        workspace = self.workspace

        def get_current_datetime() -> dict[str, str]:
            """Return the current date and time for the user's configured timezone."""
            effective_timezone = resolve_timezone(store.timezone)
            now = datetime.now(effective_timezone)
            return {"timezone": store.timezone, "datetime": now.isoformat()}

        def remember_preference(key: str, value: str) -> dict[str, Any]:
            """Store an important user preference or durable fact for future conversations."""
            return store.remember(key, value)

        def recall_memory(query: str = "") -> list[dict[str, Any]]:
            """Retrieve stored memory. Use an empty query to retrieve all remembered facts."""
            return store.recall(query)

        def add_todo(task: str, due: str = "", priority: str = "normal") -> dict[str, Any]:
            """Create a todo item. The due field can be ISO datetime or plain natural text."""
            return store.add_todo(task, due, priority)

        def list_todos(status: str = "open") -> list[dict[str, Any]]:
            """List todos by status. Status can be open, done, or all."""
            return store.list_todos(status)

        def complete_todo(todo_id: str) -> dict[str, Any]:
            """Mark a todo item as done by its id, such as todo-1."""
            return store.complete_todo(todo_id)

        def add_note(title: str, body: str) -> dict[str, Any]:
            """Create a note for ideas, plans, personal records, or useful information."""
            return store.add_note(title, body)

        def search_notes(query: str = "") -> list[dict[str, Any]]:
            """Search saved notes. Use an empty query to return recent notes."""
            return store.search_notes(query)

        def set_reminder(text: str, remind_at: str) -> dict[str, Any]:
            """Store a reminder record. This does not create an operating system notification."""
            return store.set_reminder(text, remind_at)

        def list_reminders(status: str = "open") -> list[dict[str, Any]]:
            """List reminders by status. Status can be open or all."""
            return store.list_reminders(status)

        def calculate(expression: str) -> dict[str, Any]:
            """Safely calculate a math expression using numbers, operators, and basic math functions."""
            try:
                return {"expression": expression, "result": safe_calculate(expression)}
            except Exception as exc:
                return {"expression": expression, "error": str(exc)}

        def call_gptoss(prompt: str, model: str = "", stream: bool = False) -> dict[str, Any]:
            """Generate text using the local GPToss backend (groq wrapper).

            Returns a dict with either `text` or `error` keys.
            """
            try:
                import gptoss
            except Exception as exc:  # pragma: no cover - runtime import may fail on systems without groq
                return {"error": f"gptoss import failed: {exc}"}
            try:
                if stream:
                    return {"error": "Streaming not supported via MOSES tool."}
                result = gptoss.generate(prompt, model=model or None, stream=False)
                return {"text": result}
            except Exception as exc:
                return {"error": str(exc)}

        def call_ollama(prompt: str, model: str = "", stream: bool = False) -> dict[str, Any]:
            """Generate text using the local Ollama backend (groq wrapper).

            Returns a dict with either `text` or `error` keys.
            """
            try:
                import ollama_api as ollama
            except Exception as exc:  # pragma: no cover - runtime import may fail on systems without groq
                return {"error": f"ollama import failed: {exc}"}
            try:
                if stream:
                    return {"error": "Streaming not supported via MOSES tool."}
                result = ollama.generate(prompt, model=model or None, stream=False)
                return {"text": result}
            except Exception as exc:
                return {"error": str(exc)}

        def list_workspace_files(directory: str = ".", pattern: str = "*", limit: int = 80) -> list[dict[str, Any]]:
            """List safe files and folders inside the workspace."""
            return workspace.list_files(directory, pattern, limit)

        def read_workspace_file(path: str) -> dict[str, Any]:
            """Read a UTF-8 text file inside the workspace."""
            return workspace.read_text_file(path)

        def write_workspace_file(path: str, content: str) -> dict[str, Any]:
            """Create or overwrite a UTF-8 text file inside the workspace."""
            return workspace.write_text_file(path, content)

        def append_workspace_file(path: str, content: str) -> dict[str, Any]:
            """Append UTF-8 text to a file inside the workspace."""
            return workspace.append_text_file(path, content)

        def list_pending_workspace_changes() -> list[dict[str, Any]]:
            """List workspace file changes staged for user review."""
            return workspace.list_pending_changes()

        tools_list = [
            get_current_datetime,
            remember_preference,
            recall_memory,
            add_todo,
            list_todos,
            complete_todo,
            add_note,
            search_notes,
            set_reminder,
            list_reminders,
            calculate,
            call_gptoss,
            call_ollama,
            list_workspace_files,
            read_workspace_file,
            write_workspace_file,
            append_workspace_file,
            list_pending_workspace_changes,
        ]

        notion_api_key = os.getenv("NOTION_API_KEY")
        if notion_api_key:
            try:
                from notion_client import Client as _NotionClient
                _notion = _NotionClient(auth=notion_api_key)

                # ── helpers ──────────────────────────────────────────────
                def _rich(text: str) -> list[dict]:
                    return [{"type": "text", "text": {"content": text}}]

                def _para(text: str) -> dict:
                    return {"object": "block", "type": "paragraph",
                            "paragraph": {"rich_text": _rich(text)}}

                def _h2(text: str) -> dict:
                    return {"object": "block", "type": "heading_2",
                            "heading_2": {"rich_text": _rich(text)}}

                def _bullet(text: str) -> dict:
                    return {"object": "block", "type": "bulleted_list_item",
                            "bulleted_list_item": {"rich_text": _rich(text)}}

                def _page_title(page: dict) -> str:
                    props = page.get("properties", {})
                    for v in props.values():
                        if v.get("type") == "title":
                            parts = v.get("title", [])
                            return "".join(p.get("plain_text", "") for p in parts)
                    return page.get("id", "?")

                # ── 1. Enterprise Search ─────────────────────────────────
                def notion_enterprise_search(query: str, filter_type: str = "") -> dict[str, Any]:
                    """Enterprise-wide full-text search across all shared Notion pages and databases.
                    filter_type can be 'page', 'database', or empty for all."""
                    try:
                        params: dict[str, Any] = {"query": query, "page_size": 20}
                        if filter_type in ("page", "database"):
                            params["filter"] = {"value": filter_type, "property": "object"}
                        results = _notion.search(**params).get("results", [])
                        out = []
                        for res in results:
                            obj_type = res.get("object", "")
                            entry: dict[str, Any] = {
                                "id": res.get("id"),
                                "type": obj_type,
                                "url": res.get("url"),
                            }
                            if obj_type == "page":
                                entry["title"] = _page_title(res)
                                entry["last_edited"] = res.get("last_edited_time", "")
                                entry["created"] = res.get("created_time", "")
                                entry["archived"] = res.get("archived", False)
                            elif obj_type == "database":
                                title_arr = res.get("title", [])
                                entry["title"] = "".join(t.get("plain_text", "") for t in title_arr)
                            out.append(entry)
                        return {"query": query, "count": len(out), "results": out}
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 2. Get / Verify any page ─────────────────────────────
                def notion_get_page(page_id: str) -> dict[str, Any]:
                    """Retrieve and verify metadata for any Notion page by its ID or URL.
                    Strips dashes from IDs automatically."""
                    try:
                        pid = page_id.strip().rstrip("/").split("/")[-1].split("?")[0]
                        pid = pid.replace("-", "")
                        if len(pid) == 32:
                            pid = f"{pid[:8]}-{pid[8:12]}-{pid[12:16]}-{pid[16:20]}-{pid[20:]}"
                        page = _notion.pages.retrieve(page_id=pid)
                        blocks = _notion.blocks.children.list(block_id=pid, page_size=30).get("results", [])
                        text_blocks = []
                        for b in blocks:
                            btype = b.get("type", "")
                            rtarr = b.get(btype, {}).get("rich_text", [])
                            line = "".join(r.get("plain_text", "") for r in rtarr)
                            if line:
                                text_blocks.append({"type": btype, "text": line})
                        return {
                            "id": page.get("id"),
                            "url": page.get("url"),
                            "title": _page_title(page),
                            "archived": page.get("archived", False),
                            "created": page.get("created_time"),
                            "last_edited": page.get("last_edited_time"),
                            "content_preview": text_blocks[:20],
                        }
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 3. Create page (supports parent page OR database) ────
                def notion_create_page(parent_id: str, title: str, content: str,
                                       parent_type: str = "page_id") -> dict[str, Any]:
                    """Create a new Notion page.
                    parent_type: 'page_id' for a sub-page, 'database_id' for a database row."""
                    try:
                        parent = {parent_type: parent_id}
                        if parent_type == "database_id":
                            props = {"Name": {"title": _rich(title)}}
                        else:
                            props = {"title": _rich(title)}
                        new_page = _notion.pages.create(
                            parent=parent,
                            properties=props,
                            children=[_h2(title), _para(content)],
                        )
                        return {"id": new_page.get("id"), "url": new_page.get("url"), "title": title}
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 4. Append rich content ───────────────────────────────
                def notion_append_content(page_id: str, content: str,
                                          block_type: str = "paragraph") -> dict[str, Any]:
                    """Append a block to a Notion page.
                    block_type: 'paragraph', 'heading_2', 'bulleted_list_item', 'quote', 'divider'."""
                    try:
                        if block_type == "divider":
                            block: dict = {"object": "block", "type": "divider", "divider": {}}
                        elif block_type == "heading_2":
                            block = _h2(content)
                        elif block_type == "bulleted_list_item":
                            block = _bullet(content)
                        elif block_type == "quote":
                            block = {"object": "block", "type": "quote",
                                     "quote": {"rich_text": _rich(content)}}
                        else:
                            block = _para(content)
                        _notion.blocks.children.append(block_id=page_id, children=[block])
                        return {"status": "ok", "page_id": page_id, "block_type": block_type}
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 5. AI Meeting Notes ──────────────────────────────────
                def notion_create_meeting_notes(parent_page_id: str, meeting_title: str,
                                                attendees: str, agenda: str,
                                                notes: str, action_items: str) -> dict[str, Any]:
                    """Create a structured AI-formatted meeting notes page in Notion.
                    attendees, agenda, notes, action_items are newline-separated strings."""
                    try:
                        from datetime import datetime as _dt
                        date_str = _dt.now().strftime("%Y-%m-%d %H:%M")
                        full_title = f"Meeting: {meeting_title} — {date_str}"

                        children: list[dict] = [
                            _h2("📋 Meeting Details"),
                            _bullet(f"Date: {date_str}"),
                            _bullet(f"Attendees: {attendees}"),
                            {"object": "block", "type": "divider", "divider": {}},
                            _h2("📌 Agenda"),
                        ]
                        for item in agenda.split("\n"):
                            if item.strip():
                                children.append(_bullet(item.strip()))
                        children.append({"object": "block", "type": "divider", "divider": {}})
                        children.append(_h2("📝 Notes"))
                        for line in notes.split("\n"):
                            if line.strip():
                                children.append(_para(line.strip()))
                        children.append({"object": "block", "type": "divider", "divider": {}})
                        children.append(_h2("✅ Action Items"))
                        for item in action_items.split("\n"):
                            if item.strip():
                                children.append({
                                    "object": "block", "type": "to_do",
                                    "to_do": {"rich_text": _rich(item.strip()), "checked": False}
                                })

                        new_page = _notion.pages.create(
                            parent={"page_id": parent_page_id},
                            properties={"title": _rich(full_title)},
                            children=children,
                        )
                        return {"id": new_page.get("id"), "url": new_page.get("url"), "title": full_title}
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 6. Database operations (granular permissions) ────────
                def notion_query_database(database_id: str, filter_property: str = "",
                                          filter_value: str = "", limit: int = 20) -> dict[str, Any]:
                    """Query a Notion database with optional property filter.
                    Supports granular access: only returns fields the integration can read."""
                    try:
                        params: dict[str, Any] = {"database_id": database_id, "page_size": min(limit, 100)}
                        if filter_property and filter_value:
                            params["filter"] = {
                                "property": filter_property,
                                "rich_text": {"contains": filter_value}
                            }
                        resp = _notion.databases.query(**params)
                        rows = []
                        for row in resp.get("results", []):
                            entry: dict[str, Any] = {"id": row.get("id"), "url": row.get("url"), "properties": {}}
                            for pname, pval in row.get("properties", {}).items():
                                ptype = pval.get("type", "")
                                if ptype == "title":
                                    entry["properties"][pname] = "".join(
                                        t.get("plain_text", "") for t in pval.get("title", []))
                                elif ptype == "rich_text":
                                    entry["properties"][pname] = "".join(
                                        t.get("plain_text", "") for t in pval.get("rich_text", []))
                                elif ptype == "select":
                                    sel = pval.get("select")
                                    entry["properties"][pname] = sel.get("name", "") if sel else ""
                                elif ptype == "multi_select":
                                    entry["properties"][pname] = [s.get("name") for s in pval.get("multi_select", [])]
                                elif ptype in ("number", "checkbox", "url", "email", "phone_number"):
                                    entry["properties"][pname] = pval.get(ptype)
                                elif ptype == "date":
                                    d = pval.get("date")
                                    entry["properties"][pname] = d.get("start") if d else ""
                                elif ptype == "status":
                                    s = pval.get("status")
                                    entry["properties"][pname] = s.get("name") if s else ""
                            rows.append(entry)
                        return {"database_id": database_id, "count": len(rows), "rows": rows}
                    except Exception as exc:
                        return {"error": str(exc)}

                def notion_add_database_row(database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
                    """Add a new row to a Notion database.
                    properties is a dict of {property_name: value}. Handles title/text/number/checkbox/select/date."""
                    try:
                        props: dict[str, Any] = {}
                        for k, v in properties.items():
                            if isinstance(v, bool):
                                props[k] = {"checkbox": v}
                            elif isinstance(v, (int, float)):
                                props[k] = {"number": v}
                            elif k.lower() in ("name", "title"):
                                props[k] = {"title": _rich(str(v))}
                            else:
                                props[k] = {"rich_text": _rich(str(v))}
                        new_row = _notion.pages.create(
                            parent={"database_id": database_id},
                            properties=props,
                        )
                        return {"id": new_row.get("id"), "url": new_row.get("url")}
                    except Exception as exc:
                        return {"error": str(exc)}

                def notion_update_page_property(page_id: str, property_name: str,
                                                 value: str) -> dict[str, Any]:
                    """Update a single text/title property on a Notion page or database row."""
                    try:
                        updated = _notion.pages.update(
                            page_id=page_id,
                            properties={property_name: {"rich_text": _rich(value)}}
                        )
                        return {"id": updated.get("id"), "url": updated.get("url"), "status": "updated"}
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 7. Private teamspace / workspace info ────────────────
                def notion_list_shared_pages(limit: int = 30) -> dict[str, Any]:
                    """List all pages and databases shared with this integration (respects private teamspaces)."""
                    try:
                        results = _notion.search(query="", page_size=min(limit, 100)).get("results", [])
                        pages = []
                        dbs = []
                        for res in results:
                            obj = res.get("object")
                            if obj == "page":
                                pages.append({"id": res.get("id"), "title": _page_title(res),
                                              "url": res.get("url"), "last_edited": res.get("last_edited_time")})
                            elif obj == "database":
                                t = "".join(x.get("plain_text", "") for x in res.get("title", []))
                                dbs.append({"id": res.get("id"), "title": t, "url": res.get("url")})
                        return {
                            "note": "Only content explicitly shared with this integration is visible (private teamspaces are excluded unless shared).",
                            "page_count": len(pages),
                            "database_count": len(dbs),
                            "pages": pages,
                            "databases": dbs,
                        }
                    except Exception as exc:
                        return {"error": str(exc)}

                # ── 8. Notion Agent ──────────────────────────────────────
                def notion_agent_run(task: str) -> dict[str, Any]:
                    """Run a high-level Notion task using MOSES as a Notion agent.
                    Examples: 'create a meeting notes page', 'search for project docs', 'add a todo to my task DB'.
                    MOSES will interpret the task and call the appropriate Notion tools."""
                    return {
                        "agent_mode": True,
                        "task": task,
                        "instruction": (
                            "You are acting as a Notion Agent. Use the available Notion tools "
                            "(notion_enterprise_search, notion_create_page, notion_append_content, "
                            "notion_create_meeting_notes, notion_query_database, notion_add_database_row, "
                            "notion_get_page, notion_list_shared_pages) to fulfill this task: " + task
                        ),
                    }

                tools_list.extend([
                    notion_enterprise_search,
                    notion_get_page,
                    notion_create_page,
                    notion_append_content,
                    notion_create_meeting_notes,
                    notion_query_database,
                    notion_add_database_row,
                    notion_update_page_property,
                    notion_list_shared_pages,
                    notion_agent_run,
                ])
            except ImportError:
                pass

        return tools_list
    def _call_gptoss(self, prompt: str, model: str | None = None, stream: bool = False):
        try:
            import gptoss
        except Exception as exc:  # pragma: no cover - runtime import may fail
            raise RuntimeError(f"gptoss import failed: {exc}")
        return gptoss.generate(prompt, model=model or None, stream=stream)

    def _call_ollama(self, prompt: str, model: str | None = None, stream: bool = False):
        try:
            import ollama_api as ollama
        except Exception as exc:  # pragma: no cover - runtime import may fail
            raise RuntimeError(f"ollama import failed: {exc}")
        return ollama.generate(prompt, model=model or None, stream=stream)

    def ask(self, message: str, backend: str = "gemini") -> str:
        cowork_state = "ON" if self.workspace.cowork_enabled else "OFF"
        review_state = "staged review" if self.workspace.review_required else "direct apply"
        backend_key = (backend or "gemini").lower()

        if backend_key == "gemini":
            if not self.gemini_ready or self.chat is None:
                raise RuntimeError(
                    "Gemini backend is not configured. Set GEMINI_API_KEY and install google-genai to use Gemini."
                )
            response = self.chat.send_message(
                f"Cowork mode is {cowork_state}. Workspace changes use {review_state}.\n\nUser request:\n{message}"
            )
            return response.text or "(MOSES completed the action, but did not return text.)"

        if backend_key in {"gptoss", "groq"}:
            try:
                result = self._call_gptoss(message, model=self.model, stream=False)
                return result if isinstance(result, str) else str(result)
            except Exception as exc:
                return f"gptoss error: {exc}"

        if backend_key in {"ollama", "ollama_api"}:
            try:
                result = self._call_ollama(message, model=self.model, stream=False)
                return result if isinstance(result, str) else str(result)
            except Exception as exc:
                return f"ollama error: {exc}"

        return f"Unknown backend: {backend}"

    def ask_with_image(self, message: str, image_bytes: bytes, mime_type: str, backend: str = "gemini") -> str:
        vision_prompt = (
            f"{message}\n\n"
            "Analyze the attached image directly. If the user is asking for a project or file change, "
            "describe the concrete visual context and the change that appears necessary."
        )

        if (backend or "gemini").lower() != "gemini":
            return "Vision is only supported with the Gemini backend."

        if not self.gemini_ready or self.client is None:
            raise RuntimeError("Gemini backend is not configured for vision support.")

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                vision_prompt,
            ],
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.35,
            ),
        )
        visual_context = response.text or "(MOSES analyzed the image, but did not return text.)"

        action_words = ("add", "append", "build", "change", "create", "edit", "fix", "make", "update", "write")
        if any(word in message.lower() for word in action_words):
            return self.ask(
                "The user gave this vision-based command:\n"
                f"{message}\n\n"
                "Visual context from the current camera/screen snapshot:\n"
                f"{visual_context}\n\n"
                "Use workspace tools if a project file change is needed and Cowork mode is on. "
                "Confirm exactly what you changed."
            )
        return visual_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MOSES, an agentic personal assistant powered by Gemini.")
    parser.add_argument("prompt", nargs="*", help="Optional one-shot prompt. Omit it for interactive chat.")
    parser.add_argument("--model", default=os.getenv("MOSES_MODEL", DEFAULT_MODEL), help="Gemini model name.")
    parser.add_argument("--timezone", default=os.getenv("MOSES_TIMEZONE", DEFAULT_TIMEZONE), help="IANA timezone.")
    parser.add_argument(
        "--data-file",
        default=os.getenv("MOSES_DATA_FILE", str(Path("data") / "moses_state.json")),
        help="Path to the local JSON memory store.",
    )
    parser.add_argument("--system", default="", help="Extra system instruction appended to MOSES's default behavior.")
    parser.add_argument(
        "--workspace",
        default=os.getenv("MOSES_WORKSPACE", str(Path.cwd())),
        help="Directory MOSES can read and edit with workspace tools.",
    )
    parser.add_argument(
        "--cowork",
        action="store_true",
        help="Start with Cowork mode enabled, allowing safe workspace file changes.",
    )
    return parser


def print_setup_error(error: Exception) -> None:
    print(f"MOSES setup error: {error}")
    print()
    print("Quick setup:")
    print("  1. python -m pip install -r requirements.txt")
    print("  2. Create .env with: GEMINI_API_KEY=your_api_key_here")
    print("  3. (Optional) Add NOTION_API_KEY=your_notion_secret to use Notion tools")
    print("  4. Run: python moses.py")


def print_runtime_error(error: Exception) -> None:
    print(f"MOSES request error: {error}")
    print("Please retry in a moment, or verify your Gemini quota and model settings.")


def main() -> int:
    args = build_parser().parse_args()

    if load_dotenv is None:
        print_setup_error(RuntimeError("python-dotenv is not installed."))
        return 1

    load_dotenv()
    store = AssistantStore(Path(args.data_file), timezone=args.timezone)
    system_instruction = SYSTEM_INSTRUCTION
    if args.system.strip():
        system_instruction += "\n\nAdditional instruction:\n" + args.system.strip()

    try:
        agent = MosesAgent(
            store=store,
            model=args.model,
            system_instruction=system_instruction,
            workspace=WorkspaceAccess(Path(args.workspace), cowork_enabled=args.cowork),
        )
    except Exception as exc:
        print_setup_error(exc)
        return 1

    if args.prompt:
        try:
            print(agent.ask(" ".join(args.prompt)))
            return 0
        except Exception as exc:
            print_runtime_error(exc)
            return 1

    print("--- MOSES personal assistant is ready ---")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("Try: remember that I prefer short answers, add a todo, or list my reminders.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except KeyboardInterrupt:
            print("\nMOSES: Farewell. I will keep your memory safe locally.")
            return 0

        if user_input.lower() in {"exit", "quit"}:
            print("MOSES: Farewell. I will keep your memory safe locally.")
            return 0
        if not user_input:
            continue

        try:
            print(f"MOSES: {agent.ask(user_input)}")
        except Exception as exc:
            print(f"MOSES error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
