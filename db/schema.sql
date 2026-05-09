CREATE TABLE IF NOT EXISTS company (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tender_name VARCHAR(255) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_company_status ON project(company_id, status);

CREATE TABLE IF NOT EXISTS document (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    file_name VARCHAR(512) NOT NULL,
    file_type VARCHAR(64) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    object_storage_uri VARCHAR(1024),
    parsed_text TEXT,
    page_count INT NOT NULL DEFAULT 0,
    parse_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_document_project ON document(project_id);

ALTER TABLE document ADD COLUMN IF NOT EXISTS object_storage_uri VARCHAR(1024);

CREATE TABLE IF NOT EXISTS task (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) REFERENCES project(id) ON DELETE SET NULL,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    progress INT NOT NULL DEFAULT 0,
    current_step VARCHAR(128),
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_project_status ON task(project_id, status);

CREATE TABLE IF NOT EXISTS risk_item (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    risk_type VARCHAR(64) NOT NULL,
    requirement TEXT NOT NULL,
    trigger_keyword VARCHAR(128),
    severity VARCHAR(16) NOT NULL,
    need_material BOOLEAN NOT NULL DEFAULT true,
    source_page INT,
    source_section VARCHAR(255),
    source_text TEXT NOT NULL,
    ai_reason TEXT,
    suggestion TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewer_note TEXT,
    material_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_project_severity_status ON risk_item(project_id, severity, status);

CREATE TABLE IF NOT EXISTS tech_requirement (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    parameter_name VARCHAR(255) NOT NULL,
    operator VARCHAR(8) NOT NULL,
    required_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(64),
    is_mandatory BOOLEAN NOT NULL DEFAULT false,
    source_page INT,
    source_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tech_requirement_project ON tech_requirement(project_id);

CREATE TABLE IF NOT EXISTS deviation_result (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    tech_requirement_id VARCHAR(64) NOT NULL REFERENCES tech_requirement(id) ON DELETE CASCADE,
    item VARCHAR(255) NOT NULL,
    parameter VARCHAR(255) NOT NULL,
    required_value VARCHAR(255) NOT NULL,
    our_value VARCHAR(255),
    deviation_type VARCHAR(32) NOT NULL DEFAULT 'unknown',
    response_text TEXT,
    evidence TEXT,
    source_page INT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    reviewer_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_deviation_project_type ON deviation_result(project_id, deviation_type);

CREATE TABLE IF NOT EXISTS material (
    id VARCHAR(64) PRIMARY KEY,
    company_id VARCHAR(64) NOT NULL,
    file_name VARCHAR(512) NOT NULL,
    material_type VARCHAR(64) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    object_storage_uri VARCHAR(1024),
    parsed_text TEXT,
    page_count INT NOT NULL DEFAULT 0,
    name VARCHAR(255),
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_material_company_type ON material(company_id, material_type);

ALTER TABLE material ADD COLUMN IF NOT EXISTS object_storage_uri VARCHAR(1024);

CREATE TABLE IF NOT EXISTS export_record (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    export_type VARCHAR(64) NOT NULL,
    format VARCHAR(16) NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    task_id VARCHAR(64) REFERENCES task(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'done',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_export_project ON export_record(project_id);

CREATE TABLE IF NOT EXISTS review_feedback (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    target_type VARCHAR(64) NOT NULL,
    target_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    before JSONB NOT NULL DEFAULT '{}'::jsonb,
    after JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewer_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_project_target ON review_feedback(project_id, target_type, target_id);

CREATE TABLE IF NOT EXISTS activity_log (
    id VARCHAR(64) PRIMARY KEY,
    actor VARCHAR(255) NOT NULL,
    method VARCHAR(16) NOT NULL,
    path TEXT NOT NULL,
    status_code INT NOT NULL,
    project_id VARCHAR(64),
    action VARCHAR(128) NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_project_created ON activity_log(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_action_created ON activity_log(action, created_at DESC);
