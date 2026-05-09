import tempfile
import unittest
from pathlib import Path

from app.models import Project
from app.store import InMemoryStore


class StoreTests(unittest.TestCase):
    def test_store_persists_and_loads_projects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            store = InMemoryStore(storage_root=temp_dir, state_file=str(state_file))
            project = Project(
                id="proj_test",
                name="测试项目",
                tender_name="测试招标",
                company_id="comp_test",
            )
            store.projects[project.id] = project
            store.save()

            reloaded = InMemoryStore(storage_root=temp_dir, state_file=str(state_file))
            self.assertIn(project.id, reloaded.projects)
            self.assertEqual(reloaded.projects[project.id].name, "测试项目")


if __name__ == "__main__":
    unittest.main()
