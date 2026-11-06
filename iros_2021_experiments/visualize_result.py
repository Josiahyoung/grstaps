#!/usr/bin/env python3
"""Plot IROS map, planned routes and task intervals (no simulation required).

Usage: python3 iros_2021_experiments/visualize_result.py -p 1
Paths default to this script's directory, independent of the working directory.
Requires matplotlib. Static plots do not infer a flight-speed animation.
"""
import argparse
import json
import math
from pathlib import Path


def read_json(path):
    text = path.read_text(encoding="utf-8")
    if text.startswith("version https://git-lfs.github.com/spec/"):
        raise ValueError(f"{path} is a Git LFS pointer; download its actual contents first")
    return json.loads(text)


def locations(config):
    points = [(p["name"], p["coord"]) for key in ("streets", "buildings")
              for p in config[key]]
    points += [(key, config[key]["coord"]) for key in
               ("hospital", "fire_station", "construction_company")]
    return points


def collect_plans(result, config):
    plans = []
    for agent, segments in (result["solution"]["motion_plans"] or {}).items():
        for segment in segments or []:
            action = int(segment["action_index"])
            start, end = float(segment["start"]), float(segment["end"])
            if not (math.isfinite(start) and math.isfinite(end) and end >= start >= 0):
                raise ValueError(f"Invalid interval for {agent}, task {action}: {start}, {end}")
            if action < -1 or action >= len(config["tasks"]):
                raise ValueError(f"Invalid action_index: {action}")
            points = [(float(p[0]), float(p[1])) for p in segment.get("waypoints") or []]
            if not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
                raise ValueError("Non-finite waypoint")
            plans.append(dict(agent=agent, action=action, start=start, end=end, points=points))
    return plans


def check_times(result, config, plans):
    warnings = []
    schedule = {int(s["index"]): s for s in result["solution"]["schedule"] or []}
    intervals = {}
    for p in plans:
        if p["action"] < 0:
            continue
        action = p["action"]
        if action in intervals and any(abs(a-b) > 1e-4 for a, b in
                                       zip(intervals[action], (p["start"], p["end"]))):
            warnings.append(f"Task {action}: agent intervals disagree")
        intervals[action] = (p["start"], p["end"])
        s = schedule.get(action)
        if s is None or abs(float(s["start_time"])-p["start"]) > 1e-4 or abs(float(s["end_time"])-p["end"]) > 1e-4:
            warnings.append(f"Task {action}: schedule and motion_plans disagree")
    for action in range(len(config["tasks"])):
        if action not in intervals:
            warnings.append(f"Task {action}: no exported task interval")
    for before, after in config["ordering_constraints"]:
        if before in intervals and after in intervals and intervals[after][0] < intervals[before][1]-1e-4:
            warnings.append(f"Precedence violated: task {before} -> task {after}")
    for agent in {p["agent"] for p in plans}:
        seq = sorted((p for p in plans if p["agent"] == agent), key=lambda p: p["start"])
        if any(b["start"] < a["end"]-1e-4 for a, b in zip(seq, seq[1:])):
            warnings.append(f"{agent}: overlapping intervals")
    if plans and abs(max(p["end"] for p in plans)-float(result["makespan"])) > 1e-4:
        warnings.append("makespan differs from last exported interval")
    return list(dict.fromkeys(warnings))


def draw_map(ax, map_data):
    from matplotlib.patches import Polygon
    for key, color in (("roads", "#e0e5ea"), ("buildings", "#a6b4c3")):
        for polygon in map_data[key]:
            xy = [(p["x"], p["y"]) for p in polygon]
            if xy:
                ax.add_patch(Polygon(xy, closed=True, facecolor=color,
                                     edgecolor="white", linewidth=0.3, zorder=0))
    ax.autoscale_view()
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (map units)")
    ax.set_ylabel("y (map units)")
    ax.grid(alpha=0.18)


def plot(config, map_data, result, problem, output, show=False):
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle

    if result.get("solved") is not True:
        raise ValueError("Result is not solved; there is no successful plan to plot")
    pts = locations(config)
    plans = collect_plans(result, config)
    if not plans:
        raise ValueError("No motion plans were exported")
    warnings = check_times(result, config, plans)
    agents = sorted({p["agent"] for p in plans},
                    key=lambda name: int(name.rsplit("_", 1)[-1]))
    colors = {agent: plt.get_cmap("tab10")(i % 10) for i, agent in enumerate(agents)}
    fig = plt.figure(figsize=(15, 8.5), layout="constrained")
    grid = fig.add_gridspec(2, 2, width_ratios=(1, 1.25))
    overview = fig.add_subplot(grid[:, 0])
    detail = fig.add_subplot(grid[0, 1])
    gantt = fig.add_subplot(grid[1, 1])
    for ax in (overview, detail):
        draw_map(ax, map_data)
    overview.set_title("Environment overview")
    overview.legend(handles=[Patch(facecolor="#a6b4c3", label="Buildings"),
                             Patch(facecolor="#e0e5ea", label="Roads")],
                    loc="upper right", fontsize=8)
    detail.set_title("Routes and task locations (zoom)")

    used = set(config["robot_start_locations"])
    for pair in config["tasks_start_end"]:
        used.update(pair)
    focus = [(pts[i][1]["x"], pts[i][1]["y"]) for i in sorted(used)]
    for ax in (overview, detail):
        for p in plans:
            xy = p["points"]
            if not xy:
                continue
            xs, ys = zip(*xy)
            ax.plot(xs, ys, color=colors[p["agent"]], linewidth=2,
                    linestyle="--" if p["action"] == -1 else "-", zorder=3)
            if ax is detail:
                for a, b in zip(xy, xy[1:]):
                    if a != b:
                        ax.annotate("", xy=b, xytext=a,
                                    arrowprops=dict(arrowstyle="->", color=colors[p["agent"]], lw=1.8), zorder=4)
        for i in sorted(used):
            name, point = pts[i]
            ax.scatter(point["x"], point["y"], s=30, c="#172b4d", zorder=5)
            if ax is detail:
                ax.annotate(f"L{i}: {name}", (point["x"], point["y"]),
                            xytext=(0, 10 if i % 2 == 0 else -20),
                            textcoords="offset points", ha="center", fontsize=8)
    focus += [xy for p in plans for xy in p["points"]]
    xmin, xmax = min(x for x, y in focus), max(x for x, y in focus)
    ymin, ymax = min(y for x, y in focus), max(y for x, y in focus)
    span = max(xmax-xmin, ymax-ymin, 0.5)
    padding = 0.3*span
    detail.set_xlim(xmin-padding, xmax+padding)
    detail.set_ylim(ymin-padding, ymax+padding)
    overview.add_patch(Rectangle((xmin-padding, ymin-padding),
                                xmax-xmin+2*padding, ymax-ymin+2*padding,
                                fill=False, edgecolor="#d1495b", linewidth=1.5, zorder=6))
    legend = [Patch(facecolor=colors[a], label=a) for a in agents]
    detail.legend(handles=legend, fontsize=8, loc="upper right")

    rows = {a: i for i, a in enumerate(agents)}
    for p in plans:
        gantt.barh(rows[p["agent"]], p["end"]-p["start"], left=p["start"],
                   height=0.5, color=colors[p["agent"]], edgecolor="white",
                   hatch="///" if p["action"] < 0 else None,
                   alpha=0.5 if p["action"] < 0 else 0.9)
        label = "transfer" if p["action"] < 0 else f'T{p["action"]}: {config["tasks"][p["action"]]}'
        gantt.text((p["start"]+p["end"])/2, rows[p["agent"]],
                   f'{label}\n{p["start"]:g} - {p["end"]:g}',
                   ha="center", va="center", fontsize=8)
    gantt.set_yticks(range(len(agents)), agents)
    gantt.set_ylim(len(agents)-0.5, -0.5)
    gantt.set_xlim(0, max(float(result["makespan"]), max(p["end"] for p in plans), 1)*1.05)
    gantt.set_xlabel("Time (model units)")
    gantt.set_title("Robot timeline | blank = idle; hatched = transfer")
    gantt.grid(axis="x", alpha=0.25)
    title = f'IROS problem {problem} | makespan = {result["makespan"]:g}'
    if warnings:
        title += "\nWARNING: output timing checks failed (see terminal)"
    fig.suptitle(title, fontsize=15, color="#b42318" if warnings else "#172b4d")
    fig.supxlabel("Timeline uses motion_plans; each task bar includes base work and in-task movement.\n"
                  "Map polygons are context; aerial plans are not constrained to roads.", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    if show:
        plt.show()
    plt.close(fig)
    return warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--problem", type=int, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="IROS experiment directory; default: script directory")
    parser.add_argument("-m", "--map", default="test.json")
    parser.add_argument("--output", type=Path, help="PNG/PDF/SVG output path")
    parser.add_argument("--show", action="store_true", help="Also open an interactive window (requires GUI)")
    args = parser.parse_args()
    folder = args.root / "problems" / str(args.problem)
    output = args.output or folder / "visualization.png"
    try:
        config = read_json(folder / "config.json")
        result = read_json(folder / "itags_output.json")
        map_data = read_json(args.root / "maps" / args.map)
        warnings = plot(config, map_data, result, args.problem, output, args.show)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        parser.exit(1, f"Cannot plot: {error}\n")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"Saved: {output.resolve()}")
    if warnings:
        print("Plot saved with warnings; do not treat it as validated execution.")
    else:
        print("Exported timing consistency checks passed (not a collision/safety validation).")


if __name__ == "__main__":
    main()
