<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  FileText,
  FolderOpen,
  PackageCheck,
  RefreshCw,
  SearchCheck,
  Settings,
  ShieldAlert,
  UploadCloud,
  WandSparkles,
  XCircle
} from "lucide-vue-next";
import { api, createExport, taskSocket, uploadMaterial, uploadTender } from "./api";
import type {
  ActivityLog,
  ClauseItem,
  DeviationResult,
  DocumentItem,
  Feedback,
  Material,
  MaterialGap,
  OutlineSection,
  PageResult,
  Project,
  RecommendationGroup,
  ReviewSummary,
  RiskItem,
  ScoringRow,
  TaskItem
} from "./types";

type TabKey = "risks" | "clauses" | "deviations" | "gaps" | "scoring" | "outline" | "documents" | "materials" | "feedback" | "rules" | "system";

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "risks", label: "风险清单" },
  { key: "clauses", label: "条款抽取" },
  { key: "deviations", label: "偏离核对" },
  { key: "gaps", label: "材料缺口" },
  { key: "scoring", label: "评分响应" },
  { key: "outline", label: "投标大纲" },
  { key: "documents", label: "文件任务" },
  { key: "materials", label: "企业资料" },
  { key: "feedback", label: "复核记录" },
  { key: "rules", label: "规则配置" },
  { key: "system", label: "系统状态" }
];

const exportOptions = [
  { label: "偏离表", export_type: "deviation_table", format: "xlsx" },
  { label: "缺口表", export_type: "material_gap_list", format: "xlsx" },
  { label: "评分矩阵", export_type: "scoring_matrix", format: "xlsx" },
  { label: "投标大纲", export_type: "bid_outline", format: "docx" },
  { label: "风控报告", export_type: "risk_report", format: "docx" },
  { label: "PDF 报告", export_type: "risk_report", format: "pdf" },
  { label: "交付包", export_type: "submission_package", format: "zip" }
];

const activeTab = ref<TabKey>("risks");
const projects = ref<Project[]>([]);
const currentProject = ref<Project | null>(null);
const summary = ref<ReviewSummary | null>(null);
const risks = ref<RiskItem[]>([]);
const clauses = ref<ClauseItem[]>([]);
const deviations = ref<DeviationResult[]>([]);
const gaps = ref<MaterialGap[]>([]);
const scoring = ref<ScoringRow[]>([]);
const outline = ref<OutlineSection[]>([]);
const documents = ref<DocumentItem[]>([]);
const tasks = ref<TaskItem[]>([]);
const materials = ref<Material[]>([]);
const feedback = ref<Feedback[]>([]);
const recommendations = ref(new Map<string, RecommendationGroup["recommendations"]>());
const rulesText = ref("{}");
const capabilities = ref<Record<string, unknown>>({});
const metrics = ref<Record<string, unknown>>({});
const integrations = ref<Record<string, unknown>>({});
const activity = ref<ActivityLog[]>([]);
const loading = ref(false);
const booting = ref(true);
const notice = ref("准备就绪");
const taskProgress = ref(0);
const taskText = ref("暂无后台任务");
const tenderInput = ref<HTMLInputElement | null>(null);
const materialInput = ref<HTMLInputElement | null>(null);

const form = reactive({
  name: "智能标书风控项目",
  tender_name: "招标文件复核",
  company_id: "comp_demo",
  material_type: "product"
});

const projectLabel = computed(() => {
  if (!currentProject.value) return "尚未选择项目";
  return `${cleanText(currentProject.value.name, currentProject.value.id)} · ${statusLabel(currentProject.value.status)}`;
});

const stats = computed(() => {
  const project = currentProject.value;
  return [
    {
      label: "高风险",
      value: project?.risk_count?.high ?? 0,
      hint: "需优先确认",
      tone: "danger",
      icon: ShieldAlert
    },
    {
      label: "技术参数",
      value: project?.tech_param_count ?? 0,
      hint: "已抽取指标",
      tone: "info",
      icon: ClipboardList
    },
    {
      label: "负偏离",
      value: project?.deviation_count?.negative ?? 0,
      hint: "影响响应",
      tone: "warn",
      icon: AlertTriangle
    },
    {
      label: "阻塞项",
      value: summary.value?.blocker_count ?? 0,
      hint: "归档前需处理",
      tone: "success",
      icon: SearchCheck
    }
  ];
});

const visibleProjects = computed(() => projects.value.filter((item) => !isNoisyProject(item)).slice(0, 10));

function setNotice(message: string) {
  notice.value = message;
}

function cleanText(value: unknown, fallback = "未命名") {
  const text = String(value ?? "").replace(/\uFFFD/g, "").trim();
  if (!text || /\?{2,}/.test(text)) return fallback;
  return text;
}

function isNoisyProject(project: Project) {
  return project.company_id === "comp_smoke"
    || /^smoke/i.test(project.name || "")
    || /\?{2,}|\uFFFD/.test(project.name || "")
    || /\?{2,}|\uFFFD/.test(project.tender_name || "");
}

function statusLabel(status: string) {
  return {
    created: "已创建",
    parsing: "解析中",
    review_pending: "待复核",
    completed: "已完成",
    pending: "待处理",
    confirmed: "已确认",
    dismissed: "已忽略",
    approved: "已通过",
    modified: "待修改",
    processing: "处理中",
    done: "完成",
    failed: "失败"
  }[status] || status;
}

function severityLabel(severity: string) {
  return { high: "高", medium: "中", low: "低" }[severity] || severity;
}

function deviationLabel(type: string) {
  return { positive: "正偏离", none: "无偏离", negative: "负偏离", unknown: "待判断" }[type] || type;
}

function clauseTypeLabel(type: string) {
  return { risk: "风险", material: "材料", technical: "技术", business: "商务", other: "其他" }[type] || type;
}

function confidence(value: number) {
  if (Number.isNaN(Number(value))) return "-";
  return `${Math.round(Number(value) * 100)}%`;
}

function stringify(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value);
}

async function run<T>(message: string, task: () => Promise<T>) {
  loading.value = true;
  setNotice(message);
  try {
    const result = await task();
    setNotice("操作完成");
    return result;
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    setNotice(messageText);
    throw error;
  } finally {
    loading.value = false;
  }
}

async function loadProjects() {
  const data = await api<PageResult<Project>>("/api/v1/projects?page_size=50");
  projects.value = data.items;
}

async function selectProject(project: Project) {
  form.company_id = project.company_id;
  await loadProject(project.id);
}

async function createProject() {
  await run("正在创建项目", async () => {
    const data = await api<{ project_id: string }>("/api/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.name.trim() || "智能标书风控项目",
        tender_name: form.tender_name.trim() || "招标文件复核",
        company_id: form.company_id.trim() || "comp_demo"
      })
    });
    await loadProjects();
    await loadProject(data.project_id);
  });
}

async function loadProject(projectId: string) {
  await run("正在刷新项目数据", async () => {
    const project = await api<Project>(`/api/v1/projects/${projectId}`);
    currentProject.value = project;
    form.company_id = project.company_id;

    const [
      summaryData,
      riskData,
      clauseData,
      deviationData,
      gapData,
      scoringData,
      outlineData,
      documentData,
      taskData,
      materialData,
      feedbackData
    ] = await Promise.all([
      api<ReviewSummary>(`/api/v1/projects/${projectId}/review-summary`),
      api<PageResult<RiskItem>>(`/api/v1/projects/${projectId}/risks?page_size=100`),
      api<PageResult<ClauseItem>>(`/api/v1/projects/${projectId}/clauses`),
      api<PageResult<DeviationResult>>(`/api/v1/projects/${projectId}/deviations?page_size=100`),
      api<PageResult<MaterialGap>>(`/api/v1/projects/${projectId}/material-gaps`),
      api<PageResult<ScoringRow>>(`/api/v1/projects/${projectId}/scoring-matrix`),
      api<PageResult<OutlineSection>>(`/api/v1/projects/${projectId}/bid-outline`),
      api<PageResult<DocumentItem>>(`/api/v1/projects/${projectId}/documents`),
      api<PageResult<TaskItem>>(`/api/v1/projects/${projectId}/tasks`),
      api<PageResult<Material>>(`/api/v1/companies/${project.company_id}/materials?page_size=100`),
      api<PageResult<Feedback>>(`/api/v1/projects/${projectId}/feedback`)
    ]);

    currentProject.value = project;
    summary.value = summaryData;
    risks.value = riskData.items;
    clauses.value = clauseData.items;
    deviations.value = deviationData.items;
    gaps.value = gapData.items;
    scoring.value = scoringData.items;
    outline.value = outlineData.items;
    documents.value = documentData.items;
    tasks.value = taskData.items;
    materials.value = materialData.items;
    feedback.value = feedbackData.items;
    await loadRecommendations(projectId);
    await loadProjects();
  });
}

async function refreshCurrent() {
  if (!currentProject.value) {
    await loadProjects();
    return;
  }
  await loadProject(currentProject.value.id);
}

async function loadRecommendations(projectId = currentProject.value?.id) {
  if (!projectId) return;
  const data = await api<PageResult<RecommendationGroup>>(`/api/v1/projects/${projectId}/material-recommendations?limit_per_risk=3`);
  recommendations.value = new Map(data.items.map((item) => [item.risk_id, item.recommendations || []]));
}

async function handleTenderUpload() {
  if (!currentProject.value) await createProject();
  const project = currentProject.value;
  const file = tenderInput.value?.files?.[0];
  if (!project || !file) {
    setNotice("请先选择招标文件");
    return;
  }
  const data = await run("正在上传并解析招标文件", () => uploadTender(project.id, file));
  if (data?.parse_task_id) watchTask(data.parse_task_id);
}

async function handleMaterialUpload() {
  const file = materialInput.value?.files?.[0];
  if (!file) {
    setNotice("请先选择企业资料");
    return;
  }
  await run("正在上传企业资料", () => uploadMaterial(form.company_id.trim() || "comp_demo", file, form.material_type));
  await refreshCurrent();
}

async function updateRisk(risk: RiskItem, status: "confirmed" | "dismissed") {
  if (!currentProject.value) return;
  await run("正在更新风险状态", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/risks/${risk.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status,
        reviewer_note: status === "dismissed" ? "人工复核忽略" : "人工复核确认",
        material_ids: risk.material_ids || []
      })
    });
    await refreshCurrent();
  });
}

async function updateDeviation(deviation: DeviationResult, reviewer_status: "approved" | "modified") {
  if (!currentProject.value) return;
  await run("正在更新偏离状态", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/deviations/${deviation.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_status })
    });
    await refreshCurrent();
  });
}

async function batchConfirmRisks() {
  if (!currentProject.value || risks.value.length === 0) return;
  await run("正在批量确认风险", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/risks/batch-confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ risk_ids: risks.value.map((item) => item.id), status: "confirmed" })
    });
    await refreshCurrent();
  });
}

async function batchApproveDeviations() {
  if (!currentProject.value || deviations.value.length === 0) return;
  await run("正在批量通过偏离项", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/deviations/batch-confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deviation_ids: deviations.value.map((item) => item.id), reviewer_status: "approved" })
    });
    await refreshCurrent();
  });
}

async function rematchDeviations() {
  if (!currentProject.value) return;
  await run("正在重新匹配产品参数", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/deviations/rematch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_ids: [] })
    });
    await refreshCurrent();
  });
}

async function autoBindMaterials() {
  if (!currentProject.value) return;
  await run("正在自动绑定推荐资料", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/material-recommendations/auto-bind`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit_per_risk: 3, min_score: 0.1 })
    });
    await refreshCurrent();
  });
}

async function completeProject() {
  if (!currentProject.value) return;
  await run("正在归档项目", async () => {
    await api(`/api/v1/projects/${currentProject.value!.id}/complete`, { method: "POST" });
    await refreshCurrent();
  });
}

async function exportFile(option: (typeof exportOptions)[number]) {
  if (!currentProject.value) return;
  await run("正在生成导出文件", () => createExport(currentProject.value!.id, {
    export_type: option.export_type,
    format: option.format,
    options: option.export_type === "deviation_table" ? { include_confidence: true } : {}
  }));
}

async function reparseDocument(documentId: string) {
  if (!currentProject.value) return;
  const data = await run("正在重新解析文件", () => api<{ parse_task_id: string }>(`/api/v1/projects/${currentProject.value!.id}/documents/${documentId}/reparse`, { method: "POST" }));
  if (data?.parse_task_id) watchTask(data.parse_task_id);
}

async function loadRules() {
  const rules = await api<Record<string, unknown>>("/api/v1/rules/risk");
  rulesText.value = JSON.stringify(rules, null, 2);
}

async function saveRules() {
  await run("正在保存规则配置", async () => {
    const payload = JSON.parse(rulesText.value);
    await api("/api/v1/rules/risk", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    await loadRules();
  });
}

async function loadSystem() {
  const [capabilityData, metricData, integrationData, activityData] = await Promise.all([
    api<Record<string, unknown>>("/api/v1/system/capabilities"),
    api<Record<string, unknown>>("/api/v1/system/metrics"),
    api<Record<string, unknown>>("/api/v1/system/integrations"),
    api<PageResult<ActivityLog>>("/api/v1/system/activity?limit=50")
  ]);
  capabilities.value = capabilityData;
  metrics.value = metricData;
  integrations.value = integrationData;
  activity.value = activityData.items;
}

function recommendationTags(riskId: string) {
  return recommendations.value.get(riskId) || [];
}

function watchTask(taskId: string) {
  taskProgress.value = 0;
  taskText.value = `任务 ${taskId}`;
  const socket = taskSocket(taskId);
  socket.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    taskProgress.value = data.progress || 0;
    taskText.value = `${data.current_step || "处理中"} · ${data.progress || 0}%`;
    if (data.event === "task_completed" || data.event === "task_failed") {
      socket.close();
      await refreshCurrent();
    }
  };
  socket.onerror = () => setNotice("任务连接中断，可手动刷新查看结果");
}

async function activateTab(tab: TabKey) {
  activeTab.value = tab;
  if (tab === "rules") await loadRules();
  if (tab === "system") await loadSystem();
}

onMounted(async () => {
  try {
    await Promise.all([loadProjects(), loadSystem(), loadRules()]);
    const firstProject = visibleProjects.value[0];
    if (firstProject) await loadProject(firstProject.id);
  } finally {
    booting.value = false;
  }
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <ShieldAlert :size="22" />
        </div>
        <div>
          <strong>标书风控 Agent</strong>
          <span>投标文件智能复核台</span>
        </div>
      </div>

      <section class="side-section">
        <div class="section-title">
          <FolderOpen :size="16" />
          <span>项目启动</span>
        </div>
        <label>
          项目名称
          <input v-model="form.name" />
        </label>
        <label>
          招标文件名称
          <input v-model="form.tender_name" />
        </label>
        <label>
          企业 ID
          <input v-model="form.company_id" />
        </label>
        <button class="primary full" :disabled="loading" @click="createProject">
          <PackageCheck :size="16" />
          新建项目
        </button>
      </section>

      <section class="side-section">
        <div class="section-title">
          <UploadCloud :size="16" />
          <span>资料上传</span>
        </div>
        <label class="file-field">
          <span>招标文件</span>
          <input ref="tenderInput" type="file" accept=".pdf,.docx,.xlsx,.xlsm,.txt,.md,.jpg,.jpeg,.png,.bmp,.tif,.tiff" />
        </label>
        <button class="secondary full" :disabled="loading" @click="handleTenderUpload">
          <UploadCloud :size="16" />
          上传解析
        </button>
        <div class="split">
          <label>
            资料类型
            <select v-model="form.material_type">
              <option value="product">产品资料</option>
              <option value="case">案例材料</option>
              <option value="qualification">资质文件</option>
            </select>
          </label>
        </div>
        <label class="file-field">
          <span>企业资料</span>
          <input ref="materialInput" type="file" accept=".pdf,.docx,.xlsx,.xlsm,.txt,.md,.jpg,.jpeg,.png,.bmp,.tif,.tiff" />
        </label>
        <button class="secondary full" :disabled="loading" @click="handleMaterialUpload">
          <Database :size="16" />
          入库企业资料
        </button>
      </section>

      <section class="side-section">
        <div class="section-title">
          <Activity :size="16" />
          <span>后台进度</span>
        </div>
        <progress :value="taskProgress" max="100" />
        <p class="muted compact">{{ taskText }}</p>
      </section>

      <section class="side-section grow">
        <div class="section-title">
          <ClipboardList :size="16" />
          <span>最近项目</span>
        </div>
        <div class="project-list">
          <button
            v-for="project in visibleProjects"
            :key="project.id"
            class="project-picker"
            :class="{ active: currentProject?.id === project.id }"
            @click="selectProject(project)"
          >
            <span>{{ cleanText(project.name, project.id) }}</span>
            <small>{{ cleanText(project.tender_name, "招标文件") }} · {{ statusLabel(project.status) }}</small>
          </button>
          <p v-if="!visibleProjects.length" class="muted">暂无可展示项目</p>
        </div>
      </section>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">Bid Risk Control Console</p>
          <h1>{{ projectLabel }}</h1>
          <span class="muted">{{ currentProject?.id || "创建或选择一个项目后开始复核" }}</span>
        </div>
        <div class="top-actions">
          <span class="status-pill" :class="{ busy: loading || booting }">{{ notice }}</span>
          <button class="icon-button" title="刷新" :disabled="loading" @click="refreshCurrent">
            <RefreshCw :size="18" />
          </button>
          <button class="primary" :disabled="!currentProject || loading" @click="completeProject">
            <CheckCircle2 :size="17" />
            归档
          </button>
        </div>
      </header>

      <section class="hero-strip">
        <div class="hero-copy">
          <span>规则抽取 · 技术偏离 · 资料匹配 · 交付导出</span>
          <strong>把投标风险压到可复核、可追踪、可交付。</strong>
        </div>
      </section>

      <section class="metrics-grid">
        <article v-for="item in stats" :key="item.label" class="metric" :class="item.tone">
          <component :is="item.icon" :size="20" />
          <div>
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.hint }}</small>
          </div>
        </article>
      </section>

      <section class="command-bar">
        <button class="secondary" :disabled="!currentProject || loading" @click="rematchDeviations">
          <WandSparkles :size="16" />
          重算偏离
        </button>
        <button class="secondary" :disabled="!currentProject || loading" @click="loadRecommendations()">
          <SearchCheck :size="16" />
          推荐材料
        </button>
        <button class="secondary" :disabled="!currentProject || loading" @click="autoBindMaterials">
          <PackageCheck :size="16" />
          自动绑定
        </button>
        <button class="secondary" :disabled="!currentProject || loading" @click="batchConfirmRisks">
          <CheckCircle2 :size="16" />
          确认风险
        </button>
        <button class="secondary" :disabled="!currentProject || loading" @click="batchApproveDeviations">
          <CheckCircle2 :size="16" />
          通过偏离
        </button>
        <div class="export-group">
          <button v-for="option in exportOptions" :key="`${option.export_type}-${option.format}`" class="ghost" :disabled="!currentProject || loading" @click="exportFile(option)">
            <Download :size="15" />
            {{ option.label }}
          </button>
        </div>
      </section>

      <nav class="tabs">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activateTab(tab.key)">
          {{ tab.label }}
        </button>
      </nav>

      <section class="data-plane">
        <div v-if="activeTab === 'risks'" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>等级</th>
                <th>要求</th>
                <th>建议</th>
                <th>材料推荐</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="risk in risks" :key="risk.id">
                <td><span class="tag" :class="risk.severity">{{ severityLabel(risk.severity) }}</span></td>
                <td>
                  <strong>{{ risk.requirement }}</strong>
                  <small>{{ risk.source_section || "来源页" }} {{ risk.source_page || "-" }} · {{ confidence(risk.confidence) }}</small>
                </td>
                <td>{{ risk.suggestion }}</td>
                <td>
                  <span v-for="item in recommendationTags(risk.id)" :key="item.material_id" class="pill">{{ item.name || item.file_name || item.material_id }} · {{ confidence(item.score) }}</span>
                  <span v-if="!recommendationTags(risk.id).length" class="muted">待推荐</span>
                </td>
                <td>{{ statusLabel(risk.status) }}</td>
                <td class="row-actions">
                  <button class="icon-button" title="确认" @click="updateRisk(risk, 'confirmed')"><CheckCircle2 :size="16" /></button>
                  <button class="icon-button" title="忽略" @click="updateRisk(risk, 'dismissed')"><XCircle :size="16" /></button>
                </td>
              </tr>
              <tr v-if="!risks.length"><td colspan="6" class="empty">上传招标文件后会生成风险清单</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'clauses'" class="table-wrap">
          <table>
            <thead><tr><th>类型</th><th>条款内容</th><th>关键词</th><th>来源</th><th>页码</th></tr></thead>
            <tbody>
              <tr v-for="clause in clauses" :key="`${clause.clause_type}-${clause.clause_text}`">
                <td>{{ clauseTypeLabel(clause.clause_type) }}</td>
                <td>{{ clause.clause_text }}</td>
                <td>{{ (clause.keywords || []).join("、") }}</td>
                <td>{{ clause.source_section || clause.file_name || "-" }}</td>
                <td>{{ clause.source_page || "-" }}</td>
              </tr>
              <tr v-if="!clauses.length"><td colspan="5" class="empty">暂无条款结果</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'deviations'" class="table-wrap">
          <table>
            <thead><tr><th>参数</th><th>要求</th><th>我方响应</th><th>偏离</th><th>证据</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="item in deviations" :key="item.id">
                <td><strong>{{ item.item }}</strong><small>{{ item.parameter }} · 页 {{ item.source_page || "-" }}</small></td>
                <td>{{ item.required_value }}</td>
                <td>{{ item.response_text }}</td>
                <td><span class="tag" :class="item.deviation_type">{{ deviationLabel(item.deviation_type) }}</span></td>
                <td>{{ item.evidence || "-" }}</td>
                <td class="row-actions">
                  <button class="icon-button" title="通过" @click="updateDeviation(item, 'approved')"><CheckCircle2 :size="16" /></button>
                  <button class="icon-button" title="待修改" @click="updateDeviation(item, 'modified')"><XCircle :size="16" /></button>
                </td>
              </tr>
              <tr v-if="!deviations.length"><td colspan="6" class="empty">暂无偏离结果</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'gaps'" class="table-wrap">
          <table>
            <thead><tr><th>等级</th><th>材料要求</th><th>建议</th><th>已绑定</th><th>推荐</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="gap in gaps" :key="`${gap.risk_id}-${gap.material_requirement}`">
                <td><span class="tag" :class="gap.severity">{{ severityLabel(gap.severity) }}</span></td>
                <td>{{ gap.material_requirement }}</td>
                <td>{{ gap.suggestion }}</td>
                <td><span v-for="name in gap.bound_materials || []" :key="name" class="pill">{{ name }}</span><span v-if="!(gap.bound_materials || []).length" class="muted">未绑定</span></td>
                <td><span v-for="item in recommendationTags(gap.risk_id)" :key="item.material_id" class="pill">{{ item.name || item.file_name || item.material_id }}</span></td>
                <td>{{ gap.status }}</td>
              </tr>
              <tr v-if="!gaps.length"><td colspan="6" class="empty">暂无材料缺口</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'scoring'" class="table-wrap">
          <table>
            <thead><tr><th>评分点</th><th>要求</th><th>响应</th><th>证据</th><th>优先级</th></tr></thead>
            <tbody>
              <tr v-for="row in scoring" :key="`${row.score_point}-${row.requirement}`">
                <td>{{ row.score_point }}</td>
                <td>{{ row.requirement }}</td>
                <td>{{ row.response }}</td>
                <td>{{ row.evidence || "-" }}</td>
                <td><span class="tag" :class="row.priority">{{ row.priority }}</span></td>
              </tr>
              <tr v-if="!scoring.length"><td colspan="5" class="empty">暂无评分矩阵</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'outline'" class="outline-grid">
          <article v-for="section in outline" :key="section.code" class="outline-item">
            <span>{{ section.code }}</span>
            <strong>{{ section.title }}</strong>
            <ul>
              <li v-for="item in section.items" :key="item.title">{{ item.title }} · {{ item.status }}</li>
            </ul>
          </article>
          <p v-if="!outline.length" class="empty">暂无投标大纲</p>
        </div>

        <div v-if="activeTab === 'documents'" class="table-wrap">
          <table>
            <thead><tr><th>文件</th><th>类型</th><th>状态</th><th>页数</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="document in documents" :key="document.id">
                <td><a :href="`/api/v1/projects/${currentProject?.id}/documents/${document.id}/download`">{{ document.file_name }}</a></td>
                <td>{{ document.file_type }}</td>
                <td>{{ statusLabel(document.parse_status) }}</td>
                <td>{{ document.page_count }}</td>
                <td><button class="ghost" @click="reparseDocument(document.id)"><RefreshCw :size="15" />重跑</button></td>
              </tr>
              <tr v-if="!documents.length"><td colspan="5" class="empty">暂无项目文件</td></tr>
            </tbody>
          </table>

          <table class="sub-table">
            <thead><tr><th>任务</th><th>状态</th><th>进度</th><th>当前步骤</th></tr></thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.id">
                <td>{{ task.task_type }}</td>
                <td>{{ statusLabel(task.status) }}</td>
                <td>{{ task.progress }}%</td>
                <td>{{ task.current_step || task.error_message || "-" }}</td>
              </tr>
              <tr v-if="!tasks.length"><td colspan="4" class="empty">暂无任务</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'materials'" class="table-wrap">
          <table>
            <thead><tr><th>资料</th><th>类型</th><th>标签</th><th>页数</th></tr></thead>
            <tbody>
              <tr v-for="material in materials" :key="material.id">
                <td><a :href="`/api/v1/companies/${form.company_id}/materials/${material.id}/download`">{{ material.name || material.file_name }}</a></td>
                <td>{{ material.material_type }}</td>
                <td>{{ material.tags.join("、") || "-" }}</td>
                <td>{{ material.page_count }}</td>
              </tr>
              <tr v-if="!materials.length"><td colspan="4" class="empty">暂无企业资料</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'feedback'" class="table-wrap">
          <table>
            <thead><tr><th>对象</th><th>动作</th><th>说明</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="item in feedback" :key="item.id">
                <td>{{ item.target_type }}</td>
                <td>{{ item.action }}</td>
                <td>{{ item.reviewer_note || "-" }}</td>
                <td>{{ item.created_at }}</td>
              </tr>
              <tr v-if="!feedback.length"><td colspan="4" class="empty">暂无人工复核记录</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="activeTab === 'rules'" class="rules-editor">
          <div class="panel-heading">
            <Settings :size="18" />
            <strong>风险规则 JSON</strong>
            <button class="secondary" @click="saveRules">保存规则</button>
          </div>
          <textarea v-model="rulesText" spellcheck="false" />
        </div>

        <div v-if="activeTab === 'system'" class="system-grid">
          <article>
            <h2>能力</h2>
            <p v-for="(value, key) in capabilities" :key="key"><span>{{ key }}</span><strong>{{ stringify(value) }}</strong></p>
          </article>
          <article>
            <h2>指标</h2>
            <p v-for="(value, key) in metrics" :key="key"><span>{{ key }}</span><strong>{{ stringify(value) }}</strong></p>
          </article>
          <article>
            <h2>集成</h2>
            <p v-for="(value, key) in integrations" :key="key"><span>{{ key }}</span><strong>{{ stringify(value) }}</strong></p>
          </article>
          <article class="activity-log">
            <h2>审计日志</h2>
            <p v-for="item in activity" :key="item.id"><span>{{ item.status_code }} · {{ item.action }}</span><strong>{{ item.project_id || item.actor }}</strong></p>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>
