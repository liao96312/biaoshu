from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.repositories.postgres import PostgresRepository
from app.store import InMemoryStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local JSON state into PostgreSQL.")
    parser.add_argument("--state-file", default=os.getenv("BID_AGENT_STATE_FILE", "storage/state.json"))
    parser.add_argument("--storage-root", default=os.getenv("BID_AGENT_STORAGE_ROOT", "storage"))
    parser.add_argument("--init-schema", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        return 2
    state_file = Path(args.state_file)
    if not state_file.exists():
        print(f"State file does not exist: {state_file}")
        return 2

    repo = PostgresRepository(database_url)
    if args.init_schema:
        schema = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
        repo.initialize_schema(schema)

    state = InMemoryStore(storage_root=args.storage_root, state_file=str(state_file))
    for company in state.companies.values():
        repo.upsert_company(company)
    for project in state.projects.values():
        repo.upsert_project(project)
    for document in state.documents.values():
        repo.upsert_document(document)
    for task in state.tasks.values():
        repo.upsert_task(task)
    for risk in state.risks.values():
        repo.upsert_risk(risk)
    for requirement in state.tech_requirements.values():
        repo.upsert_tech_requirement(requirement)
    for deviation in state.deviations.values():
        if deviation.tech_requirement_id in state.tech_requirements:
            repo.upsert_deviation(deviation)
    for material in state.materials.values():
        repo.upsert_material(material)
    for export in state.exports.values():
        repo.upsert_export(export)
    for feedback in state.feedback.values():
        repo.upsert_feedback(feedback)
    for activity in state.activity_logs.values():
        repo.upsert_activity_log(activity)

    print(
        "Migrated "
        f"{len(state.companies)} companies, "
        f"{len(state.projects)} projects, "
        f"{len(state.documents)} documents, "
        f"{len(state.tasks)} tasks, "
        f"{len(state.risks)} risks, "
        f"{len(state.tech_requirements)} requirements, "
        f"{len(state.deviations)} deviations, "
        f"{len(state.materials)} materials, "
        f"{len(state.exports)} exports, "
        f"{len(state.feedback)} feedback records, "
        f"{len(state.activity_logs)} activity logs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
