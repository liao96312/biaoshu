# 标书风控 Agent

[![CI](https://github.com/liao96312/biaoshu/actions/workflows/ci.yml/badge.svg)](https://github.com/liao96312/biaoshu/actions/workflows/ci.yml)

这是按《标书风控 Agent 技术设计文档 v2》落地的投标文件智能复核项目。当前实现已经覆盖项目创建、招标文件解析、废标风险识别、技术参数偏离核对、企业资料检索推荐、人工复核闭环、审计留痕和多格式交付导出。

## 项目结构

- `web/`：Vue 3 + Vite 前端工作台，主入口，包含项目启动、文件上传、复核表格、资料推荐、规则配置和系统状态。
- `app/`：FastAPI 后端接口、解析任务、业务规则、Agent 工作流、存储适配和导出服务。
- `db/`：PostgreSQL 表结构。
- `scripts/`：本地冒烟测试、数据库初始化、状态迁移和连接检查脚本。
- `tests/`：接口、解析、导出、任务和规则回归测试。

## 本地启动

后端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd web
npm install
npm run dev
```

访问地址：

- 前端工作台：http://127.0.0.1:5173/
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/healthz
- 就绪检查：http://127.0.0.1:8000/readyz
- 旧版后端静态页：http://127.0.0.1:8000/app/

## Docker Compose

```powershell
copy .env.example .env
docker compose up --build
```

Compose 会启动 `web`、`api`、`worker`、PostgreSQL、Redis、Qdrant 和 MinIO。默认访问 `http://127.0.0.1:5173/`，前端容器通过 Nginx 将 `/api/` 和 `/ws/` 代理到后端服务。

Compose 默认使用 `BID_AGENT_STORAGE_BACKEND=postgres_mirror`：API 和 worker 仍保留本地 JSON 状态作为演示兜底，同时把业务数据镜像写入 PostgreSQL；PostgreSQL 首次启动会自动执行 `db/schema.sql`。各服务带健康检查，`web` 会等待 `api` 健康后再对外服务，`api` 和 `worker` 会等待 PostgreSQL 与 Redis 可用。

常用部署检查：

```powershell
docker compose config
docker compose ps
docker compose logs -f api
```

## 安全配置

- 认证：本地默认开放；设置 `BID_AGENT_TOKEN` 后 API 需要 `Authorization: Bearer <token>`，设置 `BID_AGENT_API_KEYS` 后支持 `X-API-Key`。
- 租户隔离：请求带 `X-Company-ID` 后，项目、资料、文件和导出会限制在该企业范围内；不带该头时保留本地演示模式。
- 上传限制：`BID_AGENT_MAX_UPLOAD_BYTES` 默认 52428800，即单文件 50MB。超过限制的上传会被拒绝并清理临时文件。
- 文件边界：上传只允许 PDF、Word、Excel、文本、Markdown 和常见图片格式；下载和删除会校验文件仍在 `storage/` 下，避免路径穿越。
- 健康检查：`/healthz` 只返回服务状态、存储后端和任务队列类型，不暴露本机绝对路径。
- 就绪检查：`/readyz` 会检查本地存储可写性，并在启用 PostgreSQL 时检查数据库读写链路可用性。
- 前端代理：生产容器由 Nginx 代理 `/api/`、`/ws/` 和 `/healthz` 到后端，避免浏览器跨域配置扩大暴露面。

## 核心能力

- 项目管理：创建投标项目、查看最近项目、项目归档门禁。
- 招标解析：上传 PDF、Word、Excel、图片或文本文件，后台解析并通过 WebSocket 推送任务进度。
- 风险识别：抽取废标风险、关键条款、来源页码、命中关键词、AI 理由和处理建议。
- 偏离核对：抽取技术参数，和企业产品资料进行匹配，生成正偏离、无偏离、负偏离和待判断结果。
- 材料推荐：从企业资料库检索证明材料，支持推荐查看和自动绑定到风险项。
- 人工复核：风险确认/忽略、偏离通过/待修改、批量确认、反馈沉淀和审计日志。
- 交付导出：偏离表、材料缺口表、评分矩阵、投标大纲、风控报告、PDF 报告和一键交付包。
- 规则运营：通过 `/api/v1/rules/risk` 查看和维护风险规则。
- 部署扩展：本地 JSON 存储可切换到 PostgreSQL，任务队列可切换到 Celery，资料检索可接入 Qdrant/Embedding，对象存储可接入 MinIO。

## 主要接口

- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/documents`
- `GET /api/v1/projects/{project_id}/risks`
- `PATCH /api/v1/projects/{project_id}/risks/{risk_id}`
- `GET /api/v1/projects/{project_id}/clauses`
- `GET /api/v1/projects/{project_id}/deviations`
- `PATCH /api/v1/projects/{project_id}/deviations/{param_id}`
- `POST /api/v1/projects/{project_id}/deviations/rematch`
- `GET /api/v1/projects/{project_id}/material-gaps`
- `GET /api/v1/projects/{project_id}/material-recommendations`
- `POST /api/v1/projects/{project_id}/material-recommendations/auto-bind`
- `GET /api/v1/projects/{project_id}/scoring-matrix`
- `GET /api/v1/projects/{project_id}/bid-outline`
- `POST /api/v1/projects/{project_id}/exports`
- `GET /api/v1/exports/{export_id}/download`
- `POST /api/v1/companies/{company_id}/materials`
- `GET /api/v1/companies/{company_id}/materials`
- `GET /api/v1/rules/risk`
- `PUT /api/v1/rules/risk`
- `GET /api/v1/system/capabilities`
- `GET /api/v1/system/metrics`
- `GET /api/v1/system/integrations`
- `GET /api/v1/system/activity`
- `WS /ws/tasks/{task_id}`

## 验证

GitHub Actions 会在 `main` 分支 push 和 pull request 上自动运行后端单测、API 冒烟、前端依赖审计和前端构建。

```powershell
python -m unittest discover -s tests
python scripts/smoke_test.py
cd web
npm run build
```

## 简历描述

可描述为：独立完成一个面向投标场景的标书风控 Agent 系统，基于 FastAPI + Vue 3 实现招标文件解析、废标风险识别、技术偏离核对、企业资料推荐、人工复核闭环和导出交付。系统预留 PostgreSQL、Redis/Celery、Qdrant、MinIO 和 LLM 适配边界，具备本地可运行、容器化部署和完整冒烟测试能力。
