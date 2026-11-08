# 校园课程智能助手：开发与验收

## 第一版范围

保留原有账号、管理员用户管理、个人信息与头像功能，新增：

- 学习概览：真实统计、今日课程、待完成计划。
- 课程管理（管理员）：分页搜索、详情、新增、编辑、删除，为指定用户分配课程。
- 我的课程（所有登录用户）：只读课程信息；包含归属自己的课程，以及课表关联的课程。
- 我的课表（学生）：查询自己的每周课表，日期可选。
- 课表管理（管理员）：按学生、日期筛选，新增、详情、修改、删除独立排课。
- 私有资料库：PDF / DOCX / UTF-8 TXT / Markdown，解析、分块、向量化、检索、重建索引与删除。
- 课程资料管理（管理员）：批量上传原文件、分页列表、纯文本预览与删除，上传失败整批回滚。
- 学习计划：上方表单保存、下方按创建时间倒序分页，支持 Agent 保存、完成状态和删除。
- 智能助手：多会话历史、工具调用、SSE 流式回答、停止生成、原文引用。

当前不包含教务系统同步、单双周课表、OCR、联网搜索、自动提醒或教师共享课程。课表按每周重复且受起止日期约束；课程由管理员维护，学生管理自己的资料与计划。

## 架构与身份边界

```text
Vue 3 / Element Plus / marked + DOMPurify
    │ JWT + REST / POST SSE
FastAPI ── SQLAlchemy ── MySQL
    │ LangChain create_agent (LangGraph / ReAct)
    │ ChatOpenAI → DeepSeek / OpenAI-compatible endpoint
    │ langchain-mcp-adapters / per-run credentials
    ▼
FastMCP（独立进程，Streamable HTTP）
      ├── get_my_schedules     查询当前用户课表（query_schedule 保留兼容）
    ├── search_materials     检索当前用户资料
    ├── list_study_plans     查询当前用户计划
    └── save_study_plan      保存当前用户明确要求保存的计划
             │
       MySQL / Chroma HTTP
                  │ Embedding → SiliconFlow BAAI/bge-m3
```

FastAPI 根据登录 JWT 决定身份。Agent 每次运行创建一个独立 MCP 客户端，使用短时、带 `aud=campus-mcp` 的工具 JWT。FastMCP 同时支持登录接口签发的无 audience JWT，便于 Inspector 调试；带 audience 的凭证只接受 `campus-mcp`。两种凭证都校验签名、过期时间及正整数 `user_id`，并在协议请求和工具执行时检查账号是否存在且启用。工具 Schema 不包含 `user_id`，不由模型决定数据归属。

个人课表、文档、计划、会话在 SQL 查询中限定所属用户。管理员专用课程 API 可维护全部用户的课程，但不会获得学生私有文档内容。向量检索同时限定用户与当前 SQL 中可用的文档 ID，结果还会再次通过 SQL 权限检查。公开 `/uploads` 继续仅用于原有通用文件功能，课程资料不写入该目录。

### 课程模块

复用已有 `courses` 表，模型位于 `app/models/course.py`，服务位于 `app/services/course_service.py`，管理员路由位于 `app/api/course.py`。原 `app.models.campus.Course` 与 `app.schemas.campus.CourseRequest/CourseResponse` 导入路径仍兼容。

`courses` 已存在时无需迁移；新库通过 `app.init_db` 或 FastAPI 启动建立该表。独立建表脚本为 `sql/courses.sql`，使用 `CREATE TABLE IF NOT EXISTS`，不清表，且要求 `users` 表已存在。

管理员页面为 `/manager/course-management`，菜单仅管理员可见，并有前端路由守卫与后端 JWT 角色校验。支持课程名/教师关键词查询、分页、详情、用户选择、课程起止日期与时间校验。管理员可修改全部课程。旧 `/api/courses` 写接口保留 URL，但同样要求管理员权限，并只操作当前管理员自己的课程。

`courses` 保存课程信息，旧 `user_id` 和上课时间字段为兼容历史数据保留，不再代表已排课。实际学生、上课时间和地点以独立 `schedules` 记录为准；同一课程可以有多条排课、关联多个学生。存在课表时禁止删除课程，存在私有资料时继续禁止删除及更换课程归属，返回 409。

### 课表模块与升级

模型位于 `app/models/schedule.py`，服务位于 `app/services/schedule_service.py`，API 位于 `app/api/schedule.py`。表包含 `student_id`、`course_id`、`weekday`、`start_time/end_time`、`start_date/end_date`、`location`、`notes`，并以外键限制学生、课程删除。仅 `student` 角色可被分配课表。

每条排课按周重复，开始及结束日期都包含在有效范围内。日期筛选同时匹配星期和有效日期；未指定日期时列出所有排课。时间按北京时间处理，不支持跨午夜时段。当前不自动阻止不同课程时间重叠，管理员需核对安排。

学生页面 `/manager/my-schedules` 只读；管理员页面 `/manager/schedule-management` 支持学生远程搜索、按学生和日期筛选、分页及 CRUD。学生身份来自 JWT，客户端传入其他 `student_id/user_id` 不会改变个人查询范围。首页今日课程和 MCP `query_schedule` 都查询新课表。

首次升级请在后端停机期间执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.init_db --migrate-legacy-schedules
```

该命令建立缺失的表，把旧课程中归属学生的有效上课安排迁移为课表；已有相同课程与学生的排课时跳过，不覆盖现有课表。无有效上课日的旧课程会通过 `invalid_course_ids` 报告，原课程数据保留。普通启动只建表，不执行迁移，也不会把已删除的排课补回来；不要将此升级命令加入日常启动流程。独立建表脚本为 `sql/schedules.sql`。

学生被排到某课程后，可以为该课程上传自己的私有资料；其他学生和管理员仍不能读取该学生的私有文档。

### 学习计划模块

复用已有 `study_plans` 表，模型独立在 `app/models/study_plan.py`，分页列表、保存、删除和状态变更集中在 `app/services/study_plan_service.py`。独立建表脚本为 `sql/study_plans.sql`，使用 `CREATE TABLE IF NOT EXISTS`，不清空原数据；原 `app.models.campus.StudyPlan` 与计划 Schema 导入路径仍兼容。

`/manager/plans` 保留已有“学习计划”菜单，页面上方填写标题、内容及可选目标日期并保存，下方按 `create_time DESC, id DESC` 显示分页列表。内容使用 marked + DOMPurify 安全渲染 Markdown。保存成功跳回第一页；失败保留输入；删除当前页最后一条时退回上一页。已有完成状态功能保留。

`GET /api/study-plans?page=1&page_size=10` 返回 `data.list` 和 `data.total`；页码必须大于 0，每页 1–100 条。可用 `status=pending/completed` 筛选，首页仅加载最新 4 条待完成计划，并通过 `total` 显示完整待完成数量。POST 保存始终创建新计划，DELETE 删除指定计划，PATCH 保留状态切换。

所有接口、MCP 工具均从已验证的 JWT 确定用户。请求中附带 `user_id` 不会改变归属；管理员同样不能操作其他用户的学习计划。删除或切换他人计划状态返回 404。标题、内容不能只含空白，限制分别为 120、10000 字符。响应不对历史内容新增输入校验，保留旧数据的可读取性。

旧 `GET /api/plans` 保留数组返回，旧保存、删除及状态变更路径也继续兼容，统一委托新服务；新页面使用分页接口。MCP `list_study_plans` 新增可选 `page/page_size`，保持 `plans` 列表字段，并返回 `total`。

Chroma 使用独立 HTTP 服务，业务后端和 MCP 共享服务而不是同时打开本地嵌入式数据库。不同 Embedding 服务地址或模型使用不同 collection；变更 Embedding 配置后需要重建资料索引。

## 环境与安装

- Node.js 满足 `frontend/package.json` 的 engines；本轮验证环境为 Node 24。
- Python 3.12+；本轮验证环境为 Python 3.14。
- MySQL 8+。
- Chroma HTTP 服务，版本与 Python 客户端对应（当前 1.5.9）。
- DeepSeek 和硅基流动密钥，或其他兼容接口。

所有命令均从 仓库根目录 开始，后端各终端需进入 `backend/`。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 仅首次创建配置时复制；已经有 .env 时不要覆盖
Copy-Item .env.example .env
```

编辑 `backend/.env`：

```dotenv
DATABASE_URL=mysql+pymysql://campus:你的密码@127.0.0.1:3306/backend
JWT_SECRET_KEY=使用至少32字节的随机密钥
LLM_API_KEY=你的DeepSeek密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_EXTRA_BODY={}
EMBEDDING_API_KEY=你的硅基流动密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8002
MCP_URL=http://127.0.0.1:8001/mcp
MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_TIMEOUT_SECONDS=20
```

数据库 URL 中的密码若含 `@`、`:` 等保留字符，需要 URL 编码。切换模型服务时同时设置地址、模型名和相应密钥。所选聊天模型必须支持工具调用和流式输出。

默认采用 DeepSeek 当前文档中的 `deepseek-flash`，通过 `thinking.type=disabled` 使用非思考模式；仅在 DeepSeek 官方域名下自动附加该参数。`LLM_EXTRA_BODY` 可以覆盖兼容服务的额外 JSON 参数。请求显式使用 Chat Completions 和 `max_tokens`，避免 LangChain 将其改写成兼容服务不支持的 OpenAI 专用参数。

### 数据服务

已有 MySQL 时，创建空库 `backend` 后直接使用；不要重复执行带 `DROP TABLE` 的旧演示 SQL。

可选使用 Docker 启动 MySQL 和 Chroma：在 仓库根目录 复制根目录 `.env.example` 为 `.env`，填写 `MYSQL_PASSWORD` 与 `MYSQL_ROOT_PASSWORD`，再运行：

```powershell
docker compose up -d mysql chroma
```

若使用本机 MySQL，只启动 Chroma 也需要填写 Compose 引用的变量（Compose 会先解析整个配置）：

```powershell
docker compose up -d chroma
```

数据保存在 Docker named volumes 中。默认端口只绑定本机。不要使用 `docker compose down -v` 清理有用数据。

### 数据库初始化

在 `backend/`：

```powershell
.\.venv\Scripts\python.exe -m app.init_db --admin campus_admin
```

密码通过交互输入，不出现在命令行参数中。该命令创建缺失的表；账号已存在时不会重置密码或修改权限。FastAPI 启动也会创建缺失的表。

本次新增独立表，不修改原 `users` 表结构。`create_all` 不负责已有表的字段迁移；后续更改模型字段需另行提供迁移，不能认为重启会自动升级表结构。

### 启动应用（三个终端）

终端 1，`backend/`：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

终端 2，`backend/`：

```powershell
.\.venv\Scripts\python.exe -m app.mcp_server
```

终端 3，`frontend/`：

```powershell
npm ci
npm run dev
```

打开前端终端显示的地址（通常 `http://localhost:5173`）；API 文档在 `http://127.0.0.1:8000/docs`。原有 `VITE_API_BASE_URL` 与 Vite 的 `/api`、`/uploads` 代理继续兼容。

### MCP 课表工具与 Inspector 验证

FastMCP 已固定在 `backend/requirements.txt`。独立进程读取同一份 `backend/.env`，监听 `MCP_HOST:MCP_PORT`；Agent 通过 `MCP_URL` 连接，修改端口时两处需保持一致。默认仅监听本机 `127.0.0.1:8001`，路径 `/mcp`。课表查询不依赖模型密钥、Embedding 或 Chroma。

`get_my_schedules(on_date?: YYYY-MM-DD)` 返回 `{"schedules": [...], "total": 1}`。每条包含课程 ID、名称、教师、星期、开始/结束时间、有效日期、地点和备注，日期和时间已转为 JSON 字符串。省略日期返回所有个人排课；指定日期同时过滤星期与有效日期范围。无课返回空数组，非法日期返回工具校验错误。`schedule_service.schedule_to_dict` 只输出公开课表字段，不包含学生身份和账号数据。旧 `query_schedule` 保持 `{"courses": [...]}` 返回格式。

从 `backend/` 安装固定版本 Inspector（独立开发依赖）：

```powershell
npm ci --prefix tools/mcp-inspector
npm --prefix tools/mcp-inspector run inspector -- --server-url http://127.0.0.1:8001/mcp --transport http
```

在 Inspector 使用 Streamable HTTP，配置请求头 `Authorization: Bearer <登录 token>`。token 来自 `POST /api/auth/login` 响应的 `data.token`，不是账号密码或 JWT 密钥。连接后执行 Tools → List Tools → `get_my_schedules`，输入 `{}` 或 `{"on_date":"2026-10-22"}`。切换另一个账号的 token 后重新连接，确认只能看到该账号课表；不带 token 应返回 401。请勿把真实 token 写入版本库或截图分享。

也可运行可重复的 Inspector CLI 验收：

```powershell
.\.venv\Scripts\python.exe tests/verify_mcp_inspector.py
```

该脚本启动独立 MCP 子进程，使用临时 SQLite 中 Alice/Bob 账号通过真实登录接口取得 token，并调用官方 Inspector CLI 验证工具发现、日期筛选、有效日期范围、无课结果及用户隔离；还验证无 token 被拒绝。token 只写入临时配置，结束后清理，不修改现有 MySQL 账号或密码。这是隔离验收，不代表已经知道本机真实账号的密码。

### FastAPI → MCP Client → FastMCP → Service 验证

新增 `GET /api/mcp/my-schedules?on_date=2026-10-22`（日期可省略）。`app/services/mcp_client.py` 使用已固定版本的 `langchain-mcp-adapters`，每次请求创建独立客户端，连接 `MCP_URL`，先发现工具再调用 `get_my_schedules`。FastAPI 验证当前登录账号后，将本次请求的原始 `Authorization` 同时用于工具发现和调用，不重新签发凭证、不传 `user_id`，不缓存带身份的工具或客户端。原有 Agent 的短时工具凭证流程保持兼容。

返回格式：`{"code":200,"message":"请求成功","data":{"schedules":[],"total":0}}`。MCP 返回的时间/日期统一为 JSON 字符串。未登录或账号禁用返回 401；非法日期返回 422；上游鉴权失败返回 401；服务不可达返回 503；超时返回 504；工具缺失、执行失败或响应格式不正确返回 502。错误响应不包含 token 或内部异常详情。`MCP_TIMEOUT_SECONDS` 默认 20 秒，涵盖工具发现和调用。

在 Swagger 中切换 aaa / bbb：

1. 确认 FastAPI（8000）和独立 MCP（8001）均已启动，刷新 `http://127.0.0.1:8000/docs`。
2. 执行 `POST /api/auth/login`，使用 aaa 的实际密码，取得 `data.token`。
3. 点击新接口旁的小锁，找到 **LoginJWT (http, Bearer)**，只粘贴完整 token（不加 `Bearer`），点击 **Apply credentials**（部分 Swagger 版本显示 Authorize）→ Close。无需使用原 OAuth2PasswordBearer 的账号密码表单。
4. 展开 **MCP 课表查询 → GET /api/mcp/my-schedules**，点击 Try it out。先清空日期查询全部个人课表，再填写日期查询；将 `data.schedules` 与相同学生的「我的课表」核对。
5. 使用 bbb 的实际密码重新登录；在 Authorize 的 LoginJWT 中先 Logout，再填写 bbb 的新 token，重复查询。aaa 的排课不能出现在 bbb 的结果中。若 bbb 未排课，应返回空数组和 total=0；仅创建课程不等于给学生排课。
6. 再切回 aaa，确认不会沿用 bbb 的身份；清除 LoginJWT 后执行应返回 401。不要在请求里传学生 ID。

自动化回归使用临时数据库中的 aaa/bbb 测试账号和真实独立 MCP 进程，验证原始 header 转发、来回切换身份、日期过滤、与 Service 直查结果一致及 Swagger 的 LoginJWT 配置。测试账号及密码仅存在于临时数据库，不代表真实 MySQL 账号已创建或重置。

### ReAct 完整对话接口与 Swagger 验证

`POST /api/chat/ask` 复用现有 `ChatOpenAI` 模型配置，通过 `create_agent` 执行模型 → 工具 → 模型循环，等待最终回答后一次性返回 JSON。使用 `backend/.env` 中的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 和可选 `LLM_EXTRA_BODY`；当前默认兼容 DeepSeek。`AGENT_TIMEOUT_SECONDS` 限制总时长，`AGENT_RECURSION_LIMIT` 限制循环步数。

请求：

```json
{
  "question": "查询我的全部课表",
  "history": []
}
```

响应：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {"answer": "这里是模型根据当前用户课表生成的完整回答"}
}
```

历史消息按先后顺序传入，仅允许 `user` / `assistant`，最多 20 条，每条及问题最多 6000 字符，总上下文最多 60000 字符，拒绝空白、system/tool 角色和伪造 tool_calls。此接口不写数据库会话，调用方维护历史；现有会话 SSE 接口保持不变。只加载只读 `get_my_schedules` 工具，逐请求转发原始 Authorization；模型、历史及请求体都不能指定查询用户。课表追问仍应重新查询，历史回答不能当作本轮课表事实。

Swagger 操作：

1. 打开 `http://127.0.0.1:8000/docs`，通过 `/api/auth/login` 获取学生 token。
2. 在 **智能助手 → POST /api/chat/ask** 右侧点小锁，选择 **LoginJWT**，粘贴 token（不加 Bearer），点击 **Apply credentials** → Close。
3. 点击 Try it out，执行上述首次查询，核对 `data.answer` 与「我的课表」一致。
4. 第二轮使用下例，将 assistant.content 替换成第一轮真实的 data.answer：

```json
{
  "question": "这些课分别在哪间教室？",
  "history": [
    {"role": "user", "content": "查询我的全部课表"},
    {"role": "assistant", "content": "第一轮返回的真实回答"}
  ]
}
```

5. 换另一学生登录。在 LoginJWT 中点击 **Remove authorization**，填写新 token，再执行相同问题；新的对话使用空 history，后续仅携带这个账号的历史。无排课账号应得到无排课的说明，不能得到其他账号的课表。
6. 移除授权应返回 401；空白问题或非法历史返回 422；缺少模型密钥返回 503；MCP 不可达返回 503、鉴权失败返回 401；总执行超时返回 504；模型失败、空回答或循环超限返回 502。失败响应不暴露凭证或内部异常详情。

开发验收已使用临时数据库、真实独立 FastMCP 和确定性测试模型，在 Swagger 实际验证首轮查询、多轮追问及 aaa/bbb 切换隔离；也验证了原始 JWT 转发与现有 SSE 回归。该验收不调用真实模型供应商，不代表 DeepSeek 密钥、额度或模型名称已经通过远程调用验证。真实账号与排课需要在本机数据库中单独准备。

### SSE 流式课程助手

新增页面 `/manager/course-assistant`，菜单「课程助手」。原有「智能助手」的会话、资料检索和计划功能保留。新页面使用 `POST /api/chat/stream`，请求体与 `/api/chat/ask` 相同：`{"question":"查询我的课表","history":[]}`，继续用本次请求的 JWT 确定查询身份。

服务端使用 `agent.astream_events(..., version="v2")`，只把公开状态、工具执行状态与模型正文投影为 SSE；不会直接透传整个 LangChain 事件、请求头、工具输入或私人推理。响应头为 `text/event-stream`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`，空闲时每 15 秒发送注释心跳。

| SSE 事件 | data 字段 | 页面行为 |
| --- | --- | --- |
| status | message | 显示连接、理解问题、查询、整理回答等状态 |
| tool_start | id、name、status | 显示工具进行中 |
| tool_end | id、name、status、summary | 更新同一个工具的结果状态及查询条数 |
| token | text | 增量显示 Markdown，使用现有 marked + DOMPurify 安全渲染 |
| error | message、code | 显示失败提示，本轮不加入历史 |
| done | success、成功时的 answer | 成功后用最终 answer 校正正文，确认本轮完成 |

鉴权、请求格式和模型密钥检查在开始 SSE 前返回 HTTP 401/422/503；开始后发生的 MCP、模型或超时错误通过 error 和 `done.success=false` 返回。客户端必须同时处理 HTTP 失败、SSE error 和未收到 done 的断线。原生 EventSource 不支持本接口的 POST/JWT 头，页面使用 fetch + ReadableStream；现有 SSE 解析器支持中文跨字节分片、CRLF 和心跳。

后续追问只携带此前成功完成的问答，按 user/assistant 成对排列，最多最近 10 对，且遵守服务端每条 6000 字符和总计 60000 字符限制。超长或未完成的问答不会带入历史；新对话清空本页内容，刷新页面也会清空。停止、失败、断线的局部回答可见，但明确标注未加入历史。客户端断开或点击停止会取消请求并关闭服务端事件迭代器。

页面验收：先问「查询我的全部课表」，检查状态、工具完成和 Markdown 回答，再问「这些课在哪间教室？」；页脚的成功问答数量应递增。点击停止或模拟失败后，计数应保持不变，下一轮继续携带此前的成功问答。切换用户重新进入页面，不能沿用上一账号的本页历史。Swagger 可查看接口及 SSE 原文；观察实时效果请使用课程助手页面。

### 管理员课程资料管理

新增 `kb_documents` 表：`file_name` 原名称、`file_path` 私有存储相对位置、`file_size` 实际字节数、`file_type` 文件类型、`text_content` 提取的预览文本，以及 ID 和创建/修改时间。原文件放在 `backend/data/kb_documents/<批次UUID>/<文件UUID>.<类型>`，不会通过 `/uploads` 暴露。前端菜单「课程资料管理」，路径 `/manager/kb-documents`，只向管理员显示，路由和全部后端接口均校验管理员权限。

接口：

| 方法与路径 | 用途 |
| --- | --- |
| POST /api/admin/kb-documents/batch | multipart 多个同名 `files` 字段，整批上传 |
| GET /api/admin/kb-documents | page/page_size/keywords 分页和文件名搜索，返回 data.list/total |
| GET /api/admin/kb-documents/{id}/preview | 返回 data.file_name/content，前端以转义的纯文本显示 |
| DELETE /api/admin/kb-documents/{id} | 删除元数据与原文件，未知 ID 返回 404 |

每批 1–20 个文件，单个最多 10MB，整批最多 50MB；支持 PDF、DOCX、UTF-8 TXT、Markdown。复用已有解析器：PDF 不得加密，最多 100 页，扫描 PDF 需先 OCR；DOCX 解压限制 30MB；提取文本上限 60KB，空文本不接受。同名原文件使用不同 UUID 保存，不覆盖已有文件。上传只存储原文件、元数据和预览文本，不调用模型、Embedding 或 Chroma，也不会自动合入个人 RAG 资料。

批量上传先写入独立批次目录，全部解析、写入和数据库 flush 成功后仅提交一次。任一后续文件无效、磁盘写入失败、数据库提交失败，均回滚本批记录并删除该批目录；此前成功的批次不受影响。若清理本身失败，会明确返回需要管理员处理的错误。数据库事务与文件系统采用失败补偿，不是跨系统事务；进程被强制终止等异常可能遗留无记录目录，需在维护时核对清理。

删除先把原文件改名隔离，数据库提交失败时恢复原文件；成功后清理隔离文件。清理文件遇到系统错误时，返回 `cleanup_pending=true`，页面会提示管理员处理，隔离文件不会通过资料接口读取。资料未与向量索引关联，不需要先删除索引。

验收：用管理员选择多份有效文档整批上传，核对数量、名称、大小、类型和预览；再将有效 TXT 与损坏 PDF 一起上传，应整批失败且列表数量不变。学生即使直接请求接口也应返回 403，未登录返回 401，禁用账号返回 401。自动化测试还覆盖磁盘写入失败、数据库提交失败、删除回滚、目录越界防护和已有资料保留，所有测试使用临时数据库与目录。

启动后端时 `create_all` 会创建缺失的 `kb_documents` 表，不会重建或覆盖旧表；本次无需迁移已有个人 `documents` 数据。实际 MySQL 建表需先启动数据库服务，离线 SQLite 验收不代表已写入真实 MySQL。

## 关键接口与事件

| 接口 | 用途 |
| --- | --- |
| POST /api/chat/ask | 接收 question/history，ReAct Agent 调用 MCP 后返回完整 data.answer |
| POST /api/chat/stream | 同样接收 question/history，以 SSE 返回状态、工具过程、正文片段及完成标记 |
| GET /api/courses | 当前用户可访问的课程信息，兼容 on_date 时按课表关联课程筛选 |
| GET /api/schedules/me?on_date=2026-10-22 | 当前用户个人课表，日期可省略 |
| GET /api/admin/schedules?student_id=1&on_date=2026-10-22 | 管理员课表查询，支持分页、学生、日期、课程过滤 |
| GET /api/admin/schedules/{id} | 管理员课表详情 |
| POST /api/admin/schedules；PUT/DELETE /api/admin/schedules/{id} | 管理员课表 CRUD |
| GET /api/admin/schedules/student-options?keywords=aaa | 学生选择项，只返回学生角色，最多 30 条 |
| GET /api/admin/courses?page=1&page_size=10&keywords=数学 | 管理员课程列表，支持 user_id 过滤 |
| GET /api/admin/courses/{id} | 管理员课程详情 |
| POST /api/admin/courses；PUT/DELETE /api/admin/courses/{id} | 管理员课程 CRUD，请求包含所属用户 user_id |
| POST /api/courses；PUT/DELETE /api/courses/{id} | 兼容旧路径，仅管理员可写自己的课程 |
| GET/POST /api/documents | 资料列表、multipart 上传 |
| GET/DELETE /api/documents/{id} | 私有原文预览、删除 |
| POST /api/documents/{id}/index | 重建索引 |
| POST /api/documents/search | 检索原文片段 |
| GET /api/study-plans?page=1&page_size=10 | 当前 JWT 用户的学习计划分页，按创建时间倒序 |
| POST /api/study-plans；DELETE /api/study-plans/{id} | 保存新计划、删除自己的计划 |
| PATCH /api/study-plans/{id} | 更新自己的计划完成状态 |
| GET/POST /api/plans；PATCH/DELETE /api/plans/{id} | 兼容旧学习计划接口，GET 保留数组结构 |
| GET/POST /api/chat/sessions | 对话列表、新建 |
| GET /api/chat/sessions/{id}/messages | 持久化消息、工具状态和检索来源 |
| POST /api/chat/sessions/{id}/stream | SSE 流式对话 |

SSE 事件：`status`、`tool_start`、`tool_end`、`token`、`sources`、`error`、`done`。每 15 秒发送注释心跳，前端使用 fetch 解析，支持中文跨字节分片。`error` 不回传底层异常或凭证，`done.success` 标识本轮是否成功。

单个会话使用数据库原子租约，拒绝并发生成；异常、断连和停止会释放租约，崩溃遗留租约在超时后可恢复。停止不会撤销已经执行的工具操作，界面有明确提示。模型的私人推理不通过 SSE 发送。

## 验证

[2026 年 11 月 8 日功能验收](test-results/2026-11-08-functional-test.md)记录了 31 条真实环境 API 用例通过，以及后端 59 项和前端 6 项自动化测试通过。真实环境覆盖 MCP、Chroma、Embedding 和聊天模型链路。停止生成及服务故障恢复使用隔离测试，浏览器页面细节待人工复核。以下命令用于复验。

```powershell
# backend/：使用临时 SQLite 和真实独立 MCP 子进程，不读取真实模型密钥
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check

# frontend/
npm test
npm run build
```

后端测试覆盖原账号登录注册、新接口身份校验、课程日期过滤、跨用户课程/计划/文档/会话权限、索引失败、检索结果二次权限校验、会话并发保护、真实 MCP HTTP 工具加载及保存计划，以及确定性测试模型驱动的 LangChain → MCP → SSE 完整编排。Embedding 与向量存储的离线测试使用替身，不等同于真实服务验收。

真实服务验收：

1. 注册两个学生账号，由管理员创建课程，再在“课表管理”为两个学生分别排课；确认学生只看到自己的“我的课表”，访问管理 API 返回 403。
2. 测试开始日、结束日、非上课日以及有效日期范围外的查询；删除有排课的课程应返回 409，清理课表后才能删除（若有资料需另行清理）。
3. 上传一份含“考核占比”等具体事实的课程文档，确认状态为“可检索”。
4. 在“检索试验台”确认原文命中，再问助手考核方式，检查引用与展开的原文片段。
5. 问课表，再明确要求“制定并保存复习计划”，在计划页确认记录。
6. 刷新聊天页，确认会话、工具结果、来源仍在。
7. 切换账号，确认课表、文档、计划、会话相互隔离。
8. 分别停止 MCP / Chroma，确认前端展示失败而不是编造成功；恢复服务后重试。

## 已知边界

- PDF 为文本提取，不包含 OCR；PDF 文本片段保留页码标记，DOCX 包括段落与表格文本，暂不保证原排版顺序。
- 单文件最大 10MB、PDF 最多 100 页、提取文本最大 60KB，避免同步索引占用过多资源；失败文档可重建索引。
- 当前索引同步执行，小规模课程资料适用；大量资料需改为任务队列并增加用户配额。
- 聊天保留数据库历史，每次最多携带最近 20 条消息；尚未实现长对话摘要。
- 引用展示的是实际检索结果，仍需核对模型是否正确解读原文；资料中的指令作为不可信数据处理。
- `langchain-mcp-adapters` 官方仓库已停止维护，按本项目选型保留；连接封装在 `agent_service.py`，未来可迁移到 `langchain.mcp`。
- 生产部署需 HTTPS、反向代理 SSE 禁用缓冲、访问限流、数据库迁移、备份与审计。Chroma 与 MCP 应保留在服务端网络，不向浏览器或公网直接开放。

## 官方接口参考

- [LangChain streaming](https://docs.langchain.com/oss/python/langchain/streaming)
- [LangChain MCP adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [FastMCP HTTP deployment](https://gofastmcp.com/deployment/http)
- [Chroma client/server mode](https://docs.trychroma.com/docs/run-chroma/client-server)
- [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
