import time

class ProgressTracker:
    def __init__(self):
        self._jobs = {}

    def init(self, job_id):
        self._jobs[job_id] = {
            "status": "initializing",
            "created_at": time.time(),
            "results": []
        }

    def update(self, job_id, key, value):
        if job_id in self._jobs:
            self._jobs[job_id][key] = value

    def get(self, job_id):
        return self._jobs.get(job_id, {})
