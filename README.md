# 标书风控 Agent MVP

这是根据 `标书风控Agent — 技术设计文档 v2.pdf` 落地的工程实现。当前主链路已经覆盖：

1. 创建投标项目
2. 上传招标文件
3. 异步解析文件并识别废标风险
4. 抽取技术参数并生成偏离表草稿
5. 检索公司资料库，推荐并绑定证明材料
6. 人工确认、修改和完成闸门
7. 导出偏离表、风险报告、材料缺失清单、评分矩阵、投标目录、PDF 报告和检查包

当前默认采用 JSON 状态和本地文件目录，适合产品验证和接口联调；也已提供 PostgreSQL、Redis/Celery、Qdrant、MinIO、LangGraph 和大模型调用的配置入口与适配边界。

当前基础依赖保证 PDF / Excel / 文本文件主链路可跑；生产依赖安装 `python-docx` 和 `paddleocr` 后可启用 Word 与扫描件 OCR 能力。

## 快速启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

生产部署依赖包含 PostgreSQL、Celery、Redis、Qdrant、MinIO、LangGraph 客户端：

```powershell
pip install -r requirements-prod.txt
```

服务启动后访问：

- 操作台: http://127.0.0.1:8000/app/
- API 文档: http://127.0.0.1:8000/docs
- 健康检查: http://127.0.0.1:8000/healthz
- 项目接口前缀: `/api/v1`

## Docker Compose

```powershell
copy .env.example .env
docker compose up --build
```

Compose 文件包含 API、PostgreSQL、Redis、Qdrant 和 MinIO，贴近技术设计文档里的部署形态。默认仍可用本地 `storage/` 跑演示；设置对应环境变量后可切到数据库、队列、向量库和对象存储。
Compose 中 API 会使用 `BID_AGENT_TASK_QUEUE=celery` 将解析任务投递给 worker。

数据库表结构已放在 [db/schema.sql](db/schema.sql)，覆盖项目、文件、任务、风险项、技术要求、偏离结果、资料和导出记录。

初始化 PostgreSQL schema：

```powershell
$env:DATABASE_URL="postgresql://bid_agent:bid_agent@127.0.0.1:5432/bid_agent"
python scripts/init_db.py
```

检查 PostgreSQL 连接：

```powershell
python scripts/check_postgres.py
```

把当前本地 `storage/state.json` 迁移到 PostgreSQL：

```powershell
python scripts/migrate_state_to_postgres.py --init-schema
```

## 当前接口

- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/complete`
- `POST /api/v1/projects/{project_id}/feedback`
- `GET /api/v1/projects/{project_id}/feedback`
- `POST /api/v1/companies`
- `GET /api/v1/companies`
- `GET /api/v1/companies/{company_id}`
- `POST /api/v1/projects/{project_id}/documents`
- `GET /api/v1/projects/{project_id}/documents`
- `POST /api/v1/projects/{project_id}/documents/{document_id}/reparse`
- `GET /api/v1/projects/{project_id}/documents/{document_id}/download`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/projects/{project_id}/tasks`
- `GET /api/v1/projects/{project_id}/risks`
- `GET /api/v1/projects/{project_id}/clauses`
- `PATCH /api/v1/projects/{project_id}/risks/{risk_id}`
- `POST /api/v1/projects/{project_id}/risks/batch-confirm`
- `GET /api/v1/projects/{project_id}/deviations`
- `PATCH /api/v1/projects/{project_id}/deviations/{param_id}`
- `POST /api/v1/projects/{project_id}/deviations/batch-confirm`
- `POST /api/v1/projects/{project_id}/deviations/rematch`
- `GET /api/v1/projects/{project_id}/material-gaps`
- `GET /api/v1/projects/{project_id}/material-recommendations`
- `POST /api/v1/projects/{project_id}/material-recommendations/auto-bind`
- `GET /api/v1/projects/{project_id}/risks/{risk_id}/material-recommendations`
- `GET /api/v1/projects/{project_id}/scoring-matrix`
- `GET /api/v1/projects/{project_id}/bid-outline`
- `GET /api/v1/projects/{project_id}/review-summary`
- `POST /api/v1/projects/{project_id}/exports`
- `GET /api/v1/exports/{export_id}/download`
- `POST /api/v1/companies/{company_id}/materials`
- `GET /api/v1/companies/{company_id}/materials`
- `DELETE /api/v1/companies/{company_id}/materials/{material_id}`
- `GET /api/v1/companies/{company_id}/materials/{material_id}/download`
- `GET /api/v1/companies/{company_id}/materials/search?q=交换机`
- `GET /api/v1/rules/risk`
- `PUT /api/v1/rules/risk`
- `GET /api/v1/system/capabilities`
- `GET /api/v1/system/metrics`
- `GET /api/v1/system/integrations`
- `GET /api/v1/system/activity`
- `WS /ws/tasks/{task_id}`

## 当前完成度

- PostgreSQL：`postgres_mirror` 保留 JSON 本地读写并镜像写入 PostgreSQL；`postgres` 会从 PostgreSQL 读取项目、公司、文档、任务、风险、技术参数、偏离、资料、导出和审核反馈。
- 向量检索：默认使用本地关键词检索；配置 `BID_AGENT_EMBEDDING_PROVIDER=openai/openai_compatible/qwen/deepseek` 后可使用真实 embedding，Qdrant 集合会按实际向量维度创建。
- Agent 编排：默认使用稳定的确定性工作流；配置 `BID_AGENT_WORKFLOW_ENGINE=langgraph` 且安装 LangGraph 后会尝试用图式工作流执行，失败时回落到默认流程。
- 操作台：已覆盖项目创建、最近项目选择、招标解析、资料上传、关键条款/风险/偏离/材料缺失/评分矩阵/投标目录查看、六类导出、文档任务、资料库、反馈、规则维护和系统状态。
- 审计留痕：所有写操作会记录到 activity log，支持按项目查询；项目删除可同步清理本地项目文件和导出文件。
- 审核闭环：`review-summary` 会汇总阻塞项、风险状态和偏离状态；风险与偏离都支持批量确认，确认后可通过完成闸门。
- 材料推荐：系统会按风险项从公司资料库检索推荐证明材料，并可自动绑定到风险项；操作台、材料缺失清单导出和评分矩阵会同步显示可读材料名称。
- 重跑解析：已有文档可通过 `documents/{document_id}/reparse` 重新进入解析队列，用于规则、资料或解析逻辑更新后的复算。
- 源文追溯：文本、PDF、Word、Excel 和 OCR 结果都会进入统一页码标记流程；Excel 以 sheet 序号映射来源页，`clauses` 接口会按页码和章节输出关键条款。
- 验证脚本：`scripts/smoke_test.py` 覆盖解析闭环、五类导出下载、文档/任务/资料/反馈、审计、项目删除、规则、系统状态和审核闸门。

## 设计边界

- Agent 拆分：`app/agents/workflow.py` 已按文档保留 8 个 Agent 边界，默认用确定性流程实现；配置 LangGraph 后可用图式编排执行。
- 配置管理：`app/config.py` 集中读取 Token、API Key、数据库、Redis、Qdrant、MinIO 和本地存储配置。
- 持久化兜底：默认使用 `storage/state.json` 保存内存状态，重启后可恢复本地演示数据。
- PostgreSQL Repository：`app/repositories/postgres.py` 已覆盖核心实体读写，配合 `db/schema.sql` 可从 JSON 迁移到 PostgreSQL。
- Runtime Repository：`app/repositories/runtime.py` 是当前 API 的统一仓储入口；默认 `BID_AGENT_STORAGE_BACKEND=json`，设置为 `postgres_mirror` 时镜像写入 PostgreSQL，设置为 `postgres` 时使用 PostgreSQL 读路径。
- 状态迁移：`scripts/migrate_state_to_postgres.py` 可将本地 JSON 状态导入 PostgreSQL，便于从演示环境平滑迁移到持久化部署。
- 任务队列：`app/task_queue.py` 默认本地后台执行；设置 `BID_AGENT_TASK_QUEUE=celery` 后投递到 Celery worker。
- 废标规则库：`app/rules/risk_rules.json` 保存高/中风险关键词和风险类型映射，后续可按行业持续积累。
- 规则运营 API：`GET/PUT /api/v1/rules/risk` 可查看和更新废标规则，更新后会刷新扫描缓存。
- 知识库检索：公司资料上传后会进入知识库索引，`materials/search` 提供检索入口；可用内存检索或 Qdrant。
- 废标风险：先用关键词和章节线索做规则扫描，每条风险都带原文片段和来源页码。
- 技术参数：AI 负责的复杂抽取暂未接入，当前用正则抽取常见数值参数。
- 偏离判断：数值比较由程序完成，符合设计文档里“禁止交给 AI”的原则。
- 产品匹配：产品资料上传后会解析参数，偏离表可通过 `deviations/rematch` 重新匹配。
- 材料缺失清单：基于需要证明材料的风险项生成，可用于 V2 的材料补齐工作台。
- 评分点响应矩阵：合并高风险项和技术偏离项，支持导出 `scoring_matrix.xlsx`。
- 实时进度：解析任务支持 `GET /api/v1/tasks/{task_id}` 轮询，也支持 WebSocket 推送。
- 人工审核闸门：`POST /projects/{project_id}/complete` 会阻止未确认高风险项、未审核负偏离/未知偏离项目直接完成。
- 审核反馈沉淀：风险确认、批量确认、偏离修改会自动写入 feedback；也可通过 `POST /feedback` 主动记录人工修正，作为后续规则优化和模型训练信号。
- 操作审计：`GET /api/v1/system/activity` 可查看写操作日志，包含动作、状态码、调用方摘要和关联项目。
- 导出：支持技术偏离表 `.xlsx`、废标风险检查报告 `.docx/.pdf`、材料缺失清单 `.xlsx`、评分点响应矩阵 `.xlsx`、投标文件目录 `.docx/.pdf` 和一键投标检查包 `.zip`。
- 认证：默认本地开放；设置 `BID_AGENT_TOKEN` 后需要 `Authorization: Bearer <token>`，设置 `BID_AGENT_API_KEYS` 后支持 `X-API-Key`。
- 速率限制：`app/rate_limit.py` 提供内存固定窗口限流，默认每客户端每小时 100 次，并返回 `X-RateLimit-*` 响应头。
- 外部系统适配器：`app/adapters/` 预留 LLM、对象存储和向量库接口，当前提供本地/内存实现，便于替换成 Claude/GPT、MinIO/OSS、Qdrant。
- LLM：默认 `BID_AGENT_LLM_PROVIDER=disabled`，规则引擎独立可跑；配置 `openai`、`deepseek`、`qwen`、`anthropic` 后会在 Agent 工作流中额外执行 AI 风险/参数抽取。
- OCR：默认 `BID_AGENT_OCR_PROVIDER=disabled`；配置 `paddleocr` 后支持图片和扫描件 OCR。
- 对象存储：默认 `BID_AGENT_OBJECT_STORAGE=local`；配置 `minio` 后上传文件会同步写入 MinIO。
- 存储追踪：文档和资料同时保留本地解析路径与 `object_storage_uri`，便于本地解析、对象存储下载和问题排查分离。
- 向量检索：默认 `BID_AGENT_VECTOR_BACKEND=memory` 和 `BID_AGENT_EMBEDDING_PROVIDER=hash`；配置真实 embedding 与 `qdrant` 后公司资料会写入 Qdrant 检索库。

## 本地验证

```powershell
python -m unittest discover -s tests
python scripts/smoke_test.py
```
