import os
import shutil
import time

class Storage:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def setup(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        jobs_dir = os.path.join(self.base_dir, "jobs")
        if not os.path.exists(jobs_dir):
            os.makedirs(jobs_dir)

    def init_job(self, job_id):
        path = self.job_dir(job_id)
        if not os.path.exists(path):
            os.makedirs(path)

    def job_dir(self, job_id):
        return os.path.join(self.base_dir, "jobs", job_id)

    def cleanup_older_than(self, hours=8):
        # Implementation to remove old job directories
        jobs_dir = os.path.join(self.base_dir, "jobs")
        if not os.path.exists(jobs_dir):
            return
        
        now = time.time()
        cutoff = now - (hours * 3600)
        
        for job_id in os.listdir(jobs_dir):
            job_path = os.path.join(jobs_dir, job_id)
            if os.path.isdir(job_path):
                mtime = os.path.getmtime(job_path)
                if mtime < cutoff:
                    try:
                        shutil.rmtree(job_path)
                    except Exception:
                        pass
