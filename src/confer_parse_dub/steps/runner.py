"""Step queue runner."""

from confer_parse_dub.exceptions import QuitRequested
from confer_parse_dub.steps.context import RunContext, Step


def run_steps(initial_steps: list[Step], context: RunContext) -> bool:
    """
    Drain the step queue until empty or the user quits.

    Steps are executed depth-first: each step's returned steps are prepended
    to the front of the queue.

    Returns True if the pipeline completed normally, False if the user quit.
    """
    queue: list[Step] = list(initial_steps)
    while queue:
        step = queue.pop(0)
        try:
            next_steps = step.execute(context)
        except QuitRequested:
            return False
        queue = next_steps + queue
    return True
