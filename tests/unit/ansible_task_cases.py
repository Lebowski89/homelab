"""Small selectors for the task fragments that cannot safely run as full plays."""

from copy import deepcopy


def walk_tasks(tasks):
    for task in tasks:
        yield task
        for branch in ("block", "rescue", "always"):
            yield from walk_tasks(task.get(branch, []))


def task_section(tasks, start, end, *, purpose):
    """Select execution boundaries while preserving enclosing block directives.

    Fixture hosts intentionally cannot run live transport/account discovery.
    Fail clearly if those boundaries disappear or become ambiguous; never fall
    back to an empty fixture. Recovery blocks must run through their entry point.
    """
    ordered = list(walk_tasks(tasks))
    boundaries = []
    for label, predicate in (("start", start), ("end", end)):
        matches = [index for index, task in enumerate(ordered) if predicate(task)]
        assert len(matches) == 1, f"{purpose}: expected one {label} execution boundary, found {len(matches)}"
        boundaries.append(matches[0])
    first, last = boundaries
    assert first <= last, f"{purpose}: execution boundaries are reversed"
    selected = {id(task) for task in ordered[first : last + 1]}

    def retain(entries):
        result = []
        for task in entries:
            if "block" in task:
                children = retain(task["block"])
                if children:
                    assert not ("rescue" in task or "always" in task), f"{purpose}: use the full recovery block entry point"
                    result.append({**deepcopy(task), "block": children})
            elif id(task) in selected:
                result.append(deepcopy(task))
        return result

    result = retain(tasks)
    assert result, f"{purpose}: no executable tasks selected"
    return result
