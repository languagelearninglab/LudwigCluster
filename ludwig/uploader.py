"""
The Uploader is used to submit jobs to one or more workers at the UIUC Learning & Language Lab
An sftp-client library is used to upload code files to each machine.
"""
from pathlib import Path
import pysftp
import platform
import psutil
import pickle
from typing import Union, Optional

from ludwig import configs
from ludwig import print_ludwig
from ludwig import run
from ludwig.job import Job


class Uploader:
    def __init__(self,
                 project_path: Path,
                 src_name: str,
                 ):
        self.project_path = project_path
        self.project_name = project_path.name
        self.src_name = src_name
        self.runs_path = self.project_path / 'runs'
        self.worker2ip = self.make_worker2ip()

    @staticmethod
    def make_worker2ip():
        """load hostname aliases from .ssh/ludwig_config"""
        res = {}
        h = None
        p = configs.Remote.path_to_ssh_config
        if not p.exists():
            raise FileNotFoundError('Please specify hostname-to-IP mappings in {}'.format(p))
        with p.open('r') as f:
            for line in f.readlines():
                words = line.split()
                if 'Host' in words:
                    h = line.split()[1]
                    res[h] = None
                elif 'HostName' in words:
                    ip = line.split()[1]
                    res[h] = ip
        return res

    def check_disk_space(self, verbose=False):
        if platform.system() in {'Linux'}:
            p = self.project_path.parent
            usage_stats = psutil.disk_usage(str(p))
            percent_used = usage_stats[3]
            if verbose:
                print_ludwig('Percent Disk Space used at {}: {}'.format(p, percent_used))
            if percent_used > configs.Remote.disk_max_percent:
                raise RuntimeError('Disk space usage > {}.'.format(configs.Remote.disk_max_percent))
        else:
            pass

    def to_disk(self,
                job: Job,
                worker: Optional[str] = None,
                verbose: bool = False,
                ) -> None:
        """
        saves parameter configuration for a single job to project_path.
        This allows Ludwig workers to find jobs
        """
        if not job.is_ready():
            raise SystemExit('Cannot save job. Job is not ready. Update job.param2val')

        # if new project, create project path on shared drive
        if not self.project_path.is_dir():
            self.project_path.mkdir()

        # save parameter configuration to shared drive
        unique_id = f'{job.param2val["param_name"]}_{job.param2val["job_name"]}'
        p = self.project_path / f'{worker}_{unique_id}.pkl'
        with p.open('wb') as f:
            pickle.dump(job.param2val, f)

        # console
        print_ludwig(f'Parameter configuration for {worker} saved to disk')
        if verbose:
            print(job)
            print()

    def start_jobs(self,
                   worker: str,
                   skip_hostkey: bool = False,  # True if skipping hostkey check (not safe)
                   ) -> None:
        """
        source code is uploaded.
        run.py is uploaded to worker, which triggers killing of existing jobs,
         and executes run.py.
        if no param2val for worker is saved to server, then run.py will exit.
        """

        # -------------------------------------- checks

        assert self.project_name.lower() == self.src_name  # TODO what about when src name must be different?
        # this must be true because in run.py project_name is converted to src_name

        self.check_disk_space()

        # -------------------------------------- prepare paths

        if not self.project_path.exists():
            self.project_path.mkdir()
        if not self.runs_path.exists():
            self.runs_path.mkdir(parents=True)

        remote_path = f'{configs.WorkerDirs.watched.name}/{self.src_name}'

        # ------------------------------------- sftp

        # (unsafe) skip hostkey check (this may prevent SSH connection errors for new users)
        cnopts = pysftp.CnOpts()
        if skip_hostkey:
            print('WARNING: Skipping hostkey check. Known hosts will not be consulted')
            cnopts.hostkeys = None

        # connect via sftp
        ludwig_data_path = self.project_path.parent
        private_key_path = ludwig_data_path / '.ludwig' / 'id_rsa'
        print(f'Looking for private key in {private_key_path}')
        if not private_key_path.exists():
            raise OSError(f'Did not find {private_key_path}')
        sftp = pysftp.Connection(username='ludwig',
                                 host=self.worker2ip[worker],
                                 private_key=str(private_key_path),
                                 cnopts=cnopts)

        # upload code files
        print_ludwig(f'Will upload {self.src_name} to {remote_path} on {worker}')
        sftp.makedirs(remote_path)
        sftp.put_r(localpath=self.src_name, remotepath=remote_path)

        # upload run.py
        run_file_name = f'run_{self.project_name}.py'
        sftp.put(localpath=run.__file__,
                 remotepath=f'{configs.WorkerDirs.watched.name}/{run_file_name}')

        print_ludwig(f'Upload to {worker} complete')

    def kill_jobs(self,
                  worker: str,
                  ) -> None:
        """
        first kil all job descriptions for worker (pickle files saved on server).
        then, run.py is uploaded to worker, which triggers killing of existing jobs,
         and executes run.py.
        because no job descriptions for worker exist on server, run.py will exit.
        """

        # -------------------------------------- checks

        assert self.project_name.lower() == self.src_name  # TODO what about when src name must be different?
        # this must be true because in run.py project_name is converted to src_name

        self.check_disk_space()

        # -------------------------------------- prepare paths

        if not self.project_path.exists():
            self.project_path.mkdir()
        if not self.runs_path.exists():
            self.runs_path.mkdir(parents=True)

        # ------------------------------------- sftp

        # connect via sftp
        ludwig_data_path = self.project_path.parent
        private_key_path = ludwig_data_path / '.ludwig' / 'id_rsa'
        print(f'Looking for private key in {str(private_key_path)}')
        if not private_key_path.exists():
            raise OSError(f'Did not find private key in {private_key_path}')
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None  # prevent: paramiko.ssh_exception.SSHException: No hostkey found
        sftp = pysftp.Connection(username='ludwig',
                                 host=self.worker2ip[worker],
                                 private_key=str(private_key_path),
                                 cnopts=cnopts)

        # upload run.py - this triggers watcher which kills active jobs associated with project
        run_file_name = f'run_{self.project_name}.py'
        sftp.put(localpath=run.__file__,
                 remotepath=f'{configs.WorkerDirs.watched.name}/{run_file_name}')

        print_ludwig(f'Killed any active jobs with src_name={self.src_name} on {worker}')