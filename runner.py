from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import graphlib
import os
import hashlib
import argparse
import shutil
import json
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED


@dataclass(frozen=True)
class Task:
    command: str
    input: tuple[Path | Task, ...]
    output: tuple[Path, ...]
    group_name: str
    cache: bool = True
    timeout: float = 0.0

    # Returns a hash integer of the (possibly empty) tuple[Path|Task]
    # In case Path is a file, it hashes the file content.
    # In case Path is a directory, it hashes all the files and subdirectories, recursively.
    # In case a Task is in the tuple, it hashes the Task using task.hash.
    # In case the tuple is empty, it return 0.
    @staticmethod
    def inouthash(items: tuple[Path | Task, ...] = ()) -> int:
        if not items:
            return 0

        def _file_hash(path: Path) -> bytes:
            # return hashlib.sha256(path.read_bytes()).digest() #Slow.
            stat = path.stat()
            data = f"{stat.st_mtime_ns}:{stat.st_size}".encode()
            return hashlib.sha256(data).digest()
        digest = hashlib.sha256()

        for item in items:
            if isinstance(item, Task):
                pass
            # digest.update(str(item.inouthash()).encode())
            elif isinstance(item, Path):
                if item.is_file():
                    digest.update(str(item).encode())
                    digest.update(_file_hash(item))
                elif item.is_dir():
                    digest.update(str(item).encode())
                    for path in sorted(item.rglob("*")):
                        digest.update(str(path.relative_to(item)).encode())
                        if path.is_file():
                            digest.update(_file_hash(path))
                else:
                    digest.update(str(item).encode())
            else:
                raise TypeError(f"Unsupported input type: {type(item)}")

        return int.from_bytes(digest.digest(), byteorder="big")

    # Execute the Task
    def execute(self, use_cache: bool = True, verbose: bool = False):
        if use_cache:
            print(f"Cached : {self}")
            return

        print(f"Execute: {self}")

        # # Create the output directory if it does not yet exist.
        for output in self.output:
            os.makedirs(output.parent, exist_ok=True)
        after = self.timeout if self.timeout > 0 else None
        # command = shlex.split(self.command) # For Linux?
        result = subprocess.run(self.command,
                                check=True,
                                capture_output=True,
                                text=True,
                                timeout=after)
        # Check if output is created.
        for output in self.output:
            if not output.exists():
                print(f"Warning: Task did not create {output}!")
        return result

    # Removes all produced outputs (if any)
    def clean(self):
        print(f"Clean: {self}")
        for out in self.output:
            if not out.exists():
                continue
            if out.is_file():
                out.unlink(missing_ok=True)
            elif out.is_dir():
                shutil.rmtree(out)

            # Recursively delete parent directory, given that they are empty.
            for dir in out.parents:
                if len(list(dir.iterdir())) == 0:
                    dir.rmdir()

    # Returns true iff all output files are present
    def output_exists(self):
        for out in self.output:
            if not out.exists():
                return False
        return True

    # Returns true iff all input files are present
    def input_exists(self):
        for inp in self.input:
            if isinstance(inp, Task):
                if not inp.input_exists():
                    return False
            elif not inp.exists():
                return False
        return True

    def __repr__(self):
        return f"<Task {self.group_name} {self.command.replace('  ', '')}>"


class Runner:
    def __init__(self):
        self._dgraph: dict[Task, dict[Task]] = {}
        self._ts: graphlib.TopologicalSorter
        self._taskcache = {}

        self._cachefile = Path(".git/runner.json")

        if not self._cachefile.exists():
            return
        # Load Task signatures from file.
        with self._cachefile.open("r", encoding="utf-8") as f:
            self._taskcache = json.load(f)

    # Retrieve and set Task signatures to file.
    def _dump_task_cache(self):
        signatures = {
            str(task): task.inouthash(task.input) + task.inouthash(task.output)
            for task in self._dgraph
        }
        with open(self._cachefile, "w", encoding="utf-8") as f:
            json.dump(signatures, f, indent=4)

    # Conversion helper function.
    def _as_tuple(self, value):
        if value is None:
            return ()
        elif isinstance(value, str):
            return (Path(value), )
        elif isinstance(value, (tuple, list)):
            return tuple(Path(val) if isinstance(val, str) else val for val in value)
        return (value,)

    # Add a task.
    def task(
        self,
        command: str,
        input: Path | Task | tuple[Path |
                                   Task, ...] | list[Path | Task] | None = None,
        output: Path | tuple[Path, ...] | list[Path] | None = None,
        group_name: str = "",
        cache: bool = True,
        timeout: float = 0.0
    ) -> Task:
        tinput = self._as_tuple(input)
        task = Task(
            command=command,
            input=tinput,
            output=self._as_tuple(output),
            group_name=group_name,
            cache=cache,
            timeout=timeout
        )
        self._dgraph[task] = {dep for dep in tinput if isinstance(dep, Task)}
        return task

    # Get all the task in a group
    def tasksWithName(self, group_name:str):
        return tuple(task for task in self._dgraph.keys() if task.group_name == group_name)

    # Clean a named (sub)graph
    def clean(self, name: str) -> None:

        targets = (task for task in self._dgraph if task.group_name == name)
        if name == "all":
            self._cachefile.unlink(missing_ok=True)
            targets = list(self._dgraph.keys())
        for task in targets:
            task.clean()

    # Execute all tasks (and dependent tasks) in a subgraph. 
    def rungroup(self, name: str) -> None:
        # Get the subgraph based on group name.
        required = self._subgraph(name)

        # Topological sort of the dependency graph.
        self._ts = graphlib.TopologicalSorter(self._dgraph)
        self._ts.prepare()

        # Execute tasks concurrently while respecting dependencies
        with ThreadPoolExecutor(max_workers=self._args.threads) as executor:
            running = {}

            while self._ts.is_active():
                # Schedule tasks whose predecessors have completed
                for task in self._ts.get_ready():
                    if task in required and not self.cache_valid(task):
                        future = executor.submit(
                            task.execute, False, not self._args.verbose)
                        running[future] = task
                    else:
                        # Skip tasks we don't need, marking them done
                        self._ts.done(task)

                if running:
                    completed, _ = wait(running, return_when=FIRST_COMPLETED)
                    for future in completed:
                        task = running.pop(future)
                        self.completedTask(task)
                        self._update_task_cache(task)
                        result: subprocess.CompletedProcess = future.result()  # Propagate exceptions
                        if result:
                            if self._args.verbose or result.returncode != 0:
                                if result.stdout:
                                    print(result.stdout, flush=True)
                                if result.stderr:
                                    print(result.stderr, flush=True)
                                if result.returncode != 0:
                                    running = {}
                                    required = {}
                                    self.stop()
                        self._ts.done(task)
        print(f"Ran group: {name} with {self._args.threads} threads")

    # Find all tasks with groupname.
    def _subgraph(self, name):
        targets = {task for task in self._dgraph if task.group_name == name}

        # Collect targets and all their transitive predecessors
        required = set(targets)
        stack = list(targets)

        while stack:
            task = stack.pop()
            for predecessor in self._dgraph.get(task, ()):
                if predecessor not in required:
                    required.add(predecessor)
                    stack.append(predecessor)

        if name == "all":
            required = self._dgraph
        return required

    def stop(self):
        self._dump_task_cache()
        print("Encountered error in process!")

    # Update the task cache (right after task.execute)
    def _update_task_cache(self, task: Task):
        self._taskcache[str(task)] = Task.inouthash(
            task.input) + Task.inouthash(task.output)

    # To be used upon async task completion.
    def completedTask(self, task: Task):
        pass

    def _parse(self, required: bool = True):
        parser = argparse.ArgumentParser(
            "Runner for RVRP project.", allow_abbrev=False)
        group = parser.add_mutually_exclusive_group(required=required)
        parser.add_argument("--clean", action='store_true',
                            help="Delete all Task output. Clean slate.")
        group.add_argument("--all", action='store_true',
                           help="Execute all Tasks in the required sequence.")
        parser.add_argument("--verbose", action='store_true',
                            help="Print task console output.")
        parser.add_argument("--threads", "--j", default=1, type=int,
                            help="Integer number of threads to use (default 1).")
        parser.add_argument("--load", action='store_true')

        # Specific Task groups.
        self._unique_group_names = set(
            task.group_name for task in self._dgraph.keys() if task.group_name != "")
        for group_name in self._unique_group_names:
            group.add_argument(f"--{group_name}", action='store_true')

        self._args = parser.parse_args()

    # Returns true for a Task iff all input/output files are present AND hashes match.
    def cache_valid(self, task: Task):
        return task.output_exists() and \
            task.input_exists() and \
            self.matches_task_hash(task)

    def matches_task_hash(self, task: Task):
        return str(task) in self._taskcache and self._taskcache[str(task)] == Task.inouthash(task.input) + Task.inouthash(task.output)

    # Run the Runners. 
    def run(self):
        self._parse()
        groups = self._unique_group_names.copy()
        groups.add("all")
        for group_name in groups:
            if hasattr(self._args, group_name) and getattr(self._args, group_name, False):
                if self._args.clean:
                    self.clean(group_name)
                self.rungroup(group_name)

        self._dump_task_cache()
