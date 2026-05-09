from __future__ import annotations

import json
import io
import time
import urllib.error
import urllib.request
from pathlib import Path
from zipfile import ZipFile


BASE_URL = "http://127.0.0.1:8000"
SMOKE_HEADERS = {"X-API-Key": f"smoke-{int(time.time() * 1000)}"}


def request(method: str, path: str, body=None, headers=None, expect_json: bool = True):
    data = None
    headers = {**SMOKE_HEADERS, **(headers or {})}
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", **headers}
    elif body is not None:
        data = body
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if expect_json else raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw.decode("utf-8")) if raw and expect_json else raw


def multipart(fields: dict[str, str], file_path: Path):
    boundary = "----bidAgentSmoke"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file_path.name}"\r\nContent-Type: text/plain\r\n\r\n'.encode()
    )
    chunks.append(file_path.read_bytes())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(chunks), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def main() -> int:
    sample_dir = Path("storage/smoke")
    sample_dir.mkdir(parents=True, exist_ok=True)
    tender = sample_dir / "tender.txt"
    product = sample_dir / "product.txt"
    delete_sample = sample_dir / "delete_me.txt"
    guarantee = sample_dir / "guarantee.txt"
    tender.write_text(
        "投标人须提供投标保证金缴纳凭证，否则投标无效。\n★核心交换机包转发率≥720Mpps。",
        encoding="utf-8",
    )
    product.write_text("核心交换机包转发率≥800Mpps。", encoding="utf-8")
    delete_sample.write_text("SMOKE_DELETE_UNIQUE material should vanish from search.", encoding="utf-8")
    guarantee.write_text("投标保证金缴纳凭证 银行回单 须提供材料", encoding="utf-8")

    _, project_resp = request(
        "POST",
        "/api/v1/projects",
        {"name": "Smoke Test", "tender_name": "文本招标", "company_id": "comp_smoke"},
    )
    project_id = project_resp["data"]["project_id"]

    body, headers = multipart({"material_type": "product", "name": "产品规格"}, product)
    request("POST", "/api/v1/companies/comp_smoke/materials", body, headers)
    body, headers = multipart({"material_type": "qualification", "name": "保证金回单"}, guarantee)
    request("POST", "/api/v1/companies/comp_smoke/materials", body, headers)
    body, headers = multipart({"material_type": "qualification", "name": "待删除资料"}, delete_sample)
    _, delete_material_upload = request("POST", "/api/v1/companies/comp_smoke/materials", body, headers)
    delete_material_id = delete_material_upload["data"]["id"]
    _, search_before_delete = request("GET", "/api/v1/companies/comp_smoke/materials/search?q=SMOKE_DELETE_UNIQUE")
    delete_material_status, _ = request("DELETE", f"/api/v1/companies/comp_smoke/materials/{delete_material_id}")
    _, search_after_delete = request("GET", "/api/v1/companies/comp_smoke/materials/search?q=SMOKE_DELETE_UNIQUE")

    body, headers = multipart({"doc_type": "tender"}, tender)
    _, upload_resp = request("POST", f"/api/v1/projects/{project_id}/documents", body, headers)
    task_id = upload_resp["data"]["parse_task_id"]
    for _ in range(60):
        _, task_resp = request("GET", f"/api/v1/tasks/{task_id}")
        if task_resp["data"]["status"] in {"done", "failed"}:
            break
        time.sleep(0.2)
    if task_resp["data"]["status"] != "done":
        print(json.dumps(task_resp, ensure_ascii=False, indent=2))
        return 1
    _, documents_before_reparse = request("GET", f"/api/v1/projects/{project_id}/documents")
    document_id = documents_before_reparse["data"]["items"][0]["id"]
    _, reparse_resp = request("POST", f"/api/v1/projects/{project_id}/documents/{document_id}/reparse")
    reparse_task_id = reparse_resp["data"]["parse_task_id"]
    for _ in range(60):
        _, reparse_task_resp = request("GET", f"/api/v1/tasks/{reparse_task_id}")
        if reparse_task_resp["data"]["status"] in {"done", "failed"}:
            break
        time.sleep(0.2)
    if reparse_task_resp["data"]["status"] != "done":
        print(json.dumps(reparse_task_resp, ensure_ascii=False, indent=2))
        return 1

    _, risks = request("GET", f"/api/v1/projects/{project_id}/risks")
    _, clauses = request("GET", f"/api/v1/projects/{project_id}/clauses")
    _, deviations = request("GET", f"/api/v1/projects/{project_id}/deviations")
    _, review_before = request("GET", f"/api/v1/projects/{project_id}/review-summary")
    _, matrix = request("GET", f"/api/v1/projects/{project_id}/scoring-matrix")
    _, gaps = request("GET", f"/api/v1/projects/{project_id}/material-gaps")
    _, material_recommendations = request("GET", f"/api/v1/projects/{project_id}/material-recommendations")
    _, auto_bind = request(
        "POST",
        f"/api/v1/projects/{project_id}/material-recommendations/auto-bind",
        {"limit_per_risk": 3, "min_score": 0.1},
    )
    _, outline = request("GET", f"/api/v1/projects/{project_id}/bid-outline")
    _, matrix_after_bind = request("GET", f"/api/v1/projects/{project_id}/scoring-matrix")
    _, documents = request("GET", f"/api/v1/projects/{project_id}/documents")
    _, tasks = request("GET", f"/api/v1/projects/{project_id}/tasks")
    _, materials = request("GET", "/api/v1/companies/comp_smoke/materials")
    _, capabilities = request("GET", "/api/v1/system/capabilities")
    _, integrations = request("GET", "/api/v1/system/integrations")
    _, rules = request("GET", "/api/v1/rules/risk")
    request(
        "POST",
        f"/api/v1/projects/{project_id}/feedback",
        {"target_type": "project", "target_id": project_id, "action": "smoke_checked", "reviewer_note": "smoke"},
    )
    _, feedback = request("GET", f"/api/v1/projects/{project_id}/feedback")
    _, activity = request("GET", f"/api/v1/system/activity?project_id={project_id}&limit=20")

    _, cleanup_project = request(
        "POST",
        "/api/v1/projects",
        {"name": "Smoke Cleanup", "tender_name": "清理测试", "company_id": "comp_smoke"},
    )
    cleanup_id = cleanup_project["data"]["project_id"]
    delete_status, delete_resp = request("DELETE", f"/api/v1/projects/{cleanup_id}?delete_files=false")
    missing_status, _ = request("GET", f"/api/v1/projects/{cleanup_id}")

    export_specs = [
        {"export_type": "deviation_table", "format": "xlsx"},
        {"export_type": "material_gap_list", "format": "xlsx"},
        {"export_type": "scoring_matrix", "format": "xlsx"},
        {"export_type": "bid_outline", "format": "docx"},
        {"export_type": "bid_outline", "format": "pdf"},
        {"export_type": "risk_report", "format": "docx"},
        {"export_type": "risk_report", "format": "pdf"},
        {"export_type": "submission_package", "format": "zip"},
    ]
    download_statuses: dict[str, int] = {}
    package_entries: list[str] = []
    for spec in export_specs:
        _, export = request("POST", f"/api/v1/projects/{project_id}/exports", spec)
        download_status, download_body = request(
            "GET", f"/api/v1/exports/{export['data']['export_id']}/download", expect_json=False
        )
        download_statuses[f"{spec['export_type']}.{spec['format']}"] = download_status
        if spec["export_type"] == "submission_package" and download_status == 200:
            with ZipFile(io.BytesIO(download_body)) as package:
                package_entries = package.namelist()
    complete_status, complete_resp = request("POST", f"/api/v1/projects/{project_id}/complete")
    request(
        "POST",
        f"/api/v1/projects/{project_id}/risks/batch-confirm",
        {"risk_ids": [item["id"] for item in risks["data"]["items"]], "status": "confirmed"},
    )
    request(
        "POST",
        f"/api/v1/projects/{project_id}/deviations/batch-confirm",
        {"deviation_ids": [item["id"] for item in deviations["data"]["items"]], "reviewer_status": "approved"},
    )
    _, review_after = request("GET", f"/api/v1/projects/{project_id}/review-summary")
    complete_after_status, complete_after_resp = request("POST", f"/api/v1/projects/{project_id}/complete")

    result = {
        "project_id": project_id,
        "task_status": task_resp["data"]["status"],
        "reparse_task_status": reparse_task_resp["data"]["status"],
        "risk_total": risks["data"]["total"],
        "clause_total": clauses["data"]["total"],
        "deviation_total": deviations["data"]["total"],
        "matrix_total": matrix["data"]["total"],
        "gap_total": gaps["data"]["total"],
        "material_recommendation_total": material_recommendations["data"]["total"],
        "auto_bound_materials": auto_bind["data"]["bound_materials"],
        "outline_total": outline["data"]["total"],
        "matrix_evidence_after_bind": ",".join(str(item.get("evidence") or "") for item in matrix_after_bind["data"]["items"]),
        "document_total": documents["data"]["total"],
        "document_has_object_uri": bool(documents["data"]["items"][0].get("object_storage_uri")),
        "task_total": tasks["data"]["total"],
        "material_total": materials["data"]["total"],
        "material_delete_status": delete_material_status,
        "material_search_before_delete": search_before_delete["data"]["total"],
        "material_search_after_delete": search_after_delete["data"]["total"],
        "feedback_total": feedback["data"]["total"],
        "review_before_blockers": review_before["data"]["blocker_count"],
        "review_after_ready": review_after["data"]["ready_to_complete"],
        "activity_total": activity["data"]["total"],
        "delete_status": delete_status,
        "deleted_project": delete_resp["data"].get("deleted"),
        "deleted_project_get_status": missing_status,
        "download_statuses": download_statuses,
        "package_entry_count": len(package_entries),
        "package_has_sources": any(item.startswith("source_documents/") for item in package_entries),
        "capability_storage": capabilities["data"]["storage"],
        "integration_count": len(integrations["data"]),
        "rule_keyword_count": len(rules["data"].get("high_keywords", []))
        + len(rules["data"].get("medium_keywords", [])),
        "complete_status": complete_status,
        "complete_message": complete_resp.get("message"),
        "complete_after_status": complete_after_status,
        "complete_after_project_status": complete_after_resp.get("data", {}).get("status"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = (
        result["risk_total"] >= 1
        and result["clause_total"] >= 2
        and result["reparse_task_status"] == "done"
        and result["deviation_total"] >= 1
        and result["document_total"] >= 1
        and result["document_has_object_uri"] is True
        and result["material_recommendation_total"] >= 1
        and result["auto_bound_materials"] >= 1
        and "保证金回单" in result["matrix_evidence_after_bind"]
        and result["task_total"] >= 1
        and result["material_total"] >= 1
        and result["material_delete_status"] == 200
        and result["material_search_before_delete"] >= 1
        and result["material_search_after_delete"] == 0
        and result["activity_total"] >= 1
        and result["delete_status"] == 200
        and result["deleted_project_get_status"] == 404
        and result["review_before_blockers"] >= 1
        and result["review_after_ready"] is True
        and result["complete_after_status"] == 200
        and result["package_entry_count"] >= 6
        and result["package_has_sources"] is True
        and all(status == 200 for status in download_statuses.values())
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
