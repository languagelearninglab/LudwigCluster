import pickle
import socket
import yaml
import pandas as pd
import importlib
from pathlib import Path
import sys
from typing import Dict, Any
import shutil

# do not import ludwig here - this file is run on Ludwig workers


def save_job_files(param2val: Dict[str, Any],
                   series_list: list,
                   runs_path: Path,
                   ) -> None:

    if not series_list:
        print('WARNING: Job did not return any results')

    # job_path refers to local directory if --isolated but not --local
    job_path = runs_path / param2val['param_name'] / param2val['job_name']
    if not job_path.exists():
        job_path.mkdir(parents=True)

    # save series_list
    for series in series_list:
        if not isinstance(series, pd.Series):
            raise TypeError('Object returned by job must be a pandas.Series.')
        if series.name is None:
            raise AttributeError('Each pandas.Series returned by job must have attribute name refer to unique string.')
        with (job_path / '{}.csv'.format(series.name)).open('w') as f:
            series.to_csv(f, index=True, header=[series.name])  # cannot name the index with "header" arg
    print(f'Saved results   to {job_path}')

    # save param2val
    param2val_path = runs_path / param2val['param_name'] / 'param2val.yaml'
    if not param2val_path.exists():
        param2val_path.parent.mkdir(exist_ok=True)
        param2val['job_name'] = None
        with param2val_path.open('w', encoding='utf8') as f:
            yaml.dump(param2val, f, default_flow_style=False, allow_unicode=True)
    print(f'Saved param2val to {param2val_path}')

    # move contents of save_path to job_path (can be local or remote)
    save_path = Path(param2val['save_path'])
    src = str(save_path)
    dst = str(job_path)
    if save_path.exists():  # user may not create a directory at save path
        shutil.move(src, dst)  # src is no longer available afterwards
        print(f'Moved contents of save_path to {job_path}')


def run_job_on_ludwig_worker(param2val):
    """
    run a single job on on a single worker.
    this function is called on a Ludwig worker.
    this means that the package ludwig cannot be imported here.
    the package ludwig works client-side, and cannot be used on the workers or the file server.
    """

    # prepare save_path - this must be done on worker
    save_path = Path(param2val['save_path'])
    if not save_path.exists():
        save_path.mkdir(parents=True)

    # execute job
    series_list = job.main(param2val)  # name each returned series using 'name' attribute

    # save results
    runs_path = remote_root_path / 'runs'
    save_job_files(param2val, series_list, runs_path)


if __name__ == '__main__':

    # get src_name + project_name
    project_name = Path(__file__).stem.replace('run_', '')
    src_name = project_name.lower()

    # define paths - do not use any paths defined in user project (they may be invalid)
    ludwig_data = Path('/') / 'media' / 'ludwig_data'
    remote_root_path = ludwig_data / project_name

    # allow import of modules located in remote root path
    sys.path.append(str(remote_root_path))

    # import user's job to execute
    job = importlib.import_module('{}.job'.format(src_name))

    # find jobs
    hostname = socket.gethostname()
    pattern = f'{hostname.lower()}_*.pkl'
    pickled_param2val_paths = list(remote_root_path.glob(pattern))
    if not pickled_param2val_paths:
        print('No jobs found.')  # that's okay. run.py was triggered which triggered killing of active jobs on worker
    else:
        print(f'Found {len(pickled_param2val_paths)} jobs:')
        for p in pickled_param2val_paths:
            print(p)

    # run all jobs
    for param2val_path in pickled_param2val_paths:
        with param2val_path.open('rb') as f:
            param2val = pickle.load(f)
        run_job_on_ludwig_worker(param2val)