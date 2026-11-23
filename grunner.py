import tkinter as tk
from runner import Runner, Task

class GUIrunner(tk.Tk, Runner):

    def __init__(self):
        tk.Tk.__init__(self)
        Runner.__init__(self)

    # Overrides Runner.run with a graphical UI.
    def run(self):
        # Parse commandline arguments.
        self._parse(required=False)

        self.title("Graphical Runner")
        self.geometry("1000x700")
        self.minsize(500, 350)

        # Main layout
        self.rowconfigure(0, weight=9)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            background="white",
            highlightthickness=0
        )
        self.canvas.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        # Bindings
        self.bind("<Escape>", lambda _: self.destroy())
        self.canvas.bind("<Configure>", lambda _: self._draw_graph())
        self.canvas.bind("<Enter>", lambda _: self._draw_graph())
        self.canvas.bind("<Leave>", lambda _: self._draw_graph())
        self.canvas.bind("<Leave>", lambda _: self._draw_graph())
        self.canvas.bind("<FocusIn>", lambda _: self._draw_graph())
        self.canvas.bind("<FocusOut>", lambda _: self._draw_graph())

        # Bottom button bar (10%)
        self.button_bar = tk.Frame(self)
        self.button_bar.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        # Thread count slider
        self.button_bar.columnconfigure(
            len(self._unique_group_names) + 2,
            weight=2
        )

        thread_frame = tk.Frame(self.button_bar)
        thread_frame.grid(
            row=0,
            column=len(self._unique_group_names) + 2,
            rowspan=2,
            sticky="nsew"
        )

        self.thread_label = tk.Label(
            thread_frame,
            text=f"Threads: {self._args.threads}"
        )
        self.thread_label.pack()

        self.num_threads = tk.IntVar(value=self._args.threads)

        self.thread_slider = tk.Scale(
            thread_frame,
            from_=1,
            to=16,
            orient=tk.HORIZONTAL,
            variable=self.num_threads,
            resolution=1,
            showvalue=False,
        )
        self.thread_slider.pack(fill="x", expand=True)
        self.thread_slider.configure(
            command=lambda value: (setattr(self._args, "threads", int(float(value))),
                                   self.thread_label.config(
                                       text=f"Threads: {int(float(value))}")
            )
        )

        # Verbosity toggle
        self.verbose_var = tk.BooleanVar(value=bool(self._args.verbose))
        self.verbose_toggle = tk.Checkbutton(
            thread_frame,
            text="Verbose",
            variable=self.verbose_var,
            command=self._update_verbose
        )
        self.verbose_toggle.pack(fill="x", expand=True)

        # Make button row fill the entire bar
        self.button_bar.rowconfigure(0, weight=1)

        # All + clean button.
        self.button_bar.columnconfigure(0, weight=1)
        button = tk.Button(
            self.button_bar,
            text=f"All",
            command=lambda: self.rungroup("all") or self._draw_graph()
        )
        self.button_bar.columnconfigure(1, weight=1)
        button.grid(row=0, column=0, sticky="nsew")
        button = tk.Button(
            self.button_bar,
            text=f"Clean",
            command=lambda: self.clean("all") or self._draw_graph()
        )
        button.grid(row=1, column=0, sticky="nsew")

        # Equally distribute group buttons
        for i, group_name in enumerate(self._unique_group_names, start=2):
            self.button_bar.columnconfigure(i, weight=1)

            button = tk.Button(
                self.button_bar,
                text=group_name,
                command=lambda group_name=group_name: self.rungroup(
                    group_name) or self._draw_graph()
            )
            button.grid(
                row=0,
                column=i,
                sticky="nsew"
            )
            button = tk.Button(
                self.button_bar,
                text="Clean",
                command=lambda group_name=group_name: self.clean(
                    group_name) or self._draw_graph()
            )
            button.grid(
                row=1,
                column=i,
                sticky="nsew"
            )

        self._draw_graph()

        self.mainloop()
        self._dump_task_cache()

    def completedTask(self, task: Task):
        self._draw_graph()
        self.update_idletasks()
        self.update()

    def _calculate_layout(self):
        graph = self._dgraph
        # Calculate depth of each node
        depths = {}

        def get_depth(task):
            if task not in depths:
                dependencies = graph[task]
                depths[task] = (
                    0 if not dependencies
                    else 1 + max(get_depth(dep) for dep in dependencies)
                )
            return depths[task]

        for task in graph:
            get_depth(task)

        # Group tasks by depth
        layers = {}

        for task, depth in depths.items():
            layers.setdefault(depth, []).append(task)

        return layers

    def _update_verbose(self):
        self._args.verbose = self.verbose_var.get()

    def _task_color(self, task: Task):
        # if task.output_exists():
        #     return "yellow"
        if self.cache_valid(task):
            return "green"
        if task.input_exists():
            return "lightgreen"
        return "red"

    def _draw_graph(self):
        self.canvas.delete("all")
        self.title(f"Graphical Runner with {self._args.threads} threads. Verbosity {self._args.verbose}")
        layers = self._calculate_layout()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 1 or height <= 1:
            return

        margin = 50
        radius = 20

        max_depth = max(layers.keys(), default=0)

        positions = {}

        # Calculate node positions
        for depth, nodes in layers.items():

            x = (
                margin + radius
                if max_depth == 0
                else margin + (width - 2 * margin) * depth / max_depth
            )

            spacing = (height - 2 * margin) / (len(nodes) + 1)

            for i, task in enumerate(nodes):
                y = margin + spacing * (i + 1)
                positions[task] = (x, y)

        # Draw dependency edges first
        for task, dependencies in self._dgraph.items():
            x1, y1 = positions[task]

            for dep in dependencies:
                x2, y2 = positions[dep]

                self.canvas.create_line(
                    x1, y1, x2, y2,
                    fill="grey",
                    width=2,
                    arrow=tk.LAST
                )

        # Draw nodes
        for task, (x, y) in positions.items():

            self.canvas.create_oval(
                x - radius, y - radius,
                x + radius, y + radius,
                fill=self._task_color(task),
                outline="black",
                width=2
            )

            self.canvas.create_text(
                x, y + radius + 12,
                text=task.group_name,
                fill="black"
            )