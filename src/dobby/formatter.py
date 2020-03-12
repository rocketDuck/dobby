"""
The contents of this file are a python translation of nomad/command/job_plan.go

TODO: Figure out license?
"""

import click

pm = click.style("+/- ", fg="yellow")
p = click.style("+ ", fg="green")
m = click.style("- ", fg="red")


def bold(t):
    return click.style(t, bold=True)


def q(t):
    t = str(t).replace('"', '"')
    return f'"{t}"'


ADDED = "Added"
DELETED = "Deleted"
EDITED = "Edited"

ID = "ID"
NAME = "Name"
TYPE = "Type"
FIELDS = "Fields"
OBJECTS = "Objects"
TASK_GROUPS = "TaskGroups"
TASKS = "Tasks"
ANNOTATIONS = "Annotations"
UPDATES = "Updates"


OLD = "Old"
NEW = "New"


def get_diff_string(obj):
    return {ADDED: (p, 2), DELETED: (m, 2), EDITED: (pm, 4)}.get(obj[TYPE], ("", 0))


def get_longest_prefixes(fields, objects):
    longest_field = longest_marker = 0
    for field in fields:
        longest_field = max(len(field[NAME]), longest_field)
        longest_marker = max(get_diff_string(field)[1], longest_marker)
    for object in objects:
        longest_marker = max(get_diff_string(object)[1], longest_marker)

    return longest_field, longest_marker


def format_job_diff(job, verbose=False):
    fields = job[FIELDS] or []
    objects = job[OBJECTS] or []

    marker, _ = get_diff_string(job)
    text = bold(f"Job: {q(job[ID])}")
    out = f"{marker}{text}\n"

    longest_field, longest_marker = get_longest_prefixes(fields, objects)
    for tg in job[TASK_GROUPS]:
        longest_marker = max(get_diff_string(tg)[1], longest_marker)

    if job[TYPE] == EDITED or verbose:
        fo = aligned_field_and_objects(
            fields, objects, 0, longest_field, longest_marker
        )
        out += fo
        if fo:
            out += "\n"

    for tg in job[TASK_GROUPS]:
        m_length = get_diff_string(tg)[1]
        k_prefix = longest_marker - m_length
        out += format_task_group_diff(tg, k_prefix, verbose)
        out += "\n"

    return out


def format_task_group_diff(task_group, tg_prefix, verbose):
    marker = get_diff_string(task_group)[0]
    text = bold(f"Task Group: {q(task_group[NAME])}")
    out = f"{marker}{' ' * tg_prefix}{text}"

    mapping = {
        "ignore": "green",
        "create": "green",
        "destroy": "red",
        "migrate": "blue",
        "canary": "blue",
        "in-place update": "cyan",
        "create/destroy update": "yellow",
    }

    tg_updates = task_group[UPDATES]
    if tg_updates:
        order = sorted(tg_updates)
        updates = []
        for update in order:
            count = tg_updates[update]
            if update in mapping:
                updates.append(click.style(f"{count} {update}", fg=mapping[update]))
            else:
                updates.append(f"{count} {update}")
        out += " ({})\n".format(", ".join(updates))
    else:
        out += "\n"

    fields = task_group[FIELDS] or []
    objects = task_group[OBJECTS] or []
    tasks = task_group[TASKS] or []

    longest_field, longest_marker = get_longest_prefixes(fields, objects)
    for task in tasks:
        longest_marker = max(get_diff_string(task)[1], longest_marker)

    sub_start_prefix = tg_prefix + 2
    if task_group[TYPE] == EDITED or verbose:
        fo = aligned_field_and_objects(
            fields, objects, sub_start_prefix, longest_field, longest_marker
        )
        out += fo
        if fo:
            out += "\n"

    for task in tasks:
        m_length = get_diff_string(task)[1]
        prefix = longest_marker - m_length
        out += format_task_diff(task, sub_start_prefix, prefix, verbose) + "\n"

    return out


def format_task_diff(task, start_prefix, task_prefix, verbose):
    marker = get_diff_string(task)[0]
    text = bold(f"Task: {q(task[NAME])}")
    out = f"{' ' * start_prefix}{marker}{' ' * task_prefix}{text}"
    if task[ANNOTATIONS]:
        out += f" ({color_annotations(task[ANNOTATIONS])})"

    # What is a none task?
    if task[TYPE] == "None" or task[TYPE] is None:
        return out
    elif task[TYPE] in (ADDED, DELETED) and not verbose:
        return out
    else:
        out += "\n"

    fields = task[FIELDS] or []
    objects = task[OBJECTS] or []

    sub_start_prefix = start_prefix + 2
    longest_field, longest_marker = get_longest_prefixes(fields, objects)

    out += aligned_field_and_objects(
        fields, objects, sub_start_prefix, longest_field, longest_marker
    )

    return out


def format_field_diff(diff, start_prefix, key_prefix, value_prefix):
    marker = get_diff_string(diff)[0]
    out = f"{' ' * start_prefix}{marker}{' ' * key_prefix}{diff[NAME]}: {' ' * value_prefix}"

    old = q(diff[OLD])
    new = q(diff[NEW])

    out += {ADDED: new, DELETED: old, EDITED: f"{old} => {new}"}.get(diff[TYPE], new)

    if diff[ANNOTATIONS]:
        out += f" ({color_annotations(diff[ANNOTATIONS])})"

    return out


def format_object_diff(diff, start_prefix, key_prefix):
    fields = diff[FIELDS] or []
    objects = diff[OBJECTS] or []

    start = " " * start_prefix
    marker, marker_len = get_diff_string(diff)
    out = f"{start}{marker}{' ' * key_prefix}{diff[NAME]} {{" + "\n"

    longest_field, longest_marker = get_longest_prefixes(fields, objects)
    sub_start_prefix = start_prefix + key_prefix + 2
    out += aligned_field_and_objects(
        fields, objects, sub_start_prefix, longest_field, longest_marker
    )

    end_prefix = " " * (start_prefix + marker_len + key_prefix)
    return "{}\n{}".format(out, end_prefix) + "}"


def format_alloc_metrics(metrics, scores, prefix):
    out = ""
    if metrics["NodesEvaluated"] == 0:
        out += f"{prefix}* No nodes were eligible for evaluation" + "\n"

    for dc, available in (metrics["NodesAvailable"] or {}).items():
        if available == 0:
            out += f"{prefix}* No nodes are available in datacenter {q(dc)}" + "\n"

    for klass, num in (metrics["ClassFiltered"] or {}).items():
        out += f"{prefix}* Class {q(klass)} filtered {num} nodes" + "\n"
    for cs, num in (metrics["ClassFiltered"] or {}).items():
        out += f"{prefix}* Constraint {q(cs)} filtered {num} nodes" + "\n"

    if metrics["NodesExhausted"]:
        out += (
            f"{prefix}* Resources exhausted on {metrics['NodesExhausted']} nodes" + "\n"
        )
    for klass, num in (metrics["ClassExhausted"] or {}).items():
        out += f"{prefix}* Class {q(klass)} exhausted on {num} nodes" + "\n"
    for dim, num in (metrics["DimensionExhausted"] or {}).items():
        out += f"{prefix}* Dimension {q(dim)} exhausted {num} nodes" + "\n"

    for dim in metrics["QuotaExhausted"] or []:
        out += f"{prefix}* Quota limit hit {q(dim)}" + "\n"

    # TODO implement scores = True if needed
    assert scores is False

    return out.rstrip()


def format_dry_run(resp, job):
    rolling = None
    for eval in resp["CreatedEvals"] or []:
        if eval["TriggeredBy"] == "rolling-update":
            rolling = eval

    out = ""
    failed_tg_allocs = resp["FailedTGAllocs"] or {}
    if not failed_tg_allocs:
        out = click.style(
            "- All tasks successfully allocated.\n", bold=True, fg="green"
        )
    else:
        if job[TYPE] == "system":
            out = click.style(
                "- WARNING: Failed to place allocations on all nodes.\n",
                bold=True,
                fg="yellow",
            )
        else:
            out = click.style(
                "- WARNING: Failed to place all allocations.\n", bold=True, fg="yellow"
            )

        s = sorted(failed_tg_allocs)
        for tg in s:
            metrics = failed_tg_allocs[tg]
            noun = "allocation"
            if metrics["CoalescedFailures"] > 1:
                noun += "s"

            out += click.style(
                f"{' ' * 2}Task Group {q(tg)} (failed to place {metrics['CoalescedFailures']+1} {noun}):",
                fg="yellow",
            )
            out += "\n"
            out += click.style(
                format_alloc_metrics(metrics, False, " " * 4), fg="yellow"
            )
            out += "\n\n"

        if rolling is None:
            out = out.rstrip()

    if rolling:
        out += click.style(
            f"- Rolling update, next evaluation will be in {rolling['Wait']}.",
            fg="green",
        )
        out += "\n"

    # TODO: Periodic jobs

    return out.rstrip()


def color_annotations(annotations):
    if not annotations:
        return ""

    mapping = {
        "forces create": "green",
        "forces destroy": "red",
        "forces in-place update": "cyan",
        "forces create/destroy update": "yellow",
    }

    colored = []
    for annotation in annotations:
        if annotation in mapping:
            colored.append(click.style(annotation, fg=mapping[annotation]))
        else:
            colored.append(annotation)

    return ", ".join(colored)


def aligned_field_and_objects(
    fields, objects, start_prefix, longest_field, longest_marker
):
    fields = fields or []
    objects = objects or []

    out = ""
    for i, field in enumerate(fields):
        m_length = get_diff_string(field)[1]
        k_prefix = longest_marker - m_length
        v_prefix = longest_field - len(field[NAME])
        out += format_field_diff(field, start_prefix, k_prefix, v_prefix)

        # Avoid a dangling new line
        if i + 1 != len(fields) or objects:
            out += "\n"

    for i, object in enumerate(objects):
        m_length = get_diff_string(object)[1]
        k_prefix = longest_marker - m_length
        out += format_object_diff(object, start_prefix, k_prefix)

        # Avoid a dangling new line
        if i + 1 != len(objects):
            out += "\n"

    return out
