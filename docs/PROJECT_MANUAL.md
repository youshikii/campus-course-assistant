# 校园课程智能助手项目说明书

> 文档版本：1.1  
> 更新日期：2026 年 11 月 8 日  
> 适用范围：当前项目代码实现；适用于项目介绍、课程设计展示、部署交接与功能验收。

## 一、项目概述

### 1.1 项目名称

校园课程智能助手——基于 Vue 3、FastAPI、MCP、LangChain Agent 与 RAG 的全栈应用。

### 1.2 建设背景

学生日常学习需要在课程安排、课程资料、学习计划之间反复切换。传统管理系统能够保存数据，但查询通常依赖固定页面，难以围绕自然语言问题串联多个操作。通用聊天模型能够生成文字，却无法直接了解学生的真实课表和个人资料，也不能自行判断数据访问权限。

本项目在已有 FastAPI + Vue 3 业务脚手架基础上，增加课程与课表管理、个人资料检索、学习计划以及 AI 对话能力。通过独立 MCP 服务将受权限约束的业务操作开放为工具，由 Agent 根据问题选择工具，以真实业务数据和检索片段辅助回答。

### 1.3 建设目标

1. 为学生提供统一的课程查询、资料检索、计划管理和自然语言交互入口。
2. 为管理员提供课程、学生排课、用户和课程资料文件的管理能力。
3. 打通“网页 → FastAPI → LangChain Agent → MCP → 业务服务”的调用链。
4. 通过 JWT 和数据库归属条件实现个人数据隔离，避免模型决定查询身份。
5. 使用 SSE 展示处理状态、工具执行过程及回答文字，提高交互可见性。
6. 保持业务服务、工具协议和模型编排分层，便于维护与后续扩展。

### 1.4 当前范围

已包含账号与权限、学习概览、课程管理、独立课表、学习计划、个人资料 RAG、管理员资料管理、课表对话及多会话智能助手。

当前未实现教务系统同步、教师角色、单双周课表、OCR、联网搜索、自动提醒和管理员资料的学生共享检索。本文将这些内容列为扩展方向，不计入已实现功能。

## 二、用户角色与权限

系统包含 `student`（学生）和 `admin`（管理员）两种角色。自行注册的账号固定为学生，管理员账号通过初始化流程或已有管理机制维护。

| 功能 | 学生端 | 管理端 |
| --- | --- | --- |
| 登录、个人信息、头像、修改密码 | 使用自己的账号 | 使用自己的账号 |
| 学习概览 | 查看个人统计、今日课程与待完成计划 | 查看个人学习空间信息 |
| 我的课程 | 只读查看自己可访问的课程 | 可使用个人课程入口 |
| 我的课表 | 只查询本人课表，可选日期 | 个人入口仍按当前账号查询 |
| 学习计划 | 保存、分页查询、删除及切换本人计划状态 | 同样仅操作本人的计划 |
| 课程资料库 | 上传、预览、检索、重建索引及删除本人的资料 | 同样使用自己的私有资料库 |
| 课程助手 | 基于本人课表的流式问答与连续追问 | 按当前账号身份使用 |
| 智能助手 | 本人课表、个人资料检索、计划查询与明确要求后的计划保存 | 按当前账号身份使用 |
| 课程管理 | 无权限 | 课程列表、详情、新增、修改、删除 |
| 课表管理 | 无权限 | 排课 CRUD，按学生、日期和课程筛选 |
| 课程资料管理 | 无权限 | 批量上传、列表搜索、纯文本预览和删除 |
| 用户管理 | 无权限 | 用户维护 |

管理员跨学生查看排课应使用“课表管理”及其管理接口。个人助手不会因为账号是管理员而自动开放他人的私有文档、学习计划或对话。

前端通过菜单和路由守卫控制页面入口；后端独立校验 JWT、账号状态及角色，个人数据查询额外限定所属用户。隐藏菜单不能替代后端鉴权。

## 三、技术架构

### 3.1 技术选型

| 层级 | 技术 | 职责 |
| --- | --- | --- |
| 前端 | Vue 3、Element Plus、Vite、Vue Router、Axios | 页面、表单、表格、路由与业务请求 |
| 回答渲染 | marked、DOMPurify | Markdown 解析与 HTML 清洗 |
| 业务后端 | FastAPI、Pydantic、SQLAlchemy、MySQL | 接口、参数校验、业务规则与数据存储 |
| 身份认证 | JWT、bcrypt | 登录凭证签发校验与密码哈希 |
| 模型接入 | langchain-openai / ChatOpenAI | 使用 OpenAI 兼容 Chat Completions 接口 |
| 智能编排 | LangChain `create_agent`，底层基于 LangGraph | 根据上下文选择工具并组织回答 |
| 工具服务 | FastMCP 独立进程 | 通过 Streamable HTTP 暴露业务工具 |
| MCP 客户端 | langchain-mcp-adapters | 加载工具、携带凭证并完成工具调用 |
| 流式传输 | SSE、fetch、ReadableStream | 推送状态、工具事件与回答片段 |
| 检索增强 | Chroma HTTP、Embedding、文本分块 | 文档向量化与相似片段检索 |
| 文档解析 | pypdf、python-docx | 提取 PDF、DOCX 文本；另支持 UTF-8 TXT、Markdown |

聊天模型默认配置为 DeepSeek 兼容接口，Embedding 默认配置为硅基流动的 `BAAI/bge-m3`。模型名称、地址与密钥均由后端环境变量控制，具体可用性需在部署环境实测。

### 3.2 系统结构

```mermaid
flowchart TD
    U[学生 / 管理员] --> V[Vue 3 网页]
    V -->|JWT + REST / POST SSE| F[FastAPI 业务服务]
    F --> S[业务 Service]
    S --> DB[(MySQL)]
    F --> A[LangChain Agent]
    A --> L[OpenAI 兼容聊天模型]
    A --> C[MCP Client]
    C -->|HTTP + 身份凭证| M[独立 FastMCP 服务]
    M --> S
    S --> R[RAG 检索服务]
    R --> E[Embedding 服务]
    R --> CH[(Chroma HTTP)]
    S --> FS[管理员资料私有文件目录]
```

FastAPI 和 FastMCP 共用业务服务代码及数据服务，但分别运行。浏览器通过 FastAPI 访问业务功能，模型 API 密钥保留在服务端。Chroma 使用独立 HTTP 服务，避免多个进程同时打开同一本地嵌入式数据库。

### 3.3 工程分层

```text
campus-course-assistant/
├── backend/
│   ├── app/
│   │   ├── api/             # REST、SSE 与管理接口
│   │   ├── services/        # 课程、课表、计划、文档、Agent 等服务
│   │   ├── models/          # SQLAlchemy 数据模型
│   │   ├── schemas/         # 请求和响应结构
│   │   ├── dependencies/    # JWT 与角色依赖
│   │   ├── common/          # 统一返回与异常处理
│   │   ├── utils/           # JWT、密码与工具凭证等
│   │   ├── mcp_server.py    # 独立 MCP 入口
│   │   ├── init_db.py       # 非清空式建表与管理员初始化
│   │   └── main.py          # FastAPI 入口
│   ├── data/kb_documents/   # 管理员资料原文件的私有目录
│   ├── tests/               # 隔离数据库与 MCP 集成测试
│   ├── tools/mcp-inspector/ # MCP 调试工具
│   └── .env.example         # 后端配置模板
├── frontend/
│   ├── src/api/             # 接口封装
│   ├── src/views/           # 业务页面
│   ├── src/layouts/         # 菜单与页面框架
│   ├── src/utils/           # 身份、SSE、历史消息等工具
│   └── tests/               # SSE 与历史处理测试
├── sql/                     # 初始化与部分独立建表脚本
├── docs/                    # 开发指南与项目说明书
└── compose.yaml             # MySQL / Chroma 容器配置
```

## 四、功能模块

### 4.1 账号与个人中心

支持登录、注册、个人信息维护、头像和密码修改。登录成功返回 `data.token`，后续业务请求使用 `Authorization: Bearer <登录token>`。密码以 bcrypt 哈希存储。受保护接口检查账号是否存在、是否启用。

### 4.2 课程与课表管理

课程管理支持管理员分页搜索、查看详情、新增、修改和删除课程。学生在“我的课程”查看自己归属或排课关联的可访问课程。

`courses` 保存课程信息；`schedules` 通过 `course_id` 关联课程，并记录学生、星期、时段、有效日期和地点。一门课程可以对应多条排课。课程表中的旧归属和时间字段为历史兼容保留，实际排课以 `schedules` 为准。

学生查询自己的课表时可选择日期；未指定日期则列出全部排课。指定日期时，必须同时满足星期匹配和起止日期范围，开始日与结束日均包含在内。当前按每周重复处理，不支持跨午夜时段，也未自动阻止课程时间重叠。

管理员可按学生、日期、课程筛选课表并进行 CRUD。仅学生角色可被分配课表。已有排课的课程禁止删除；存在关联资料时，课程删除等操作也受保护。

### 4.3 学习计划

页面上方填写标题、内容与可选目标日期，下方按创建时间倒序分页展示。支持新增保存、删除及待完成/已完成状态切换。计划内容支持安全 Markdown 渲染。

所有计划操作限定当前 JWT 用户。智能助手仅在用户明确要求保存时调用保存工具，只有工具返回成功才能宣称已保存。

### 4.4 个人课程资料库与 RAG

支持 PDF、DOCX、UTF-8 TXT 和 Markdown，可关联有权限访问的课程。上传后提取文本、分块、调用 Embedding 并写入 Chroma；数据库保存文档归属、正文、索引状态、片段数量和错误信息。索引失败后可重建。

处理链路为：

```text
上传个人文档 → 提取文本 → 分块（800 字符，重叠 120 字符）
    → Embedding → Chroma 保存片段及归属元数据

用户问题 → 问题向量化 → 按当前用户和可用文档过滤检索
    → SQL 权限复核 → 返回原文片段与引用标识 → 模型组织回答
```

检索工具提供实际片段和形如 `[资料ID-片段N]` 的引用标识，智能助手页面展示来源，便于核对回答依据。无匹配结果时，提示词要求模型明确说明缺少资料；模型对片段的理解仍需人工核对。

单文件上限 10MB，PDF 最多 100 页且不能加密，提取文本上限 60KB；DOCX 有解压大小限制。扫描 PDF 需要先进行 OCR。当前个人资料库保留提取文本，并不提供与管理员模块相同的原文件归档机制。

### 4.5 管理员课程资料管理

管理员在独立页面批量上传、搜索分页列表、预览提取的纯文本和删除资料。`kb_documents` 记录文件名、相对存储位置、实际字节数、文件类型和预览文本。原文件存于私有目录，使用 UUID 命名，不通过公开 `/uploads` 暴露。

每批 1–20 个文件，单文件最多 10MB，整批最多 50MB。全部文件解析和写入成功后统一提交数据库；任一文件无效、磁盘写入失败或数据库提交失败时，回滚本批记录并清理本批文件，保留此前成功批次。

删除先隔离原文件，再提交数据库删除；提交失败则恢复文件。提交成功但后续文件清理失败时返回 `cleanup_pending=true`，页面提示管理员处理。数据库和文件系统通过失败补偿保持一致，强制终止进程仍可能产生需要维护清理的孤立文件。

**本模块当前只提供资料文件管理与预览，没有向量化，也未接入学生共享 RAG。** 个人 `documents` 与管理员 `kb_documents` 是两条独立的数据链路。

### 4.6 课程助手与智能助手

| 维度 | 课程助手 | 智能助手 |
| --- | --- | --- |
| 页面 | `/manager/course-assistant` | `/manager/assistant` |
| 工具范围 | 仅 `get_my_schedules` | 个人课表、资料检索、计划查询和保存 |
| 交互 | SSE 流式问答；另提供完整回答 API | 多会话 SSE 对话 |
| 历史 | 页面内保存成功问答，刷新清空 | 数据库存储会话与消息 |
| 凭证 | 转发本次请求原始 Authorization | 按当前用户签发短时 MCP 工具 JWT |
| 适用场景 | 查课表、问时间地点、连续追问 | 围绕课表、个人资料和计划综合问答 |

课程助手的后续追问最多携带最近 10 对成功问答，并受单条和总长度约束。失败、停止和断线产生的局部回答不加入后续历史。涉及课表事实时要求重新查询工具，客户端历史只作为理解上下文的材料。

智能助手支持会话持久化、工具状态及检索来源记录。同一会话使用数据库租约阻止并发生成。停止生成会取消请求，但不会撤销已经成功执行的工具写入，例如已保存的计划。

## 五、Agent、MCP 与 SSE 设计

### 5.1 Agent 工作流程

1. FastAPI 验证用户身份与问题格式，构建允许的历史消息。
2. 创建本次运行独立的 MCP 客户端，加载相应工具。
3. 使用 `create_agent` 构建 Agent，由模型判断是否需要工具及后续调用。
4. MCP 服务校验凭证，从服务端确定用户，调用业务 Service。
5. 工具结果回传 Agent，模型继续调用工具或生成最终回答。
6. 完整回答接口返回 `data.answer`；流式接口持续推送事件。

该流程采用 ReAct 式工具迭代，但网页只展示处理状态、工具过程和回答，不展示模型私人推理。

### 5.2 MCP 工具

| 工具 | 输入要点 | 能力 |
| --- | --- | --- |
| `get_my_schedules` | 可选 `on_date` | 查询当前用户课表，返回 `schedules` 与 `total` |
| `query_schedule` | 可选日期 | 保留旧课表工具兼容入口 |
| `search_materials` | 问题、可选课程及数量 | 检索当前用户个人资料，返回片段与来源 |
| `list_study_plans` | 分页参数 | 查询当前用户学习计划 |
| `save_study_plan` | 标题、内容、可选目标日期 | 保存当前用户明确要求保存的计划 |

工具输入不开放用于选择身份的 `user_id`。FastMCP 从 Authorization 解析 JWT，并检查数据库账号状态。登录 JWT 和带 `aud=campus-mcp` 的短时工具 JWT 均有对应校验，不接受任意 audience。

### 5.3 SSE 事件

课程助手使用 `astream_events(version="v2")` 读取模型和工具事件；多会话智能助手使用 Agent 的消息与更新流。

| 事件 | 网页用途 |
| --- | --- |
| `status` | 显示连接、查询、生成等处理状态 |
| `tool_start` | 显示工具开始执行 |
| `tool_end` | 更新工具完成或失败状态 |
| `token` | 增量展示回答文字 |
| `sources` | 智能助手展示检索来源 |
| `error` | 展示失败提示 |
| `done` | 标记本轮成功或失败；课程助手成功时带最终回答 |

接口通过 POST 接收问题并携带 JWT，因此前端使用 fetch 读取事件流。服务端每 15 秒发送注释心跳；前端处理中文跨字节分片、CRLF、HTTP 错误、SSE 错误以及缺失完成事件的断线。

## 六、数据库设计

所有业务表继承公共 `id`、`create_time`、`update_time` 字段。下表列出核心字段，完整定义以 `backend/app/models/` 为准。

| 表 | 核心字段 | 作用 |
| --- | --- | --- |
| `users` | username、password、name、role、status、email、phone、avatar | 账号、角色及个人信息 |
| `courses` | user_id、name、teacher、旧地点与日期时间字段、notes | 课程信息及历史兼容 |
| `schedules` | student_id、course_id、weekday、start_time/end_time、start_date/end_date、location、notes | 实际学生排课 |
| `study_plans` | user_id、title、content、target_date、status | 个人学习计划 |
| `documents` | user_id、course_id、name、content、status、chunk_count、error | 私有资料及索引状态 |
| `kb_documents` | file_name、file_path、file_size、file_type、text_content | 管理员资料文件元数据与预览 |
| `chat_sessions` | user_id、title、run_token、run_started_at | 个人会话与生成租约 |
| `chat_messages` | session_id、role、content、sources、events | 对话消息、来源及工具事件 |

主要关系：用户对应多条课表、计划、私有文档与会话；课程对应多条课表及可选关联文档；会话对应多条消息。Chroma 保存文档片段向量和检索元数据，MySQL 作为业务归属与权限判断依据。

新库可以通过初始化命令或 FastAPI 启动创建缺失的表。`create_all` 不迁移已有表字段；历史课表迁移使用显式升级命令，详见开发指南。

## 七、主要接口

接口统一以 `/api` 开头，通常返回 `code`、`message`、`data`。分页接口一般在 `data` 下返回 `list` 和 `total`；SSE 接口使用事件流格式。完整请求字段以运行中的 Swagger 为准。

| 方法与路径 | 用途 | 权限 |
| --- | --- | --- |
| `POST /api/auth/login`、`POST /api/auth/register` | 登录、注册 | 公开 |
| `GET /api/courses` | 可访问课程列表 | 已登录 |
| `GET/POST /api/admin/courses` | 课程分页列表、新增 | 管理员 |
| `GET/PUT/DELETE /api/admin/courses/{id}` | 课程详情、修改、删除 | 管理员 |
| `GET /api/schedules/me` | 本人课表，可选日期 | 已登录 |
| `GET/POST /api/admin/schedules` | 管理端课表查询、新增 | 管理员 |
| `GET/PUT/DELETE /api/admin/schedules/{id}` | 排课详情、修改、删除 | 管理员 |
| `GET/POST /api/study-plans` | 本人计划分页列表、保存 | 已登录 |
| `PATCH/DELETE /api/study-plans/{id}` | 本人计划状态变更、删除 | 已登录 |
| `GET/POST /api/documents` | 私有资料列表、上传 | 已登录 |
| `GET/DELETE /api/documents/{id}` | 私有资料文本详情、删除 | 已登录 |
| `POST /api/documents/{id}/index` | 重建个人文档索引 | 已登录 |
| `POST /api/documents/search` | 检索个人资料 | 已登录 |
| `GET /api/admin/kb-documents` | 管理员资料分页与搜索 | 管理员 |
| `POST /api/admin/kb-documents/batch` | 整批上传 | 管理员 |
| `GET /api/admin/kb-documents/{id}/preview` | 纯文本预览 | 管理员 |
| `DELETE /api/admin/kb-documents/{id}` | 删除资料 | 管理员 |
| `GET /api/mcp/my-schedules` | 验证 FastAPI → MCP → Service | 已登录 |
| `POST /api/chat/ask` | 课表 Agent 完整回答 | 已登录 |
| `POST /api/chat/stream` | 课表 Agent SSE 回答 | 已登录 |
| `GET/POST /api/chat/sessions` | 个人会话列表、新建 | 已登录 |
| `GET /api/chat/sessions/{id}/messages` | 个人会话历史 | 已登录 |
| `POST /api/chat/sessions/{id}/stream` | 多工具智能助手 SSE | 已登录 |

课表完整回答请求示例：

```json
{
  "question": "这些课在哪间教室？",
  "history": [
    {"role": "user", "content": "查询我的全部课表"},
    {"role": "assistant", "content": "这里填写上一轮成功返回的实际回答。"}
  ]
}
```

## 八、部署与运行

### 8.1 环境要求

- Python 3.12+；应与安装的依赖兼容。
- Node.js 满足项目 `engines`：`^22.18.0 || >=24.12.0`。
- MySQL 8+。
- Chroma HTTP 服务；项目 Compose 使用 1.5.9。
- 支持工具调用和流式输出的 OpenAI 兼容聊天模型，以及可用的 Embedding 服务。

### 8.2 后端配置

从仓库根目录进入 `backend/`，首次安装：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

填写 `backend/.env`，以下仅为占位示例：

```dotenv
DATABASE_URL=mysql+pymysql://campus:数据库密码@127.0.0.1:3306/backend
JWT_SECRET_KEY=替换为足够长的随机密钥
LLM_API_KEY=聊天服务密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
EMBEDDING_API_KEY=向量服务密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8002
MCP_URL=http://127.0.0.1:8001/mcp
MCP_HOST=127.0.0.1
MCP_PORT=8001
```

JWT 密钥由本项目生成和保管，不是模型平台 API Key。模型和 Embedding 密钥分别来自对应服务商。数据库密码若含 URL 保留字符需编码；真实 `.env` 不应公开。

### 8.3 数据服务与账号初始化

先启动本机 MySQL 并创建配置中的数据库。也可使用项目 `compose.yaml` 启动 MySQL 和 Chroma：首次在 仓库根目录 根据根目录 `.env.example` 创建 Compose 用的 `.env`，填写数据库密码后执行：

```powershell
docker compose up -d mysql chroma
```

本机已有 MySQL 时仅启动 `chroma`，避免重复占用 3306；Compose 仍要求配置其引用的环境变量。根目录 Compose `.env` 与 `backend/.env` 是不同配置文件。

数据库可连接后，在后端目录执行：

```powershell
.\.venv\Scripts\python.exe -m app.init_db --admin campus_admin
```

按交互提示设置管理员密码。账号已存在时，此命令不会重置密码或修改权限。学生可从注册页面创建，再由管理员维护课程与排课。新克隆的仓库不包含演示账号和排课数据。已有数据的数据库不要重复导入含清表语句的旧初始化 SQL。

### 8.4 启动应用

分别在三个终端运行，保持 MySQL 和 Chroma 已启动：

```powershell
# 终端一：backend/，启动业务后端
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# 终端二：backend/，启动独立 MCP 服务
.\.venv\Scripts\python.exe -m app.mcp_server
```

```powershell
# 终端三：frontend/，启动网页
npm ci
npm run dev -- --host 127.0.0.1
```

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:5173` | 网页入口 |
| `http://127.0.0.1:8000/` | FastAPI 基础存活检查 |
| `http://127.0.0.1:8000/docs` | Swagger 接口文档 |
| `http://127.0.0.1:8001/mcp` | MCP 协议端点，需通过客户端携带凭证连接 |
| `http://127.0.0.1:8002` | Chroma HTTP 服务 |

Vue 网页需要通过 Vite 或部署后的 HTTP 服务访问；直接预览 `frontend/index.html` 不能代替应用启动。FastAPI 根路径响应也不能证明 MCP、模型和 RAG 服务均可用，应继续按功能验收。

## 九、测试与验收

### 9.1 自动化检查

```powershell
# backend/
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check

# frontend/
npm test
npm run build
```

后端测试使用临时 SQLite、隔离文件目录及真实独立 MCP 子进程，覆盖身份、跨用户隔离、课程与课表规则、计划、文档、会话并发、工具调用和上传回滚等；模型及向量服务部分使用确定性替身。前端测试覆盖 SSE 分片解析和成功问答历史处理。

2026 年 11 月 8 日的[功能验收记录](test-results/2026-11-08-functional-test.md)显示，真实环境 API 用例 31 条通过，后端自动化 59 项、前端自动化 6 项通过。真实接口验收使用了已配置的 MCP、Chroma、Embedding 和聊天模型，覆盖课表连续追问、资料引用和确认保存计划。停止生成及两项服务故障恢复由隔离测试验证。浏览器页面交互仍需逐项复核。本次文档更新未重新运行应用测试。

现有本地演示库包含 3 个学生账号、5 门带「演示」前缀的课程和 7 条排课记录，有效期为 2026 年 11 月 2 日至 12 月 27 日。演示时可按学生筛选管理课表，再用相应学生账号对照个人课表。新建空库可按上文流程自行录入演示数据。

### 9.2 功能验收建议

| 场景 | 操作 | 预期结果 |
| --- | --- | --- |
| 角色权限 | 学生访问管理页面及 API | 页面入口受限，管理 API 返回 403 |
| 课程维护 | 管理员创建并修改课程 | 列表、详情与修改结果一致 |
| 个人课表 | 为两个学生分别排课，切换登录查询 | 各自只读取自己的排课 |
| 日期筛选 | 查询开始日、结束日、非上课日及范围外日期 | 按星期与有效期正确过滤 |
| 删除约束 | 删除已排课课程 | 返回冲突，原数据保留 |
| 学习计划 | 保存、分页、切换状态、删除并跨账号查询 | 只操作本人记录，列表倒序 |
| MCP 调用链 | 登录后调用 `/api/mcp/my-schedules` | 返回本人实际课表；空课表返回空列表与 0 |
| 课表对话 | 先查课表，再追问地点 | 调用工具并正确理解追问 |
| SSE | 观察状态、工具和文字；停止或中断 | 事件正确展示，未成功轮次不加入课程助手历史 |
| 私有 RAG | 上传含特定事实的文档，检索并提问 | 命中本人原文，回答展示实际来源 |
| 计划工具 | 明确要求制定并保存计划 | 工具成功后计划页可见记录 |
| 管理资料批量回滚 | 同批上传有效 TXT 与损坏 PDF | 整批失败，已有资料不受影响 |
| 纯文本预览 | 上传含 HTML 标签的文本 | 显示原始字符，不作为 HTML 执行 |
| 服务异常 | 暂停 MCP 或 Chroma 后查询 | 显示失败提示，不宣称成功 |

可使用 MCP Inspector 连接 `http://127.0.0.1:8001/mcp`，添加 `Authorization` 请求头，值为 `Bearer <登录token>`，连接后在 Tools 中调用 `get_my_schedules`。直接浏览 MCP URL 出现缺少凭证提示，不代表课表工具本身故障。

## 十、项目特点与后续扩展

### 10.1 项目特点

- 业务管理与 AI 工具共用 Service，减少规则重复实现。
- MCP 独立进程，便于直接调试工具协议和身份转发。
- 查询身份由 JWT 与数据库确定，不交给模型或工具参数选择。
- 个人 RAG 提供原文片段、引用标识和检索结果权限复核。
- SSE 展示工具执行及回答状态，处理失败、停止和断线。
- 管理员批量资料上传具有事务回滚及文件失败补偿。
- 保留旧课程、计划及工具入口的必要兼容，支持逐步升级。

### 10.2 已知限制

当前索引同步执行，适合小规模资料；尚未引入后台任务队列、长对话摘要、生产级审计或完整数据库迁移体系。排课冲突需要管理员人工检查。资料引用能够帮助核对来源，不能保证模型每次都正确理解内容。

本文描述的是代码能力，不代表当前机器的 MySQL、MCP、Chroma 和外部模型服务均在运行。真实环境需完成配置、建表和逐项联调后再认定部署可用。

### 10.3 扩展方向

1. 明确共享范围后，将管理员资料接入课程公共知识库与权限过滤检索。
2. 增加排课冲突检测、单双周配置和教务数据导入。
3. 引入异步索引任务、用户配额和失败重试管理。
4. 增加 OCR、长对话摘要和回答质量评估。
5. 建立数据库迁移、操作审计、备份与恢复流程。
6. 生产部署配置 HTTPS、限流、监控及 SSE 反向代理禁用缓冲；MCP 与 Chroma 保留在服务端网络。

## 十一、相关文档

- [项目入口与基础说明](../README.md)
- [开发、配置与详细验收指南](DEVELOPMENT.md)
- [后端配置模板](../backend/.env.example)
- [后端依赖清单](../backend/requirements.txt)
- [前端依赖与运行脚本](../frontend/package.json)
- [数据服务 Compose 配置](../compose.yaml)
