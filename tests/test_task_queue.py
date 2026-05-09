import unittest

from app.task_queue import LocalTaskQueue, task_queue


class TaskQueueTests(unittest.TestCase):
    def test_default_task_queue_is_local(self):
        self.assertIsInstance(task_queue, LocalTaskQueue)
        self.assertEqual(task_queue.name, "local_background")


if __name__ == "__main__":
    unittest.main()
