# Python Pipeline Runner

A lightweight, dependency-aware task orchestration framework written in Python for automating, monitoring, and managing computational workflows.

Python Pipeline Runner provides automatic dependency resolution, incremental execution, caching, parallel processing, and a graphical interface for visualizing and controlling pipelines.

It is particularly suited to software compilation, dataset generation, computational experiments, optimization, and research workflows.

## Features

- **Dependency Management:** Automatically resolves task execution order using a directed acyclic graph (DAG).
- **Incremental Execution:** Skips tasks whose inputs and outputs have not changed.
- **Automatic Caching:** Stores task signatures to avoid unnecessary recomputation.
- **Parallel Execution:** Runs independent tasks concurrently while respecting dependencies.
- **Flexible I/O:** Supports files, directories, and dependencies between tasks.
- **Task Grouping:** Organizes tasks into groups that can be executed or cleaned independently.
- **Timeouts:** Supports individual task execution time limits.
- **Graphical Interface:** Visualizes dependencies and monitors task execution through Tkinter.
- **Command-Line Interface:** Provides convenient execution and cleanup options.

## Architecture

The framework consists of three main components:

| Component | Description |
|---|---|
| `Runner` | Manages dependencies, caching, scheduling, execution, and cleanup. |
| `GUIrunner` | Extends `Runner` with a graphical interface for visualizing and controlling pipelines. |

## Runner

The `Runner` class manages the complete pipeline.

### Task registration

Tasks are registered using `runner.task()`:

```python
mytask = runner.task(
    command="python script.py",
    input="data/input.csv",
    output="results/output.csv",
    group_name="Processing"
)
```

Inputs and outputs can be single paths or collections. Inputs can also reference previously defined tasks, automatically establishing dependencies. The command can be anything as long as it runs in the terminal.

### Dependency management

Dependencies are resolved using Python's built-in `graphlib.TopologicalSorter`.

The runner automatically:

- Executes prerequisites before dependent tasks.
- Identifies independent tasks that can run concurrently.
- Includes all transitive dependencies of selected task groups.
- Restricts execution to tasks required by the selected target.

### Incremental execution and caching

Task signatures are stored in:

```text
.git/runner.json
```

Before executing a task, the runner checks that:

1. All expected outputs exist.
2. All required inputs exist.
3. The current input and output signature matches the cached signature.

Tasks that satisfy these conditions are not executed.

### Parallel execution

Independent tasks are executed concurrently using `ThreadPoolExecutor`.

The maximum number of worker threads is configurable, and tasks are scheduled as soon as their dependencies are complete.

### Task grouping

Tasks can be organized into logical groups, with names such as compilation, optimization, post-processing, and analysis.

The main group-related methods are:

- `tasksWithName()`: Returns tasks belonging to a group.
- `rungroup()`: Executes a group and its prerequisites.
- `clean()`: Removes outputs associated with a group.

The special group `all` selects the entire pipeline.

### Command-line interface

The runner supports the following arguments:

| Argument | Description |
|---|---|
| `--all` | Execute the complete pipeline. |
| `--clean` | Clean the selected group before execution. |
| `--verbose` | Display task console output. |
| `--threads N` | Set the maximum number of worker threads. |
| `--GROUPNAME` | Execute a specific task group. |

Examples:

```bash
# Execute the complete pipeline
python pipeline.py --all

# Execute a specific group and its prerequisites
python pipeline.py --ALNS

# Execute using eight threads
python pipeline.py --all --threads=8

# Clean and rebuild the complete pipeline
python pipeline.py --all --clean

# Clean a subgraph containing MYGROUP tasks as leafs 
python pipeline.py --MYGROUP --clean

# Execute a group with verbose output
python pipeline.py --MYGROUP --verbose
```

## GUIrunner

`GUIrunner` extends `Runner` with a graphical interface implemented using Tkinter.

### Dependency visualization

Tasks are displayed as nodes in a directed graph, automatically arranged into layers according to dependency depth.

### Task status

Tasks are color-coded according to their current state:

| Color | Meaning |
|---|---|
| Green | Outputs exist and the cached signature is valid. |
| Light green | Inputs exist, but the task is not up to date. |
| Red | One or more required inputs are missing. |

The graph is refreshed as tasks complete.

### Interactive controls

- **All:** Executes the complete pipeline.
- **Group buttons:** Execute individual groups and their prerequisites.
- **Clean:** Removes outputs associated with the selected group.
- **Thread slider:** Adjusts the number of concurrent workers (1–16).
- **Verbose toggle:** Enables or disables console output.
- **Escape:** Closes the interface.

The window title also reflects the current thread count and verbosity setting.

## Installation

Requirements:
- Python 3.10 or newer.
- Tkinter for the graphical interface.
- No external Python dependencies.

Clone the repository:

```bash
git clone https://github.com/Nielsdejong18622/Runner.git
cd Runner
```

Verify your Python installation and Tkinter availability:

```bash
python --version
python -m tkinter
```

## Getting Started

The following example defines a simple three-stage pipeline:

```python
from pathlib import Path
from GUIrunner import GUIrunner

if __name__ == "__main__":
    runner = GUIrunner()

    # Generate a dataset
    generate = runner.task(
        command="python generate.py",
        input=Path("scripts/generate.py"),
        output=Path("data/dataset.csv"),
        group_name="Generation"
    )

    # Process the dataset
    process = runner.task(
        command="python process.py",
        input=generate,
        output=Path("results/processed.csv"),
        group_name="Processing"
    )

    # Generate a report
    runner.task(
        command="python report.py",
        input=process,
        output=Path("results/report.pdf"),
        group_name="Reporting"
    )

    runner.run()
```

Running the script opens the graphical interface, allowing you to inspect dependencies and execute individual stages.

For command-line execution without a GUI, replace `GUIrunner` with `Runner`:

```python
from runner import Runner

runner = Runner()
```


## Limitations and Considerations

- Commands use `subprocess` with `shell=True` for string commands. Only trusted command inputs should be used.
- File signatures rely on modification timestamps and sizes rather than content hashes. Changes preserving both may go undetected.
- Tasks are identified using their string representation, so task definitions should be unique.
- All relevant inputs and outputs should be declared to ensure reliable cache invalidation.
- Tasks should not concurrently modify the same outputs.
- Failed subprocess executions propagate exceptions.
- The `cache` attribute and `--load` argument are reserved and not fully integrated into execution behavior.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

**Python Pipeline Runner** – A simple and efficient framework for organizing, automating, and visualizing computational workflows.