import functools
import json
import os
import pathlib
import sys

import yaml
from dotenv.main import DotEnv
from jinja2 import Environment, FileSystemLoader
from jinja2.runtime import Context

ENVIRON = os.environ
ENV_TRANS_TABLE = str.maketrans({"_": "", "-": "", ".": "_"})


def to_env_name(key):
    return key.upper().translate(ENV_TRANS_TABLE)


class EnvLookupDict(dict):
    def __init__(self, data, previous):
        self._previous = previous
        super().__init__(data)

    def __getitem__(self, key):
        parts = self._previous + [key]
        env_name = to_env_name(".".join(parts))
        if env_name in ENVIRON:
            return ENVIRON[env_name]
        try:
            result = super().__getitem__(key)
        except KeyError:
            result = {}
        if isinstance(result, dict):
            result = EnvLookupDict(result, parts)
        return result


class EnvLookupContext(Context):
    def resolve(self, key):
        env_name = to_env_name(key)
        if env_name in ENVIRON:
            return ENVIRON[env_name]
        result = super().resolve(key)
        if isinstance(result, dict):
            result = EnvLookupDict(result, [key])
        return result


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
    vars = merge_dict(vars, ENVIRON)
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
    env.context_class = EnvLookupContext
    template = env.from_string(template_text)
    return template.render(vars)
