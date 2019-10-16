# Ludwig

## Info

The UIUC Learning & language Lab provides compute resources for lab members and collaborators wishing to train large neural network models. 
The resource consists of a file server and 8 Ubuntu 16.04 machines with GPU acceleration for deep learning tasks.

## Specs

| hostname  |GPU                    | Model               |
|-----------|-----------------------|---------------------|
| hoff      |1 Geforce GTX 1080     | Alienware Aurora R6 |
| norman    |1 Geforce GTX 1080     | Alienware Aurora R6 |
| hebb      |1 Geforce GTX 1080     | Alienware Aurora R6 |
| hinton    |1 Geforce GTX 1080     | Alienware Aurora R6 |
| pitts     |1 Geforce GTX 1080     | Alienware Aurora R6 |
| hawkins   |1 Geforce GTX 1080 Ti  | Alienware Aurora R7 |
| lecun     |1 Geforce GTX 1080 Ti  | Alienware Aurora R7 |
| bengio    |1 Geforce GTX 1080 Ti  | Alienware Aurora R7 |

All machines are configured to use:
* CUDA 10.0
* cudnn 7
* python3.7
* tensorflow-gpu==2.0.0rc1
* pytorch
* allennlp==0.9.0


## Requirements

### Linux or MacOS
Windows is currently not supported due to uncertainty about how mounting is performed.

### Python
Tasks submitted to Ludwig must be programmed in Python 3 (the Python3.7 interpreter is used on each worker).

### Project Organization

```ludwig``` requires that the user create two special modules:
* ```src.params```: contains information about which parameters to use for each job
* ```src.config```: contains basic information like the name of the user's project

See the `Example` folder for a simple project that is compatible with `Ludwig`. 

### Access to the shared drive
See the administrator to provide access to the lab's shared drive. Mount the drive at ```/media/research_data```.
The share is hosted by the lab's file server using ```samba```, and is shared with each node. 
Because we do not allow direct shell access to nodes, all data and logs must be saved to the shared drive.

### Worker IP addresses

Upon trying to submit jobs, first-time users will notice the following error message:

```
FileNotFoundError: Please specify hostname-to-IP mappings in /home/ph/.ssh/ludwig_config
```

This means that `Ludwig` does not know the IP address of the workers to submit jobs to.
To remedy, type:

```bash
ludwig-add-ssh-config
```

## Submitting a Job

### 1) Install ludwig

In a terminal, type:

```bash
(venv) pip3 install git+https://github.com/phueb/Ludwig.git
```

### 2) The command-line tool

To submit jobs, go to your project root folder, and invoke the command-line tool that has been installed:

```bash
(venv) ludwig
``` 

Alternatively, use 

```bash
python3 -m ludwig
```

Next, check the status of the Ludwig machines:

```bash
(venv) ludwig-status
```

### Non-standard mount location

Across different operating systems, the default mount location is different.
That means that the path to the shared drive will be different.
To upload data or third-party source code to the shared drive, ```ludwig``` must be explicitly told where to find the shared drive:

For example, if `research_data` is mounted at `/Volumes/research_data`:

```
ludwig -mnt /Volumes/research_data
```
The ```-mnt``` flag is used to specify where the shared drive is mounted on the user's machine.

### Saving Data
Any data (e.g. accuracy per epoch) that needs to persist, should be returned by job.main() as a list of pandas DataFrame objects.
These will be automatically saved to the shared drive after a job has completed.

Alternatively, if the data is too big to be held in memory, it is recommended to write the data to disk,
and manually move it to the shared drive at the end of main.job(), as illustrated here: 

```python
from pathlib import Path
import shutil

def main():

    for epoch in range(10):
        data = train_epoch()
        save_to_worker(data)  # save intermediate data to worker
    
    # at end of training copy all data files to file server
    for data_path in Path('/var/sftp/ludwig/<unique_data_folder_name>').glob('data*.csv'):
        src = str(data_path)
        dst = '/media/research_data/<your_project_name>/{}'.format(data_path.name)
        shutil.move(src, dst)
```

### Logging
By default, the stdout of a submitted job will be redirected to a file located on the shared drive.
After uploading your code, verify that your task is being processed by reading the log file.
If you don't recognize the output in the file, it is likely that the node is currently processing another user's task.
Retry when the node is no longer busy. 

## Note

Calling ```ludwig``` while previously submitted jobs are still being executed, 
will stop all previously submitted jobs.