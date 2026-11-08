"""Offline integration suite: isolated SQLite, real MCP HTTP, deterministic model.

No local .env credentials, external model APIs, or existing databases are used.
Run: python -m unittest discover -s tests -v
"""
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

TEMP = tempfile.TemporaryDirectory(prefix="campus-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(TEMP.name) / "test.sqlite3").as_posix()
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-with-at-least-thirty-two-bytes"
os.environ["LLM_API_KEY"] = ""
os.environ["EMBEDDING_API_KEY"] = ""

from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from pydantic import PrivateAttr
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_mcp_adapters.client import MultiServerMCPClient
from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.utils.mcp_auth import create_tool_token, decode_tool_token
from app.models.campus import ChatSession, Course, Document
from app.models.user import User
from app.models.schedule import Schedule
from app.models.study_plan import StudyPlan
from app.models.kb_document import KBDocument
from app.services import chat_service, rag_service
from app.utils.jwt import create_access_token
from app.utils.password import hash_password


class ScriptedCourseModel(BaseChatModel):
    """Exercises the actual create_agent -> MCP -> tools loop without paid calls."""

    @property
    def _llm_type(self):
        return "offline-course-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        calls = [
            ("get_my_schedules", {}),
            ("list_study_plans", {}),
            ("save_study_plan", {"title": "数学复习", "content": "每天练习 30 分钟", "target_date": "2026-11-01"}),
        ]
        if len(tool_messages) < len(calls):
            name, args = calls[len(tool_messages)]
            response = AIMessage(content="", tool_calls=[{"id": f"call-{len(tool_messages)}", "name": name, "args": args}])
        else:
            response = AIMessage(content="已查询课表，并保存数学复习计划。")
        return ChatResult(generations=[ChatGeneration(message=response)])


class ScheduleDialogueModel(BaseChatModel):
    """Deterministic model; the real Agent must fetch real MCP schedule results."""
    _seen: list = PrivateAttr(default_factory=list)
    _tools: list = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self):
        return "offline-schedule-dialogue"

    def bind_tools(self, tools, **kwargs):
        self._tools = [tool.name for tool in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from app.services.agent_service import tool_payload
        self._seen.append(list(messages))
        if not isinstance(messages[-1], ToolMessage):
            response = AIMessage(content="", tool_calls=[{
                "id": "schedule-query", "name": "get_my_schedules", "args": {},
            }])
        else:
            rows = tool_payload(messages[-1])["schedules"]
            answer = "；".join(f'{row["name"]}，{row["teacher"]}，{row["location"]}' for row in rows)
            response = AIMessage(content=answer or "没有符合条件的排课")
        return ChatResult(generations=[ChatGeneration(message=response)])


class StreamingScheduleModel(ScheduleDialogueModel):
    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        message = self._generate(messages, stop, run_manager, **kwargs).generations[0].message
        if message.tool_calls:
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[
                {"name": call["name"], "args": json.dumps(call["args"]), "id": call["id"], "index": index}
                for index, call in enumerate(message.tool_calls)
            ]))
        else:
            for offset in range(0, len(message.content), 4):
                yield ChatGenerationChunk(message=AIMessageChunk(content=message.content[offset:offset + 4]))


class CampusIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        environment = {**os.environ, "MCP_PORT": str(port)}
        cls.mcp_url = f"http://127.0.0.1:{port}/mcp"
        cls.log = open(Path(TEMP.name) / "mcp.log", "w", encoding="utf-8")
        cls.process = subprocess.Popen(
            [sys.executable, "-m", "app.mcp_server"], env=environment,
            stdout=cls.log, stderr=cls.log,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        import httpx
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                if httpx.get(cls.mcp_url, timeout=1).status_code == 401:
                    return
            except httpx.HTTPError:
                pass
            if cls.process.poll() is not None:
                break
            time.sleep(0.1)
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.log.close()
        raise RuntimeError((Path(TEMP.name) / "mcp.log").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.log.close()
        cls.context.__exit__(None, None, None)
        engine.dispose()

    def setUp(self):
        with SessionLocal() as db:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.add_all([
                User(id=1, username="alice", password=hash_password("alice123"), name="Alice", role="student", status=1),
                User(id=2, username="bob", password=hash_password("bob123"), name="Bob", role="student", status=1),
                User(id=3, username="admin", password=hash_password("admin123"), name="管理员", role="admin", status=1),
            ])
            db.commit()
        self.alice = {"Authorization": f"Bearer {create_access_token(1)}"}
        self.bob = {"Authorization": f"Bearer {create_access_token(2)}"}
        self.admin = {"Authorization": f"Bearer {create_access_token(3)}"}
        self.course_data = {"name": "高等数学", "teacher": "张老师", "location": "教学楼 A101",
            "weekday": 4, "start_time": "08:00:00", "end_time": "09:40:00",
            "start_date": "2026-09-01", "end_date": "2027-01-15", "notes": ""}

    def create_course(self, user_id=1):
        response = self.client.post("/api/admin/courses", headers=self.admin, json={**self.course_data, "user_id": user_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def create_schedule(self, course_id, student_id=1, **overrides):
        fields = ("weekday", "start_time", "end_time", "start_date", "end_date", "location", "notes")
        data = {key: self.course_data[key] for key in fields}
        data.update(course_id=course_id, student_id=student_id, **overrides)
        response = self.client.post("/api/admin/schedules", headers=self.admin, json=data)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def test_existing_login_and_registration(self):
        response = self.client.post("/api/auth/login", json={"username": "alice", "password": "alice123"})
        self.assertEqual(response.json()["code"], 200)
        self.assertIn("token", response.json()["data"])
        response = self.client.post("/api/auth/register", json={"username": "new-student", "password": "123456"})
        self.assertEqual(response.json()["code"], 200)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(User).where(User.username == "new-student")).role, "student")

    def test_admin_user_creation_and_deletion_with_campus_data(self):
        from app.schemas.user import UserCreateRequest
        from app.services import user_service
        from app.common.exceptions import BusinessException

        self.create_course()
        with SessionLocal() as db:
            admin = db.get(User, 3)
            created = user_service.create_user(db, UserCreateRequest(username="new-user"))
            self.assertEqual(created.name, "new-user")
            with self.assertRaises(BusinessException) as caught:
                user_service.delete_user(db, 1, admin)
            self.assertEqual(caught.exception.code, 409)
            user_service.delete_user(db, created.id, admin)
            self.assertIsNone(db.get(User, created.id))

    def test_document_parsers_and_size_limits(self):
        from io import BytesIO
        from docx import Document as DocxDocument
        from fastapi import HTTPException

        self.assertEqual(rag_service.extract_text("notes.txt", b"\xef\xbb\xbfhello"), "hello")
        document = DocxDocument()
        document.add_paragraph("课程大纲")
        document.add_table(rows=1, cols=1).cell(0, 0).text = "考核方式"
        output = BytesIO()
        document.save(output)
        extracted = rag_service.extract_text("outline.docx", output.getvalue())
        self.assertIn("课程大纲", extracted)
        self.assertIn("考核方式", extracted)
        for data in (b"x" * (rag_service.MAX_DOCUMENT_SIZE + 1), "字".encode() * 21000):
            with self.assertRaises(HTTPException):
                rag_service.extract_text("large.txt", data)

    def test_courses_isolated_and_filtered_by_date(self):
        course = self.create_course()
        self.create_schedule(course["id"])
        self.assertEqual(len(self.client.get("/api/courses", headers=self.alice).json()["data"]), 1)
        self.assertEqual(self.client.get("/api/courses", headers=self.bob).json()["data"], [])
        self.assertEqual(len(self.client.get("/api/courses?on_date=2026-10-22", headers=self.alice).json()["data"]), 1)
        for date in ("2026-10-23", "2027-10-21"):
            self.assertEqual(self.client.get(f"/api/courses?on_date={date}", headers=self.alice).json()["data"], [])

    def test_students_cannot_mutate_courses_through_legacy_endpoints(self):
        course = self.create_course()
        path = f'/api/courses/{course["id"]}'
        for headers in (self.alice, self.bob):
            self.assertEqual(self.client.post("/api/courses", headers=headers, json=self.course_data).status_code, 403)
            self.assertEqual(self.client.put(path, headers=headers, json=self.course_data).status_code, 403)
            self.assertEqual(self.client.delete(path, headers=headers).status_code, 403)
        self.assertEqual(len(self.client.get("/api/courses", headers=self.alice).json()["data"]), 1)

    def test_invalid_schedule_rejected(self):
        for change in ({"weekday": 8}, {"end_time": "07:00:00"}, {"end_date": "2026-01-01"}, {"name": " "}, {"start_time": "08:00:00+08:00"}):
            self.assertEqual(self.client.post("/api/admin/courses", headers=self.admin, json={**self.course_data, "user_id": 1, **change}).status_code, 422)

    def test_auth_required_for_new_endpoints(self):
        for path in ("/api/courses", "/api/documents", "/api/plans", "/api/chat/sessions"):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_plans_isolation_status_and_delete(self):
        plan = self.client.post("/api/plans", headers=self.alice, json={"title": "复习", "content": "# 数学\n每天练习"}).json()["data"]
        self.assertEqual(self.client.get("/api/plans", headers=self.bob).json()["data"], [])
        path = f'/api/plans/{plan["id"]}'
        self.assertEqual(self.client.patch(path, headers=self.bob, json={"status": "completed"}).status_code, 404)
        self.assertEqual(self.client.patch(path, headers=self.alice, json={"status": "invalid"}).status_code, 422)
        self.assertEqual(self.client.patch(path, headers=self.alice, json={"status": "completed"}).status_code, 200)
        self.assertEqual(self.client.delete(path, headers=self.bob).status_code, 404)
        self.assertEqual(self.client.delete(path, headers=self.alice).status_code, 200)

    def test_study_plans_pagination_orders_by_creation_time_then_id(self):
        from datetime import datetime
        ids = []
        for title in ("新时间低ID", "新时间高ID", "旧时间高ID"):
            row = self.client.post("/api/study-plans", headers=self.alice,
                json={"title": title, "content": "每天练习"}).json()["data"]
            ids.append(row["id"])
        self.client.post("/api/study-plans", headers=self.bob, json={"title": "Bob", "content": "private"})
        with SessionLocal() as db:
            for index, plan_id in enumerate(ids):
                db.get(StudyPlan, plan_id).create_time = datetime(2026, 10, 22 if index == 2 else 23, 12)
            db.commit()
        first = self.client.get("/api/study-plans?page=1&page_size=2", headers=self.alice).json()["data"]
        second = self.client.get("/api/study-plans?page=2&page_size=2", headers=self.alice).json()["data"]
        self.assertEqual(first["total"], 3)
        self.assertEqual([row["id"] for row in first["list"]], [ids[1], ids[0]])
        self.assertEqual([row["id"] for row in second["list"]], [ids[2]])
        self.assertIn("create_time", first["list"][0])
        self.assertEqual(self.client.get("/api/study-plans?page=3&page_size=2", headers=self.alice).json()["data"]["list"], [])

    def test_study_plan_owner_comes_only_from_jwt_even_for_admin(self):
        response = self.client.post("/api/study-plans", headers=self.alice,
            json={"user_id": 2, "title": "  我的计划  ", "content": "    保留 Markdown 缩进", "status": "completed"})
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()["data"]
        self.assertEqual(row["title"], "我的计划")
        self.assertEqual(row["content"], "    保留 Markdown 缩进")
        self.assertEqual(row["status"], "pending")
        with SessionLocal() as db:
            self.assertEqual(db.get(StudyPlan, row["id"]).user_id, 1)
        for headers in (self.bob, self.admin):
            data = self.client.get("/api/study-plans?user_id=1", headers=headers).json()["data"]
            self.assertEqual(data, {"list": [], "total": 0})
            self.assertEqual(self.client.delete(f'/api/study-plans/{row["id"]}', headers=headers).status_code, 404)
            self.assertEqual(self.client.patch(f'/api/study-plans/{row["id"]}', headers=headers, json={"status": "completed"}).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/study-plans/{row["id"]}', headers=self.alice).status_code, 200)
        self.assertEqual(self.client.get("/api/study-plans", headers=self.alice).json()["data"]["total"], 0)
        self.assertEqual(self.client.delete(f'/api/study-plans/{row["id"]}', headers=self.alice).status_code, 404)

    def test_study_plan_auth_and_input_validation(self):
        for method, path, data in (("GET", "/api/study-plans", None),
            ("POST", "/api/study-plans", {"title": "计划", "content": "复习"}),
            ("DELETE", "/api/study-plans/1", None),
            ("PATCH", "/api/study-plans/1", {"status": "completed"})):
            self.assertEqual(self.client.request(method, path, json=data).status_code, 401)
        for data in ({"title": " ", "content": "x"}, {"title": "x", "content": "\n\t"},
            {"title": "x" * 121, "content": "x"}, {"title": "x", "content": "x" * 10001},
            {"title": "x", "content": "x", "target_date": "invalid"}):
            self.assertEqual(self.client.post("/api/study-plans", headers=self.alice, json=data).status_code, 422)
        for query in ("page=0", "page=-1", "page_size=0", "page_size=101", "status=invalid"):
            self.assertEqual(self.client.get(f"/api/study-plans?{query}", headers=self.alice).status_code, 422)

    def test_study_plan_pending_filter_reports_full_count(self):
        for index in range(6):
            self.client.post("/api/study-plans", headers=self.alice, json={"title": f"计划{index}", "content": "复习"})
        row = self.client.get("/api/study-plans", headers=self.alice).json()["data"]["list"][0]
        self.client.patch(f'/api/study-plans/{row["id"]}', headers=self.alice, json={"status": "completed"})
        pending = self.client.get("/api/study-plans?status=pending&page_size=4", headers=self.alice).json()["data"]
        self.assertEqual(pending["total"], 5)
        self.assertEqual(len(pending["list"]), 4)
        completed = self.client.get("/api/study-plans?status=completed", headers=self.alice).json()["data"]
        self.assertEqual(completed["total"], 1)
        self.assertEqual(completed["list"][0]["id"], row["id"])

    def test_legacy_plan_data_and_import_paths_remain_compatible(self):
        from app.models.campus import StudyPlan as LegacyModel
        from app.schemas.campus import PlanRequest as LegacyRequest
        from app.schemas.study_plan import PlanRequest
        self.assertIs(LegacyModel, StudyPlan)
        self.assertIs(LegacyRequest, PlanRequest)
        with SessionLocal() as db:
            db.add(StudyPlan(user_id=1, title=" ", content="\n", status="pending"))
            db.commit()
        self.assertEqual(self.client.get("/api/study-plans", headers=self.alice).json()["data"]["total"], 1)
        self.assertEqual(len(self.client.get("/api/plans", headers=self.alice).json()["data"]), 1)

    def test_document_validation_and_course_ownership(self):
        course = self.create_course()
        for filename, content in (("evil.exe", b"file"), ("empty.txt", b""), ("bad.txt", b"\xff\xfe")):
            self.assertIn(self.client.post("/api/documents", headers=self.alice, files={"file": (filename, content)}).status_code, (413, 422))
        self.assertEqual(self.client.post("/api/documents", headers=self.bob,
            data={"course_id": course["id"]}, files={"file": ("notes.txt", b"private")}).status_code, 404)

    def test_missing_embedding_records_failed_document_privately(self):
        response = self.client.post("/api/documents", headers=self.alice, files={"file": ("notes.md", "期末占比60%".encode())})
        document = response.json()["data"]
        self.assertEqual(document["status"], "failed")
        self.assertEqual(self.client.get("/api/documents", headers=self.bob).json()["data"], [])
        self.assertEqual(self.client.get(f'/api/documents/{document["id"]}', headers=self.bob).status_code, 404)
        self.assertEqual(self.client.post(f'/api/documents/{document["id"]}/index', headers=self.bob).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/documents/{document["id"]}', headers=self.bob).status_code, 404)
        self.assertNotIn("content", document)

    def test_index_and_retrieval_check_sql_ownership(self):
        class Embeddings:
            def embed_documents(self, texts): return [[1.0, 0.0] for _ in texts]
            def embed_query(self, text): return [1.0, 0.0]

        class Store:
            def delete(self, **kwargs): pass
            def upsert(self, **kwargs): self.batch = kwargs
            def query(self, **kwargs):
                self.filters = kwargs["where"]
                return {"documents": [["考核占比60%", "他人的资料"]], "metadatas": [[
                    {"user_id": 1, "document_id": self.batch["metadatas"][0]["document_id"], "chunk": 1},
                    {"user_id": 2, "document_id": 999, "chunk": 1}]]}

        store = Store()
        with patch.object(rag_service, "embedding_client", return_value=Embeddings()), patch.object(rag_service, "collection", return_value=store):
            document = self.client.post("/api/documents", headers=self.alice, files={"file": ("notes.txt", "考核占比60%".encode())}).json()["data"]
            self.assertEqual(document["status"], "ready")
            response = self.client.post("/api/documents/search", headers=self.alice, json={"query": "怎么考核"})
            results = response.json()["data"]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["document_id"], document["id"])
            self.assertIn({"user_id": 1}, store.filters["$and"])
            self.assertEqual(self.client.post("/api/documents/search", headers=self.bob, json={"query": "怎么考核"}).json()["data"], [])
            self.assertEqual(self.client.delete(f'/api/documents/{document["id"]}', headers=self.alice).status_code, 200)

    def test_course_with_document_cannot_be_deleted(self):
        course = self.create_course()
        self.client.post("/api/documents", headers=self.alice, data={"course_id": course["id"]}, files={"file": ("notes.txt", b"notes")})
        self.assertEqual(self.client.delete(f'/api/admin/courses/{course["id"]}', headers=self.admin).status_code, 409)

    def test_admin_course_crud_and_student_visibility(self):
        course = self.create_course()
        path = f'/api/admin/courses/{course["id"]}'
        detail = self.client.get(path, headers=self.admin).json()["data"]
        self.assertEqual(detail["username"], "alice")
        self.assertEqual(detail["user_id"], 1)
        payload = {**self.course_data, "user_id": 2, "name": "大学数学"}
        updated = self.client.put(path, headers=self.admin, json=payload)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["data"]["name"], "大学数学")
        self.assertEqual(self.client.get("/api/courses", headers=self.alice).json()["data"], [])
        self.assertEqual(len(self.client.get("/api/courses", headers=self.bob).json()["data"]), 1)
        self.assertEqual(self.client.delete(path, headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.admin).status_code, 404)

    def test_all_admin_course_routes_require_admin(self):
        course = self.create_course()
        base = "/api/admin/courses"
        payload = {**self.course_data, "user_id": 1}
        actions = [("GET", base, None), ("GET", f'{base}/{course["id"]}', None),
                   ("POST", base, payload), ("PUT", f'{base}/{course["id"]}', payload),
                   ("DELETE", f'{base}/{course["id"]}', None)]
        for headers, expected in (({}, 401), (self.alice, 403), (self.bob, 403)):
            for method, path, data in actions:
                response = self.client.request(method, path, headers=headers, json=data)
                self.assertEqual(response.status_code, expected, (method, path, response.text))

    def test_admin_course_list_pagination_search_and_owner_filter(self):
        self.create_course(1)
        self.create_course(2)
        response = self.client.get("/api/admin/courses?page=1&page_size=1", headers=self.admin).json()["data"]
        self.assertEqual(response["total"], 2)
        self.assertEqual(len(response["list"]), 1)
        second = self.client.get("/api/admin/courses?page=2&page_size=1", headers=self.admin).json()["data"]
        self.assertNotEqual(response["list"][0]["id"], second["list"][0]["id"])
        for keyword in ("数学", "张老师"):
            data = self.client.get("/api/admin/courses", headers=self.admin, params={"keywords": keyword, "user_id": 2}).json()["data"]
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["list"][0]["user_id"], 2)
        self.assertEqual(self.client.get("/api/admin/courses?keywords=notfound", headers=self.admin).json()["data"]["total"], 0)
        for query in ("page=0", "page_size=0", "page_size=101", "user_id=0"):
            self.assertEqual(self.client.get(f"/api/admin/courses?{query}", headers=self.admin).status_code, 422)

    def test_admin_course_missing_records_and_owner(self):
        payload = {**self.course_data, "user_id": 999}
        self.assertEqual(self.client.post("/api/admin/courses", headers=self.admin, json=payload).status_code, 404)
        for method in ("GET", "PUT", "DELETE"):
            self.assertEqual(self.client.request(method, "/api/admin/courses/999", headers=self.admin,
                json={**self.course_data, "user_id": 1} if method == "PUT" else None).status_code, 404)
        course = self.create_course()
        self.assertEqual(self.client.put(f'/api/admin/courses/{course["id"]}', headers=self.admin, json=payload).status_code, 404)

    def test_course_with_private_document_cannot_change_owner(self):
        course = self.create_course()
        with SessionLocal() as db:
            db.add(Document(user_id=1, course_id=course["id"], name="private.txt", content="private", status="failed"))
            db.commit()
        path = f'/api/admin/courses/{course["id"]}'
        payload = {**self.course_data, "user_id": 2}
        self.assertEqual(self.client.put(path, headers=self.admin, json=payload).status_code, 409)
        self.assertEqual(self.client.delete(path, headers=self.admin).status_code, 409)
        self.assertEqual(self.client.get(path, headers=self.admin).json()["data"]["user_id"], 1)

    def test_legacy_course_writes_still_work_for_admin_owned_courses(self):
        created = self.client.post("/api/courses", headers=self.admin, json=self.course_data)
        self.assertEqual(created.status_code, 200, created.text)
        path = f'/api/courses/{created.json()["data"]["id"]}'
        self.assertEqual(self.client.put(path, headers=self.admin, json=self.course_data).status_code, 200)
        self.assertEqual(self.client.delete(path, headers=self.admin).status_code, 200)

    def test_chat_history_private_and_concurrent_run_rejected(self):
        session = self.client.post("/api/chat/sessions", headers=self.alice).json()["data"]
        session_id = session["id"]
        self.assertEqual(self.client.get(f"/api/chat/sessions/{session_id}/messages", headers=self.bob).status_code, 404)
        token, history = chat_service.acquire_run(1, session_id, "你好")
        self.assertEqual(history[-1]["content"], "你好")
        with self.assertRaises(Exception) as error:
            chat_service.acquire_run(1, session_id, "重复发送")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.client.delete(f"/api/chat/sessions/{session_id}", headers=self.alice).status_code, 409)
        chat_service.finish_run(session_id, "wrong-token", "错误的回答", [], [])
        self.assertEqual(len(chat_service.get_messages(1, session_id)), 1)
        chat_service.finish_run(session_id, token, "你好，同学", [], [])
        self.assertEqual(len(chat_service.get_messages(1, session_id)), 2)
        self.assertEqual(self.client.delete(f"/api/chat/sessions/{session_id}", headers=self.alice).status_code, 200)

    def test_missing_model_key_returns_actionable_error(self):
        session = self.client.post("/api/chat/sessions", headers=self.alice).json()["data"]
        response = self.client.post(f'/api/chat/sessions/{session["id"]}/stream', headers=self.alice, json={"message": "你好"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM_API_KEY", response.json()["message"])

    def test_compatible_model_sends_deepseek_parameters_on_wire(self):
        import httpx
        from app.services.agent_service import build_chat_model

        payloads = []

        def handle(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "mock-completion", "object": "chat.completion",
                "created": 1, "model": "deepseek-flash", "choices": [{"index": 0,
                "message": {"role": "assistant", "content": "你好"}, "finish_reason": "stop"}]})

        with patch.object(settings, "LLM_API_KEY", "test-only"):
            model = build_chat_model()
            model.streaming = False
            # Inject a transport instead of calling any external model API.
            with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
                model.http_client = http_client
                from openai import OpenAI
                model.client = OpenAI(api_key="test-only", base_url=settings.LLM_BASE_URL, http_client=http_client).chat.completions
                response = model.invoke("你好")
        self.assertEqual(response.content, "你好")
        self.assertEqual(payloads[0]["max_tokens"], 2048)
        self.assertNotIn("max_completion_tokens", payloads[0])
        self.assertEqual(payloads[0]["thinking"], {"type": "disabled"})

    def test_mcp_rejects_invalid_credentials(self):
        import httpx
        import jwt
        self.assertEqual(httpx.get(self.mcp_url).status_code, 401)
        payload = decode_tool_token(create_tool_token(1))
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["aud"], "campus-mcp")
        expired = jwt.encode({"user_id": 1, "aud": "campus-mcp", "exp": 1},
            settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        self.assertEqual(httpx.get(self.mcp_url, headers={"Authorization": f"Bearer {expired}"}).status_code, 401)
        for claims in (
            {"user_id": 1}, {"user_id": 1, "exp": 9999999999, "aud": "other-service"},
            {"user_id": True, "exp": 9999999999}, {"user_id": "1", "exp": 9999999999},
            {"user_id": -1, "exp": 9999999999}, {"exp": 9999999999},
            {"user_id": 9999, "exp": 9999999999},
            {"user_id": 1, "exp": 9999999999, "aud": ""},
        ):
            token = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            self.assertEqual(httpx.get(self.mcp_url, headers={"Authorization": f"Bearer {token}"}).status_code, 401)
        for authorization in ("Basic abc", "Bearer broken", "Bearer", "Bearer a b"):
            self.assertEqual(httpx.get(self.mcp_url, headers={"Authorization": authorization}).status_code, 401)
        with SessionLocal() as db:
            db.get(User, 1).status = 0
            db.commit()
        self.assertEqual(httpx.get(self.mcp_url, headers=self.alice).status_code, 401)

    def test_real_mcp_transport_isolates_users_and_saves_plan(self):
        course = self.create_course()
        self.create_schedule(course["id"], location="新课表地点", start_time="14:00:00", end_time="15:30:00")

        async def run():
            for user_id, expected in ((1, 1), (2, 0)):
                client = MultiServerMCPClient({"campus": {"transport": "http", "url": self.mcp_url,
                    "headers": {"Authorization": f"Bearer {create_tool_token(user_id)}"}}})
                tools = {tool.name: tool for tool in await client.get_tools()}
                self.assertEqual(set(tools), {"get_my_schedules", "query_schedule", "search_materials", "list_study_plans", "save_study_plan"})
                self.assertNotIn("user_id", tools["query_schedule"].args)
                result = await tools["query_schedule"].ainvoke({})
                if isinstance(result, tuple): result = result[0]
                if isinstance(result, list): result = "".join(block.get("text", "") for block in result)
                self.assertEqual(len(json.loads(result)["courses"]), expected)
                if user_id == 1:
                    self.assertEqual(json.loads(result)["courses"][0]["location"], "新课表地点")
                    self.assertEqual(json.loads(result)["courses"][0]["start_time"], "14:00:00")
                if user_id == 1:
                    await tools["save_study_plan"].ainvoke({"title": "MCP 计划", "content": "数学复习"})
        asyncio.run(run())
        self.assertEqual(len(self.client.get("/api/plans", headers=self.alice).json()["data"]), 1)
        self.assertEqual(self.client.get("/api/plans", headers=self.bob).json()["data"], [])

    def test_login_token_mcp_schedule_dates_and_isolation(self):
        course = self.create_course()
        self.create_schedule(course["id"])

        async def run():
            for username, password, expected in (("alice", "alice123", 1), ("bob", "bob123", 0)):
                token = self.client.post("/api/auth/login", json={"username": username, "password": password}).json()["data"]["token"]
                client = MultiServerMCPClient({"campus": {"transport": "http", "url": self.mcp_url,
                    "headers": {"Authorization": f"bearer {token}"}}})
                tools = {tool.name: tool for tool in await client.get_tools()}
                self.assertEqual(set(tools["get_my_schedules"].args), {"on_date"})
                for args, count in (({}, expected), ({"on_date": "2026-10-22"}, expected),
                                    ({"on_date": "2026-10-23"}, 0), ({"on_date": "2027-02-04"}, 0)):
                    result = await tools["get_my_schedules"].ainvoke(args)
                    if isinstance(result, tuple): result = result[0]
                    if isinstance(result, list): result = "".join(block.get("text", "") for block in result)
                    data = json.loads(result)
                    self.assertEqual(data["total"], count)
                    self.assertEqual(len(data["schedules"]), count)
                    if count:
                        row = data["schedules"][0]
                        self.assertEqual(row["start_time"], "08:00:00")
                        self.assertEqual(row["start_date"], "2026-09-01")
                        self.assertNotIn("student_id", row)
                with self.assertRaises(Exception):
                    await tools["get_my_schedules"].ainvoke({"on_date": "not-a-date"})
        asyncio.run(run())

    def test_fastapi_mcp_aaa_bbb_jwt_forwarding(self):
        with SessionLocal() as db:
            db.get(User, 1).username = "aaa"
            db.get(User, 2).username = "bbb"
            db.commit()
        course = self.create_course()
        self.create_schedule(course["id"])
        with patch.object(settings, "MCP_URL", self.mcp_url), patch(
            "app.services.mcp_client.MultiServerMCPClient", wraps=MultiServerMCPClient
        ) as factory:
            for name, password, expected in (("aaa", "alice123", 1), ("bbb", "bob123", 0), ("aaa", "alice123", 1)):
                login = self.client.post("/api/auth/login", json={"username": name, "password": password})
                token = login.json()["data"]["token"]
                authorization = f"bEaReR {token}"
                response = self.client.get("/api/mcp/my-schedules", headers={"Authorization": authorization},
                    params={"on_date": "2026-10-22", "user_id": 1, "student_id": 1})
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()["data"]
                self.assertEqual(data["total"], expected)
                self.assertEqual(len(data["schedules"]), expected)
                connection = factory.call_args.args[0]["campus"]
                self.assertEqual(connection["headers"], {"Authorization": authorization})
                self.assertNotIn("user_id", connection)
                direct = self.client.get("/api/schedules/me", headers={"Authorization": authorization},
                    params={"on_date": "2026-10-22"}).json()["data"]
                self.assertEqual(data["schedules"], direct)
            self.assertEqual(factory.call_count, 3)
            empty = self.client.get("/api/mcp/my-schedules", headers=self.alice,
                                    params={"on_date": "2026-10-23"})
            self.assertEqual(empty.json()["data"], {"schedules": [], "total": 0})

    def test_fastapi_mcp_auth_and_swagger(self):
        with patch("app.services.mcp_client.MultiServerMCPClient") as factory:
            for headers in ({}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic abc"}):
                self.assertEqual(self.client.get("/api/mcp/my-schedules", headers=headers).status_code, 401)
            self.assertEqual(self.client.get("/api/mcp/my-schedules", headers=self.alice,
                params={"on_date": "invalid"}).status_code, 422)
            with SessionLocal() as db:
                db.get(User, 1).status = 0
                db.commit()
            self.assertEqual(self.client.get("/api/mcp/my-schedules", headers=self.alice).status_code, 401)
            factory.assert_not_called()
        schema = self.client.get("/openapi.json").json()
        endpoint = schema["paths"]["/api/mcp/my-schedules"]["get"]
        self.assertEqual(endpoint["security"], [{"LoginJWT": []}])
        self.assertEqual(schema["components"]["securitySchemes"]["LoginJWT"]["scheme"], "bearer")
        self.assertEqual([p["name"] for p in endpoint["parameters"]], ["on_date"])

    def test_fastapi_mcp_upstream_failures_are_safe(self):
        import httpx
        for error, expected in (
            (httpx.ConnectError("private detail"), 503),
            (TimeoutError("private detail"), 504),
            (ValueError("private detail"), 502),
            (ExceptionGroup("transport", [httpx.HTTPStatusError("private detail",
                request=httpx.Request("POST", "http://local/mcp"), response=httpx.Response(401))]), 401),
        ):
            with self.subTest(expected=expected), patch("app.services.mcp_client.MultiServerMCPClient") as factory:
                factory.return_value.get_tools = AsyncMock(side_effect=error)
                response = self.client.get("/api/mcp/my-schedules", headers=self.alice)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("private detail", response.text)
                self.assertNotIn(self.alice["Authorization"], response.text)

    def test_fastapi_mcp_timeout_and_invalid_tool_response(self):
        async def slow():
            await asyncio.sleep(1)
        with patch.object(settings, "MCP_TIMEOUT_SECONDS", 0.01), patch("app.services.mcp_client.MultiServerMCPClient") as factory:
            factory.return_value.get_tools = slow
            self.assertEqual(self.client.get("/api/mcp/my-schedules", headers=self.alice).status_code, 504)
        from types import SimpleNamespace
        for tools in ([], [SimpleNamespace(name="get_my_schedules", ainvoke=AsyncMock(
            return_value=ToolMessage(content='{"schedules":[],"total":1}', tool_call_id="schedules")))]):
            with patch("app.services.mcp_client.MultiServerMCPClient") as factory:
                factory.return_value.get_tools = AsyncMock(return_value=tools)
                self.assertEqual(self.client.get("/api/mcp/my-schedules", headers=self.alice).status_code, 502)

    def test_chat_ask_react_mcp_history_and_account_isolation(self):
        course = self.create_course()
        self.create_schedule(course["id"], location="学生一专属教室")
        model = ScheduleDialogueModel()
        with patch.object(settings, "LLM_API_KEY", "offline-test"), patch.object(settings, "MCP_URL", self.mcp_url), patch(
            "app.services.agent_service.build_chat_model", return_value=model
        ), patch("app.services.mcp_client.MultiServerMCPClient", wraps=MultiServerMCPClient) as factory:
            first = self.client.post("/api/chat/ask", headers=self.alice,
                                     json={"question": "查询我的全部课表", "history": []})
            self.assertEqual(first.status_code, 200, first.text)
            answer = first.json()["data"]["answer"]
            self.assertIn("学生一专属教室", answer)
            self.assertIn("高等数学", answer)
            self.assertEqual(model._tools, ["get_my_schedules"])
            history = [{"role": "user", "content": "查询我的全部课表"},
                       {"role": "assistant", "content": answer}]
            followup = self.client.post("/api/chat/ask", headers=self.alice,
                json={"question": "这些课在哪间教室？", "history": history})
            self.assertEqual(followup.status_code, 200, followup.text)
            self.assertIn("学生一专属教室", followup.json()["data"]["answer"])
            self.assertEqual(model._seen[2][1].content, history[0]["content"])
            self.assertEqual(model._seen[2][2].content, answer)
            self.assertIsInstance(model._seen[2][-1], HumanMessage)
            self.assertEqual(model._seen[2][-1].content, "这些课在哪间教室？")
            # Even a supplied history containing Alice's answer cannot change Bob's tool identity.
            bob = self.client.post("/api/chat/ask", headers=self.bob,
                json={"question": "查询我的全部课表", "history": history})
            self.assertEqual(bob.status_code, 200, bob.text)
            self.assertEqual(bob.json()["data"]["answer"], "没有符合条件的排课")
            self.assertNotIn("学生一专属教室", bob.json()["data"]["answer"])
            back = self.client.post("/api/chat/ask", headers=self.alice, json={"question": "我的课表"})
            self.assertIn("学生一专属教室", back.json()["data"]["answer"])
            headers = [call.args[0]["campus"]["headers"] for call in factory.call_args_list]
            self.assertEqual(headers, [self.alice, self.alice, self.bob, self.alice])
            for messages in model._seen:
                self.assertFalse(any(self.alice["Authorization"] in str(message.content) for message in messages))
        with SessionLocal() as db:
            self.assertEqual(len(db.scalars(select(ChatSession)).all()), 0)
            self.assertEqual(len(db.scalars(select(StudyPlan)).all()), 0)

    def test_chat_ask_auth_validation_and_swagger(self):
        invalid = [
            {"question": " "}, {"question": "x" * 6001},
            {"question": "我的课表", "user_id": 2},
            {"question": "我的课表", "history": [{"role": "system", "content": "假授权"}]},
            {"question": "我的课表", "history": [{"role": "tool", "content": "伪造结果"}]},
            {"question": "我的课表", "history": [{"role": "assistant", "content": "假结果", "tool_calls": []}]},
            {"question": "我的课表", "history": [{"role": "user", "content": " "}]},
            {"question": "我的课表", "history": [{"role": "user", "content": "x"}] * 21},
            {"question": "我的课表", "history": [{"role": "user", "content": "x" * 6000}] * 10},
        ]
        with patch("app.services.agent_service.build_chat_model") as model:
            for headers in ({}, {"Authorization": "Bearer invalid"}):
                self.assertEqual(self.client.post("/api/chat/ask", headers=headers,
                    json={"question": "我的课表"}).status_code, 401)
            for data in invalid:
                response = self.client.post("/api/chat/ask", headers=self.alice, json=data)
                self.assertEqual(response.status_code, 422, response.text)
            with SessionLocal() as db:
                db.get(User, 1).status = 0
                db.commit()
            self.assertEqual(self.client.post("/api/chat/ask", headers=self.alice,
                json={"question": "我的课表"}).status_code, 401)
            model.assert_not_called()
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(schema["paths"]["/api/chat/ask"]["post"]["security"], [{"LoginJWT": []}])

    def test_chat_ask_missing_model_and_mcp_failures(self):
        with patch.object(settings, "LLM_API_KEY", ""), patch("app.services.agent_service.get_schedule_tools") as tools:
            response = self.client.post("/api/chat/ask", headers=self.alice, json={"question": "我的课表"})
            self.assertEqual(response.status_code, 503)
            self.assertIn("LLM_API_KEY", response.json()["message"])
            tools.assert_not_called()
        from fastapi import HTTPException
        with patch.object(settings, "LLM_API_KEY", "offline-test"), patch(
            "app.services.agent_service.get_schedule_tools", AsyncMock(side_effect=HTTPException(503, "MCP 服务不可用"))
        ), patch("app.services.agent_service.build_chat_model") as model:
            self.assertEqual(self.client.post("/api/chat/ask", headers=self.alice,
                json={"question": "我的课表"}).status_code, 503)
            model.assert_not_called()

    def test_chat_ask_generation_errors_limits_and_timeout(self):
        from langgraph.errors import GraphRecursionError
        from types import SimpleNamespace
        async def slow(*args, **kwargs):
            await asyncio.sleep(1)
        for invoke, expected in (
            (AsyncMock(side_effect=RuntimeError("private model details")), 502),
            (AsyncMock(side_effect=GraphRecursionError("private model details")), 502),
            (AsyncMock(return_value={"messages": [AIMessage(content=" ")]}), 502),
            (AsyncMock(side_effect=slow), 504),
        ):
            with patch.object(settings, "LLM_API_KEY", "offline-test"), patch.object(settings, "AGENT_TIMEOUT_SECONDS", 0.05), patch(
                "app.services.agent_service.get_schedule_tools", AsyncMock(return_value=[])
            ), patch("app.services.agent_service.build_chat_model"), patch(
                "app.services.agent_service.create_agent", return_value=SimpleNamespace(ainvoke=invoke)
            ):
                response = self.client.post("/api/chat/ask", headers=self.alice, json={"question": "我的课表"})
                self.assertEqual(response.status_code, expected, response.text)
                self.assertNotIn("private model details", response.text)

    @staticmethod
    def sse_events(response):
        events = []
        for frame in response.text.split("\n\n"):
            if frame.startswith("event: "):
                name, data = frame.split("\n", 1)
                events.append((name[7:], json.loads(data[6:])))
        return events

    def test_chat_stream_real_v2_events_history_and_isolation(self):
        course = self.create_course()
        self.create_schedule(course["id"], location="流式专属教室 A101")
        model = StreamingScheduleModel()
        with patch.object(settings, "LLM_API_KEY", "offline-test"), patch.object(settings, "MCP_URL", self.mcp_url), patch(
            "app.services.agent_service.build_chat_model", return_value=model
        ):
            history = []
            for headers, question, expected in ((self.alice, "我的全部课表", "流式专属教室 A101"),
                (self.alice, "这些课在哪里上？", "流式专属教室 A101"), (self.bob, "我的全部课表", "没有符合条件的排课")):
                response = self.client.post("/api/chat/stream", headers=headers,
                    json={"question": question, "history": history})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("text/event-stream", response.headers["content-type"])
                self.assertEqual(response.headers["x-accel-buffering"], "no")
                events = self.sse_events(response)
                names = [name for name, _ in events]
                for name in ("status", "tool_start", "tool_end", "token", "done"):
                    self.assertIn(name, names, response.text)
                self.assertNotIn("error", names, response.text)
                self.assertLess(names.index("tool_start"), names.index("tool_end"))
                terminal = events[-1]
                self.assertEqual(terminal[0], "done")
                self.assertTrue(terminal[1]["success"], response.text)
                self.assertIn(expected, terminal[1]["answer"])
                tokens = [payload["text"] for name, payload in events if name == "token"]
                self.assertGreater(len(tokens), 1)
                self.assertEqual("".join(tokens), terminal[1]["answer"])
                start = next(payload for name, payload in events if name == "tool_start")
                end = next(payload for name, payload in events if name == "tool_end")
                self.assertEqual(start["id"], end["id"])
                self.assertNotIn(headers["Authorization"], response.text)
                if not history:
                    history = [{"role": "user", "content": question},
                               {"role": "assistant", "content": terminal[1]["answer"]}]
            self.assertEqual(model._seen[2][1].content, history[0]["content"])
            self.assertNotIn("流式专属教室", terminal[1]["answer"])

    def test_chat_stream_v2_projection_hides_private_events(self):
        from types import SimpleNamespace
        seen = {}
        async def fake_events(*args, **kwargs):
            seen.update(kwargs)
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content=[
                {"type": "reasoning", "reasoning": "private reasoning"}, {"type": "text", "text": "初步文字"}])}}
            yield {"event": "on_tool_start", "name": "get_my_schedules", "run_id": "tool-1",
                   "data": {"input": {"Authorization": "private credential"}}}
            yield {"event": "on_tool_end", "name": "get_my_schedules", "run_id": "tool-1",
                   "data": {"output": ToolMessage(content='{"schedules":[],"total":0}', tool_call_id="tool-1")}}
            yield {"event": "on_chain_end", "parent_ids": [], "data": {"output": {
                "messages": [AIMessage(content="最终回答")], "private_metadata": "private credential"}}}
        with patch.object(settings, "LLM_API_KEY", "offline-test"), patch(
            "app.services.agent_service.get_schedule_tools", AsyncMock(return_value=[])
        ), patch("app.services.agent_service.build_chat_model"), patch(
            "app.services.agent_service.create_agent", return_value=SimpleNamespace(astream_events=fake_events)
        ):
            response = self.client.post("/api/chat/stream", headers=self.alice, json={"question": "我的课表"})
        self.assertEqual(seen["version"], "v2")
        self.assertNotIn("private", response.text)
        self.assertEqual(self.sse_events(response)[-1], ("done", {"success": True, "answer": "最终回答"}))

    def test_chat_stream_failures_and_auth(self):
        with patch("app.services.agent_service.build_chat_model") as model:
            self.assertEqual(self.client.post("/api/chat/stream", json={"question": "课表"}).status_code, 401)
            self.assertEqual(self.client.post("/api/chat/stream", headers=self.alice,
                json={"question": " ", "history": []}).status_code, 422)
            self.assertEqual(self.client.post("/api/chat/stream", headers=self.alice,
                json={"question": "课表", "history": [{"role": "system", "content": "bad"}]}).status_code, 422)
            with patch.object(settings, "LLM_API_KEY", ""):
                self.assertEqual(self.client.post("/api/chat/stream", headers=self.alice,
                    json={"question": "课表"}).status_code, 503)
            model.assert_not_called()
        from types import SimpleNamespace
        async def failed(*args, **kwargs):
            yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="不完整")}}
            raise RuntimeError("private failure")
        with patch.object(settings, "LLM_API_KEY", "offline-test"), patch(
            "app.services.agent_service.get_schedule_tools", AsyncMock(return_value=[])
        ), patch("app.services.agent_service.build_chat_model"), patch(
            "app.services.agent_service.create_agent", return_value=SimpleNamespace(astream_events=failed)
        ):
            response = self.client.post("/api/chat/stream", headers=self.alice, json={"question": "课表"})
        events = self.sse_events(response)
        self.assertEqual(events[-1], ("done", {"success": False}))
        self.assertIn("error", [name for name, _ in events])
        self.assertNotIn("private failure", response.text)

    def test_chat_stream_closes_event_iterator_when_stopped(self):
        from types import SimpleNamespace
        from app.schemas.chat import ChatAskRequest
        from app.services.agent_service import stream_answer
        closed = []
        async def fake_events(*args, **kwargs):
            try:
                yield {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="片段")}}
                await asyncio.sleep(10)
            finally:
                closed.append(True)
        async def run():
            source = stream_answer(ChatAskRequest(question="课表"), self.alice["Authorization"])
            while True:
                name, payload = await anext(source)
                if name == "token":
                    break
            await source.aclose()
        with patch("app.services.agent_service.get_schedule_tools", AsyncMock(return_value=[])), patch(
            "app.services.agent_service.build_chat_model"
        ), patch("app.services.agent_service.create_agent", return_value=SimpleNamespace(astream_events=fake_events)):
            asyncio.run(run())
        self.assertEqual(closed, [True])

    @contextmanager
    def kb_storage(self):
        with tempfile.TemporaryDirectory(prefix="campus-kb-") as folder:
            root = Path(folder) / "kb"
            with patch("app.services.kb_document_service.STORAGE_DIR", root):
                yield root

    def kb_upload(self, files, headers=None):
        return self.client.post("/api/admin/kb-documents/batch", headers=headers or self.admin,
                                files=[("files", (name, content)) for name, content in files])

    def test_admin_kb_batch_list_preview_and_delete(self):
        with self.kb_storage() as root:
            result = self.kb_upload([("../../notes.txt", "数学笔记".encode()),
                                     ("大纲.md", b"# syllabus\n<script>alert(1)</script>")])
            self.assertEqual(result.status_code, 200, result.text)
            rows = result.json()["data"]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["file_name"], "notes.txt")
            for row in rows:
                self.assertFalse(Path(row["file_path"]).is_absolute())
                self.assertEqual((root / row["file_path"]).stat().st_size, row["file_size"])
                self.assertNotIn("text_content", row)
            page = self.client.get("/api/admin/kb-documents", headers=self.admin,
                                   params={"page_size": 1}).json()["data"]
            self.assertEqual(page["total"], 2)
            self.assertEqual(len(page["list"]), 1)
            filtered = self.client.get("/api/admin/kb-documents", headers=self.admin,
                                       params={"keywords": "notes"}).json()["data"]
            self.assertEqual(filtered["total"], 1)
            preview = self.client.get(f'/api/admin/kb-documents/{rows[1]["id"]}/preview', headers=self.admin)
            self.assertEqual(preview.json()["data"]["content"], "# syllabus\n<script>alert(1)</script>")
            original = root / rows[0]["file_path"]
            deleted = self.client.delete(f'/api/admin/kb-documents/{rows[0]["id"]}', headers=self.admin)
            self.assertEqual(deleted.json()["data"], {"deleted": True, "cleanup_pending": False})
            self.assertFalse(original.exists())
            self.assertEqual(self.client.get(f'/api/admin/kb-documents/{rows[0]["id"]}/preview', headers=self.admin).status_code, 404)
            self.assertEqual(self.client.get("/api/admin/kb-documents", headers=self.admin).json()["data"]["total"], 1)

    def test_admin_kb_permissions_for_every_route(self):
        with self.kb_storage() as root:
            for headers, expected in (({}, 401), (self.alice, 403), (self.bob, 403)):
                for method, path, kwargs in (
                    ("get", "/api/admin/kb-documents", {}),
                    ("get", "/api/admin/kb-documents/1/preview", {}),
                    ("delete", "/api/admin/kb-documents/1", {}),
                    ("post", "/api/admin/kb-documents/batch", {"files": [("files", ("a.txt", b"text"))]}),
                ):
                    response = getattr(self.client, method)(path, headers=headers, **kwargs)
                    self.assertEqual(response.status_code, expected, response.text)
            self.assertFalse(root.exists())
            with SessionLocal() as db:
                db.get(User, 3).status = 0
                db.commit()
            self.assertEqual(self.kb_upload([("a.txt", b"text")]).status_code, 401)

    def test_admin_kb_later_parse_failure_rolls_back_entire_batch(self):
        with self.kb_storage() as root:
            existing = self.kb_upload([("old.txt", b"keep me")]).json()["data"][0]
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            for bad in (("broken.pdf", b"not a pdf"), ("bad.exe", b"executable"), ("bad.txt", b"\xff\xfe")):
                result = self.kb_upload([("new.txt", b"valid first file"), bad])
                self.assertEqual(result.status_code, 422, result.text)
                self.assertIn("本批未保存", result.json()["message"])
                self.assertEqual(sorted(path.relative_to(root).as_posix() for path in root.rglob("*")), before)
                with SessionLocal() as db:
                    self.assertEqual([row.id for row in db.scalars(select(KBDocument))], [existing["id"]])
                self.assertEqual((root / existing["file_path"]).read_bytes(), b"keep me")

    def test_admin_kb_disk_and_database_failure_rollbacks(self):
        from app.services import kb_document_service as service
        from sqlalchemy.exc import SQLAlchemyError
        with self.kb_storage() as root:
            original_write = service._write_file
            written = []
            def fail_second(path, content):
                original_write(path, content)
                written.append(path)
                if len(written) == 2:
                    raise OSError("private disk details")
            with patch.object(service, "_write_file", side_effect=fail_second):
                result = self.kb_upload([("a.txt", b"first"), ("b.txt", b"second")])
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("private disk details", result.text)
            self.assertEqual(list(root.iterdir()), [])
            with patch("app.services.kb_document_service.Session.commit", side_effect=SQLAlchemyError("private sql")):
                result = self.kb_upload([("a.txt", b"first"), ("b.txt", b"second")])
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("private sql", result.text)
            self.assertEqual(list(root.iterdir()), [])
            with SessionLocal() as db:
                self.assertEqual(db.scalars(select(KBDocument)).all(), [])
            # A failed mkdir must not clean up another batch's pre-existing directory.
            from types import SimpleNamespace
            owned_by_other = root / "existing-batch"
            owned_by_other.mkdir()
            (owned_by_other / "keep.txt").write_text("keep")
            with patch.object(service, "uuid4", return_value=SimpleNamespace(hex="existing-batch")):
                self.assertEqual(self.kb_upload([("a.txt", b"text")]).status_code, 503)
            self.assertEqual((owned_by_other / "keep.txt").read_text(), "keep")

    def test_admin_kb_upload_limits(self):
        from app.services import kb_document_service as service
        with self.kb_storage() as root:
            self.assertEqual(self.kb_upload([(f"{i}.txt", b"x") for i in range(21)]).status_code, 422)
            self.assertFalse(root.exists())
            self.assertEqual(self.kb_upload([("empty.txt", b"")]).status_code, 413)
            self.assertEqual(self.kb_upload([("big.txt", b"x" * (10 * 1024 * 1024 + 1))]).status_code, 413)
            with patch.object(service, "MAX_BATCH_SIZE", 8):
                self.assertEqual(self.kb_upload([("a.txt", b"first"), ("b.txt", b"second")]).status_code, 413)
            self.assertEqual(list(root.iterdir()), [])

    def test_admin_kb_delete_commit_failure_restores_file(self):
        from sqlalchemy.exc import SQLAlchemyError
        with self.kb_storage() as root:
            row = self.kb_upload([("a.txt", b"keep this file")]).json()["data"][0]
            with patch("app.services.kb_document_service.Session.commit", side_effect=SQLAlchemyError("private sql")):
                result = self.client.delete(f'/api/admin/kb-documents/{row["id"]}', headers=self.admin)
            self.assertEqual(result.status_code, 503)
            self.assertEqual((root / row["file_path"]).read_bytes(), b"keep this file")
            with SessionLocal() as db:
                self.assertIsNotNone(db.get(KBDocument, row["id"]))
            self.assertFalse(list(root.rglob(".deleted-*")))

    def test_admin_kb_storage_path_cannot_escape_private_root(self):
        with self.kb_storage() as root:
            row = self.kb_upload([("a.txt", b"text")]).json()["data"][0]
            outside = root.parent / "outside.txt"
            outside.write_text("keep")
            with SessionLocal() as db:
                db.get(KBDocument, row["id"]).file_path = "../outside.txt"
                db.commit()
            result = self.client.delete(f'/api/admin/kb-documents/{row["id"]}', headers=self.admin)
            self.assertEqual(result.status_code, 500)
            self.assertEqual(outside.read_text(), "keep")

    def test_agent_sse_runs_real_tools_and_persists_history(self):
        course = self.create_course()
        self.create_schedule(course["id"])
        session = self.client.post("/api/chat/sessions", headers=self.alice).json()["data"]
        with patch.object(settings, "LLM_API_KEY", "test-only"), patch.object(settings, "MCP_URL", self.mcp_url), patch("app.services.agent_service.ChatOpenAI", return_value=ScriptedCourseModel()):
            response = self.client.post(f'/api/chat/sessions/{session["id"]}/stream', headers=self.alice,
                json={"message": "查看课表并帮我保存一份数学复习计划"})
        self.assertEqual(response.status_code, 200)
        for event in ("status", "tool_start", "tool_end", "token", "done"):
            self.assertIn(f"event: {event}", response.text, response.text)
        self.assertNotIn("event: error", response.text, response.text)
        self.assertIn('"success": true', response.text)
        messages = chat_service.get_messages(1, session["id"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(len(messages[-1]["events"]), 3)
        self.assertEqual(len(self.client.get("/api/plans", headers=self.alice).json()["data"]), 1)
        with SessionLocal() as db:
            self.assertIsNone(db.get(ChatSession, session["id"]).run_token)

    def test_agent_failure_releases_lease(self):
        session = self.client.post("/api/chat/sessions", headers=self.alice).json()["data"]
        with patch.object(settings, "LLM_API_KEY", "test-only"), patch("app.services.agent_service.MultiServerMCPClient.get_tools", side_effect=RuntimeError("private backend error")):
            response = self.client.post(f'/api/chat/sessions/{session["id"]}/stream', headers=self.alice, json={"message": "你好"})
        self.assertIn("event: error", response.text)
        self.assertNotIn("private backend error", response.text)
        with SessionLocal() as db:
            self.assertIsNone(db.get(ChatSession, session["id"]).run_token)

    def test_schedule_crud_is_independent_of_course(self):
        course = self.create_course(3)
        self.assertEqual(self.client.get("/api/schedules/me", headers=self.alice).json()["data"], [])
        slot = self.create_schedule(course["id"], location="实际排课地点")
        path = f'/api/admin/schedules/{slot["id"]}'
        detail = self.client.get(path, headers=self.admin).json()["data"]
        self.assertEqual(detail["student_id"], 1)
        self.assertEqual(detail["location"], "实际排课地点")
        data = {key: detail[key] for key in ("student_id", "course_id", "weekday", "start_time", "end_time", "start_date", "end_date", "location", "notes")}
        data.update(student_id=2, start_time="10:00:00", end_time="11:40:00")
        updated = self.client.put(path, headers=self.admin, json=data)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(self.client.get("/api/schedules/me", headers=self.alice).json()["data"], [])
        self.assertEqual(self.client.get("/api/schedules/me", headers=self.bob).json()["data"][0]["start_time"], "10:00:00")
        self.assertEqual(self.client.delete(path, headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.admin).status_code, 404)
        with SessionLocal() as db:
            self.assertIsNotNone(db.get(Course, course["id"]))

    def test_student_schedule_query_isolated_and_inclusive_dates(self):
        course = self.create_course(3)
        alice_slot = self.create_schedule(course["id"], start_date="2026-10-22", end_date="2026-11-05")
        bob_slot = self.create_schedule(course["id"], 2)
        for date in ("2026-10-22", "2026-11-05"):
            rows = self.client.get("/api/schedules/me", headers=self.alice, params={"on_date": date, "student_id": 2, "user_id": 2}).json()["data"]
            self.assertEqual([row["id"] for row in rows], [alice_slot["id"]])
            self.assertNotIn(bob_slot["id"], [row["id"] for row in rows])
        for date in ("2026-10-15", "2026-10-23", "2026-11-12"):
            self.assertEqual(self.client.get("/api/schedules/me", headers=self.alice, params={"on_date": date}).json()["data"], [])
        self.assertEqual(self.client.get("/api/schedules/me?on_date=invalid", headers=self.alice).status_code, 422)
        self.assertEqual(self.client.get("/api/schedules/me").status_code, 401)

    def test_schedule_management_requires_admin_for_every_route(self):
        course = self.create_course(3)
        slot = self.create_schedule(course["id"])
        path = f'/api/admin/schedules/{slot["id"]}'
        data = {key: slot[key] for key in ("student_id", "course_id", "weekday", "start_time", "end_time", "start_date", "end_date", "location", "notes")}
        actions = [("GET", "/api/admin/schedules", None), ("GET", path, None),
            ("GET", "/api/admin/schedules/student-options", None),
            ("POST", "/api/admin/schedules", data), ("PUT", path, data), ("DELETE", path, None)]
        for headers, status in (({}, 401), (self.alice, 403), (self.bob, 403)):
            for method, url, payload in actions:
                self.assertEqual(self.client.request(method, url, headers=headers, json=payload).status_code, status)

    def test_admin_schedule_filters_and_student_options(self):
        course = self.create_course(3)
        self.create_schedule(course["id"], 1)
        self.create_schedule(course["id"], 2)
        all_rows = self.client.get("/api/admin/schedules?page_size=1", headers=self.admin).json()["data"]
        self.assertEqual(all_rows["total"], 2)
        self.assertEqual(len(all_rows["list"]), 1)
        rows = self.client.get("/api/admin/schedules", headers=self.admin, params={"student_id": 2, "on_date": "2026-10-22", "course_id": course["id"]}).json()["data"]
        self.assertEqual(rows["total"], 1)
        self.assertEqual(rows["list"][0]["student_id"], 2)
        self.assertEqual(self.client.get("/api/admin/schedules?on_date=2026-10-23", headers=self.admin).json()["data"]["total"], 0)
        for query in ("page=0", "page_size=101", "student_id=0", "on_date=bad"):
            self.assertEqual(self.client.get(f"/api/admin/schedules?{query}", headers=self.admin).status_code, 422)
        options = self.client.get("/api/admin/schedules/student-options", headers=self.admin).json()["data"]
        self.assertEqual({row["id"] for row in options}, {1, 2})
        options = self.client.get("/api/admin/schedules/student-options?keywords=alice", headers=self.admin).json()["data"]
        self.assertEqual([row["id"] for row in options], [1])

    def test_schedule_validation_references_and_missing_rows(self):
        course = self.create_course(3)
        data = {key: self.course_data[key] for key in ("weekday", "start_time", "end_time", "start_date", "end_date", "location", "notes")}
        data.update(student_id=1, course_id=course["id"])
        for update in ({"weekday": 0}, {"end_time": "07:00:00"}, {"end_date": "2026-01-01"},
            {"start_time": "08:00:00+08:00"}, {"student_id": 3},
            {"start_date": "2026-10-23", "end_date": "2026-10-23"}):
            self.assertEqual(self.client.post("/api/admin/schedules", headers=self.admin, json={**data, **update}).status_code, 422)
        for update in ({"student_id": 999}, {"course_id": 999}):
            self.assertEqual(self.client.post("/api/admin/schedules", headers=self.admin, json={**data, **update}).status_code, 404)
        for method in ("GET", "PUT", "DELETE"):
            self.assertEqual(self.client.request(method, "/api/admin/schedules/999", headers=self.admin, json=data if method == "PUT" else None).status_code, 404)

    def test_course_delete_blocked_until_schedules_removed(self):
        course = self.create_course(3)
        slot = self.create_schedule(course["id"])
        for path in (f'/api/admin/courses/{course["id"]}', f'/api/courses/{course["id"]}'):
            response = self.client.delete(path, headers=self.admin)
            self.assertEqual(response.status_code, 409)
            self.assertIn("已排课", response.json()["message"])
        self.assertEqual(self.client.delete(f'/api/admin/schedules/{slot["id"]}', headers=self.admin).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/admin/courses/{course["id"]}', headers=self.admin).status_code, 200)

    def test_scheduled_student_can_use_course_without_reading_others_documents(self):
        course = self.create_course(3)
        self.create_schedule(course["id"], 1)
        visible = self.client.get("/api/courses", headers=self.alice).json()["data"]
        self.assertEqual([row["id"] for row in visible], [course["id"]])
        self.assertEqual(self.client.get("/api/courses", headers=self.bob).json()["data"], [])
        uploaded = self.client.post("/api/documents", headers=self.alice, data={"course_id": course["id"]}, files={"file": ("notes.txt", b"private notes")})
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        doc_id = uploaded.json()["data"]["id"]
        self.assertEqual(self.client.get(f"/api/documents/{doc_id}", headers=self.bob).status_code, 404)
        self.assertEqual(self.client.get(f"/api/documents/{doc_id}", headers=self.admin).status_code, 404)

    def test_user_with_schedule_cannot_be_deleted(self):
        from app.common.exceptions import BusinessException
        from app.services.user_service import delete_user
        course = self.create_course(3)
        self.create_schedule(course["id"], 1)
        with SessionLocal() as db:
            with self.assertRaises(BusinessException) as caught:
                delete_user(db, 1, db.get(User, 3))
            self.assertEqual(caught.exception.code, 409)

    def test_legacy_schedule_migration_does_not_duplicate_or_run_at_startup(self):
        from app.migrate_schedules import migrate_legacy_schedules
        course = self.create_course(1)
        self.create_course(3)
        with SessionLocal() as db:
            self.assertEqual(migrate_legacy_schedules(db), {"migrated": 1, "invalid_course_ids": []})
            self.assertEqual(migrate_legacy_schedules(db)["migrated"], 0)
            slot = db.scalar(select(Schedule).where(Schedule.course_id == course["id"]))
            self.assertEqual(slot.location, self.course_data["location"])
            db.delete(slot)
            db.commit()
        # Ordinary schema initialization does not recreate deliberately deleted slots.
        Base.metadata.create_all(engine)
        self.assertEqual(self.client.get("/api/schedules/me", headers=self.alice).json()["data"], [])


if __name__ == "__main__":
    unittest.main()
