import functools
import json
import os
import pathlib
import sys

import yaml
from dotenv.main import DotEnv
from jinja2 import Environment, FileSystemLoader


def merge_dict(current, next):
    current = current.copy()
    for key, value in next.items():
        if isinstance(value, dict) and isinstance(current.get(key, None), dict):
            current[key] = merge_dict(current[key], value)
        else:
            current[key] = value
    return current


def merge_var_files(*var_files):
    vars = []
    for fname in var_files:
        if fname == "-":
            vars.append(yaml.safe_load(sys.stdin))
        elif fname.endswith(".env"):
            vars.append(DotEnv(fname).dict())
        else:
            with open(fname) as f:
                if fname.endswith(".json"):
                    vars.append(json.load(f))
                else:
                    vars.append(yaml.safe_load(f))

    if not vars:
        return {}
    elif len(vars) == 1:
        return vars[0]
    else:
        return functools.reduce(merge_dict, vars)


def render(hcl_file, var_files):
    vars = merge_var_files(*var_files)
    vars = merge_dict(vars, os.environ)
    if hcl_file == "-":
        template_text = sys.stdin.read()
        search_path = pathlib.Path.cwd()
    else:
        with open(hcl_file, mode="r") as ftemplate:
            template_text = ftemplate.read()
        search_path = pathlib.Path(hcl_file).parent

    env = Environment(
        loader=FileSystemLoader(search_path),
        autoescape=False,
        block_start_string="[%",
        block_end_string="%]",
        variable_start_string="[[",
        variable_end_string="]]",
        comment_start_string="[#",
        comment_end_string="#]",
    )
    template = env.from_string(template_text)
    return template.render(vars)
