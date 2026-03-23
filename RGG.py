from __future__ import annotations

import math
import queue
import random
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext


def generate_uniform_points(n: int, rng: random.Random):
    points = []
    for _ in range(n):
        points.append((rng.random(), rng.random()))
    return points


def construct_rgg(points, radius: float):
    n = len(points)
    graph = []
    for _ in range(n):
        graph.append([])

    radius_squared = radius * radius

    for i in range(n):
        x1, y1 = points[i]
        for j in range(i + 1, n):
            x2, y2 = points[j]
            dx = x1 - x2
            dy = y1 - y2
            if dx * dx + dy * dy <= radius_squared:
                graph[i].append(j)
                graph[j].append(i)

    return graph


def is_connected(graph) -> bool:
    n = len(graph)
    if n == 0:
        return False

    stack = [0]
    visited = [False] * n
    visited[0] = True
    reached = 1

    while stack:
        current = stack.pop()
        for neighbor in graph[current]:
            if not visited[neighbor]:
                visited[neighbor] = True
                reached += 1
                stack.append(neighbor)

    return reached == n


def estimate_connectivity_probability(n: int, r: float, t: int, rng: random.Random, logger=None) -> float:
    if n <= 0:
        raise ValueError("n must be positive.")
    if r < 0:
        raise ValueError("r must be non-negative.")
    if t <= 0:
        raise ValueError("T must be positive.")

    connected_count = 0

    for trial in range(1, t + 1):
        points = generate_uniform_points(n, rng)
        radius = r / math.sqrt(n)
        graph = construct_rgg(points, radius)

        connected = is_connected(graph)
        if connected:
            connected_count += 1

        if logger is not None:
            logger(
                "trial {:>3d}/{:<3d} | n = {:>5d} | r = {:>7.4f} | R(n) = {:>8.5f} | connected = {}".format(
                    trial, t, n, r, radius, connected
                )
            )

    probability = connected_count / t

    if logger is not None:
        logger(
            "estimated connectivity probability = {}/{} = {:.4f}".format(
                connected_count, t, probability
            )
        )

    return probability


def estimate_rc(
    n_values,
    t: int,
    p_target: float,
    eps: float,
    r_start_low: float,
    r_start_high: float,
    rng: random.Random,
    logger=None,
) -> float:

    if not n_values:
        raise ValueError("N_values must not be empty.")
    if t <= 0:
        raise ValueError("T must be positive.")
    if not (0.0 < p_target <= 1.0):
        raise ValueError("p_target must be in (0, 1].")
    if eps <= 0:
        raise ValueError("eps must be positive.")
    if r_start_low <= 0 or r_start_high <= 0:
        raise ValueError("Initial r bounds must be positive.")
    if r_start_low >= r_start_high:
        raise ValueError("r_start_low must be smaller than r_start_high.")

    rc_estimates = []

    for n in n_values:
        r_low = r_start_low
        r_high = r_start_high

        if logger is not None:
            logger("")
            logger("=== estimating r_c for n = {} ===".format(n))

        while True:
            p_low = estimate_connectivity_probability(n, r_low, t, rng, logger)
            p_high = estimate_connectivity_probability(n, r_high, t, rng, logger)

            if logger is not None:
                logger(
                    "bracket check | r_low = {:.6f}, p_low = {:.4f} | r_high = {:.6f}, p_high = {:.4f}".format(
                        r_low, p_low, r_high, p_high
                    )
                )

            if p_low >= p_target:
                r_low = r_low / 2.0
                if logger is not None:
                    logger("p_low >= p_target, shrink lower bound to {:.6f}".format(r_low))

            if p_high < p_target:
                r_high = 2.0 * r_high
                if logger is not None:
                    logger("p_high < p_target, expand upper bound to {:.6f}".format(r_high))

            if p_low < p_target and p_high >= p_target:
                break

        while (r_high - r_low) > eps:
            r_mid = (r_low + r_high) / 2.0
            p_mid = estimate_connectivity_probability(n, r_mid, t, rng, logger)

            if logger is not None:
                logger(
                    "binary search | r_low = {:.6f}, r_mid = {:.6f}, r_high = {:.6f}, p_mid = {:.4f}".format(
                        r_low, r_mid, r_high, p_mid
                    )
                )

            if p_mid >= p_target:
                r_high = r_mid
            else:
                r_low = r_mid

        rc_n = (r_low + r_high) / 2.0
        rc_estimates.append(rc_n)

        if logger is not None:
            logger("record rc_n = {:.6f}".format(rc_n))

    large_n_count = 5
    if len(rc_estimates) < large_n_count:
        selected = rc_estimates
    else:
        selected = rc_estimates[-large_n_count:]

    final_rc = sum(selected) / len(selected)

    if logger is not None:
        logger("")
        logger("large-n rc estimates used = {}".format(", ".join("{:.6f}".format(x) for x in selected)))
        logger("final estimated rc = {:.6f}".format(final_rc))

    return final_rc


class RGGApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Random Geometric Graph Connectivity")
        self.root.geometry("980x720")

        self.seed_var = tk.StringVar(value="42")
        self.n_var = tk.StringVar(value="100")
        self.r_var = tk.StringVar(value="1.6")
        self.t_var = tk.StringVar(value="20")

        self.n_values_var = tk.StringVar(value="100,200,500,1000,2000")
        self.p_target_var = tk.StringVar(value="0.95")
        self.eps_var = tk.StringVar(value="0.05")
        self.r_low_var = tk.StringVar(value="0.5")
        self.r_high_var = tk.StringVar(value="3.0")
        self.message_queue = queue.Queue()

        self._build_ui()
        self.root.after(100, self._process_ui_queue)

    def _build_ui(self):
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill=tk.X)

        row1 = tk.LabelFrame(input_frame, text="Single Connectivity Run", padx=8, pady=8)
        row1.pack(fill=tk.X, pady=5)

        self._add_labeled_entry(row1, "Seed", self.seed_var, 0, 0)
        self._add_labeled_entry(row1, "n", self.n_var, 0, 2)
        self._add_labeled_entry(row1, "r", self.r_var, 0, 4)
        self._add_labeled_entry(row1, "T", self.t_var, 0, 6)

        single_button = tk.Button(row1, text="Run Connectivity", command=self.run_single_connectivity)
        single_button.grid(row=0, column=8, padx=8, pady=4, sticky="w")

        row2 = tk.LabelFrame(input_frame, text="Estimate rc", padx=8, pady=8)
        row2.pack(fill=tk.X, pady=5)

        self._add_labeled_entry(row2, "N_values", self.n_values_var, 0, 0, width=24)
        self._add_labeled_entry(row2, "T", self.t_var, 0, 2)
        self._add_labeled_entry(row2, "p_target", self.p_target_var, 0, 4)
        self._add_labeled_entry(row2, "eps", self.eps_var, 0, 6)
        self._add_labeled_entry(row2, "r_start_low", self.r_low_var, 1, 0)
        self._add_labeled_entry(row2, "r_start_high", self.r_high_var, 1, 2)

        rc_button = tk.Button(row2, text="Estimate rc", command=self.run_estimate_rc)
        rc_button.grid(row=1, column=4, padx=8, pady=4, sticky="w")

        clear_button = tk.Button(row2, text="Clear Log", command=self.clear_log)
        clear_button.grid(row=1, column=5, padx=8, pady=4, sticky="w")

        result_frame = tk.LabelFrame(main_frame, text="Result", padx=8, pady=8)
        result_frame.pack(fill=tk.X, pady=5)

        self.result_label = tk.Label(
            result_frame,
            text="Ready. Enter parameters and click a button.",
            anchor="w",
            justify="left",
        )
        self.result_label.pack(fill=tk.X)

        log_frame = tk.LabelFrame(main_frame, text="Connectivity Record / Search Log", padx=8, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _add_labeled_entry(self, parent, label_text, text_var, row, column, width=10):
        label = tk.Label(parent, text=label_text)
        label.grid(row=row, column=column, padx=4, pady=4, sticky="e")
        entry = tk.Entry(parent, textvariable=text_var, width=width)
        entry.grid(row=row, column=column + 1, padx=4, pady=4, sticky="w")

    def log(self, message: str):
        self.message_queue.put(("log", message))

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def set_result(self, message: str):
        self.message_queue.put(("result", message))

    def show_error(self, message: str):
        self.message_queue.put(("error", message))

    def _process_ui_queue(self):
        try:
            while True:
                message_type, payload = self.message_queue.get_nowait()
                if message_type == "log":
                    self.log_text.insert(tk.END, payload + "\n")
                    self.log_text.see(tk.END)
                elif message_type == "result":
                    self.result_label.config(text=payload)
                elif message_type == "error":
                    messagebox.showerror("Input Error", payload)
        except queue.Empty:
            pass

        self.root.after(100, self._process_ui_queue)

    def _parse_int(self, value: str, field_name: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError("{} must be an integer.".format(field_name)) from exc

    def _parse_float(self, value: str, field_name: str) -> float:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError("{} must be a number.".format(field_name)) from exc

    def _parse_n_values(self, value: str):
        parts = value.split(",")
        n_values = []
        for part in parts:
            stripped = part.strip()
            if stripped:
                n_values.append(int(stripped))
        if not n_values:
            raise ValueError("N_values must contain at least one integer.")
        return n_values

    def run_single_connectivity(self):
        self._run_in_background(self._run_single_connectivity_impl)

    def run_estimate_rc(self):
        self._run_in_background(self._run_estimate_rc_impl)

    def _run_in_background(self, target):
        worker = threading.Thread(target=target, daemon=True)
        worker.start()

    def _run_single_connectivity_impl(self):
        try:
            seed = self._parse_int(self.seed_var.get(), "Seed")
            n = self._parse_int(self.n_var.get(), "n")
            r = self._parse_float(self.r_var.get(), "r")
            t = self._parse_int(self.t_var.get(), "T")

            rng = random.Random(seed)

            self.log("")
            self.log("=== single connectivity experiment started ===")
            probability = estimate_connectivity_probability(n, r, t, rng, self.log)
            radius = r / math.sqrt(n)
            self.set_result(
                "Single run complete: n = {}, r = {:.4f}, R(n) = {:.6f}, T = {}, estimated P(connected) = {:.4f}".format(
                    n, r, radius, t, probability
                )
            )
        except Exception as exc:
            self.show_error(str(exc))

    def _run_estimate_rc_impl(self):
        try:
            seed = self._parse_int(self.seed_var.get(), "Seed")
            n_values = self._parse_n_values(self.n_values_var.get())
            t = self._parse_int(self.t_var.get(), "T")
            p_target = self._parse_float(self.p_target_var.get(), "p_target")
            eps = self._parse_float(self.eps_var.get(), "eps")
            r_start_low = self._parse_float(self.r_low_var.get(), "r_start_low")
            r_start_high = self._parse_float(self.r_high_var.get(), "r_start_high")

            rng = random.Random(seed)

            self.log("")
            self.log("=== rc estimation started ===")
            final_rc = estimate_rc(
                n_values=n_values,
                t=t,
                p_target=p_target,
                eps=eps,
                r_start_low=r_start_low,
                r_start_high=r_start_high,
                rng=rng,
                logger=self.log,
            )
            self.set_result(
                "rc estimation complete: N_values = {}, T = {}, p_target = {:.3f}, final rc = {:.6f}".format(
                    n_values, t, p_target, final_rc
                )
            )
        except Exception as exc:
            self.show_error(str(exc))


def main():
    root = tk.Tk()
    app = RGGApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
