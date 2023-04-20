import argparse
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

from rich import progress as pg


def run_script(script_path, args):
    # Get the path to the python executable
    python_path = sys.executable
    # Run the script
    result = subprocess.run(
        [python_path, script_path] + args, capture_output=True, text=True
    )

    return result.stdout


def main(script_path, args, repetitions=100):
    epsilon_steps = [0.1, 0.5, 1.0]
    total_runs = len(epsilon_steps) * repetitions

    successes_at_epsilon_level = {epsilon: 0 for epsilon in epsilon_steps}

    with pg.Progress(
        "[progress.description]{task.description}",
        pg.BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        pg.TimeRemainingColumn(),
        pg.TimeElapsedColumn(),
        pg.MofNCompleteColumn(),
        refresh_per_second=1,
    ) as progress:
        task_epsilon = progress.add_task(
            "[red]Epsilon level...", total=len(epsilon_steps)
        )
        task_repetition = progress.add_task("[green]Repetition...", total=repetitions)

        for e_i, epsilon in enumerate(epsilon_steps):
            futures = []

            with ProcessPoolExecutor() as executor:
                # Add each repetition to the executor
                for i in range(repetitions):
                    future = executor.submit(
                        run_script,
                        script_path,
                        args + ["--seed", str(i), "--epsilon", str(epsilon)],
                    )
                    futures.append(future)

                n_finished = 0

                while n_finished < len(futures):
                    n_finished = [future.done() for future in futures].count(True)

                    progress.update(
                        task_repetition, completed=n_finished, total=len(futures)
                    )

                    percentage_of_total_completed = (
                        (e_i * repetitions) + n_finished
                    ) / total_runs

                    progress.update(
                        task_epsilon,
                        completed=percentage_of_total_completed * len(epsilon_steps),
                        total=len(epsilon_steps),
                        description=f"[red]Epsilon level: {epsilon:.0f}",
                    )

                progress.reset(task_repetition)

            for future in futures:
                if future.done() and "Scenario failed: False" in future.result():
                    successes_at_epsilon_level[epsilon] += 1

    print(successes_at_epsilon_level)


class SplitArgs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.split(","))


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repetitions", type=int, default=100, help="Number of times to run the script"
    )
    parser.add_argument("script_path", help="Path to the script to run")
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="Arguments to pass to the script"
    )
    args = parser.parse_args()
    main(args.script_path, args.args, args.repetitions)
