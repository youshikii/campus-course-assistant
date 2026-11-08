# 校园课程智能助手

校园课程智能助手面向学生和管理员。管理员维护课程、学生排课和课程资料，学生查看个人课表、上传学习资料，并通过智能助手查询课表、检索资料和保存学习计划。

| 使用场景 | 功能 |
| --- | --- |
| 学生日常学习 | 我的课程、个人课表、学习计划、个人资料上传与检索 |
| 课程助手 | 查询当前账号的课表，支持流式回答与连续追问 |
| 智能助手 | 保存多轮会话，查询个人课表和计划，基于私有资料回答并展示来源。用户明确要求后可保存计划 |
| 管理员工作台 | 用户管理、课程管理、按学生排课、批量上传及预览课程资料 |

课程和排课独立保存。同一门课程可以排给多个学生，学生只能查询自己的排课。管理员批量上传的资料目前与学生个人检索分别管理。排课按星期和有效日期生效，冲突由管理员人工检查。

前端采用 Vue 3、Element Plus 和 Vite。后端采用 FastAPI、SQLAlchemy 和 MySQL，通过 JWT 鉴权。AI 对话使用 LangChain、FastMCP 和 SSE，个人资料检索使用 Chroma 和 bge-m3 向量模型。

## 目录结构

```text
campus-course-assistant/
├── backend/
│   ├── app/             API、权限、业务服务、MCP 和 RAG
│   ├── tests/           后端自动化测试
│   └── .env.example     后端配置模板
├── frontend/
│   ├── src/             学生与管理员页面
│   └── tests/           前端自动化测试
├── docs/                项目说明、开发指南和验收记录
├── sql/                 独立建表脚本
├── compose.yaml         本地 MySQL 与 Chroma
└── .env.example         Compose 配置模板
```

## 本地启动

准备 Python 3.12 或以上、MySQL 8.0 或以上，以及符合前端要求的 Node.js（22.18 至 22.x，或 24.12 及以上）。先进入克隆后的仓库根目录。以下命令以 PowerShell 为例。

1. **准备数据库。** 创建一个空 MySQL 库，或用 Compose 启动数据库和 Chroma。Compose 使用项目根目录的 `.env`，首次启动时从根目录的 `.env.example` 复制并填写密码。使用本机 MySQL 时，只启动 Compose 的 Chroma 服务即可。已有数据的库请保留现有表并按开发指南升级。旧版含删表语句的初始化 SQL 不随仓库发布。
2. **配置后端。** 进入 `backend/`，首次运行时创建虚拟环境、安装依赖，并将当前目录的 `.env.example` 复制为 `.env`。填写数据库连接和 JWT 密钥。演示智能助手与资料检索时，还需配置聊天模型、Embedding 和 Chroma。已有配置直接使用。

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

   填好 `backend/.env` 后初始化：

   ```powershell
   .\.venv\Scripts\python.exe -m app.init_db --admin campus_admin
   ```

   初始化命令交互输入新管理员密码，创建缺失的表。已有同名账号会保留原密码和角色。
3. **启动 FastAPI 与 MCP。** 在两个终端中分别进入 `backend/`，各运行一条命令。

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   .\.venv\Scripts\python.exe -m app.mcp_server
   ```

4. **启动前端。** 在第三个终端进入 `frontend/`。

   ```powershell
   npm ci
   npm run dev -- --host 127.0.0.1
   ```

启动后访问 [系统首页](http://127.0.0.1:5173) 或 [API 文档](http://127.0.0.1:8000/docs)。配置项、服务端口和旧库迁移步骤见 [开发与验收指南](docs/DEVELOPMENT.md)。

## 演示与验收

1. 管理员在「课程管理」创建课程，再在「课表管理」为两个学生设置不同课程或时段。
2. 分别登录两个学生账号，在「我的课表」对比安排，再用「课程助手」追问上课地点。
3. 在个人「课程资料库」上传一份含明确复习范围的示例文档。在「智能助手」提问并展开来源，明确要求保存计划后，到「学习计划」核对记录。

2026 年 11 月 8 日的本地验收记录显示，真实环境 API 用例 31 条通过，后端自动化 59 项和前端自动化 6 项通过。真实接口验收覆盖 MCP、Chroma、Embedding 和聊天模型链路。浏览器页面细节仍需按用例逐项复核。[验收记录](docs/test-results/2026-11-08-functional-test.md)

[项目说明书](docs/PROJECT_MANUAL.md) · [功能测试用例](docs/FUNCTIONAL_TEST_CASES.md)
