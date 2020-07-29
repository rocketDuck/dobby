import functools
import json
import os
import pathlib
import re

import yaml
from dotenv.main import DotEnv
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.runtime import Context

NORMALIZATION_RE = re.compile("[^0-9a-z]")


def normalize_key(key):
    return NORMALIZATION_RE.sub("", key.lower())


def normalize_object(obj):
    if not isinstance(obj, dict):
        return obj
    return {normalize_key(k): normalize_object(v) for k, v in obj.items()}


def os_env_to_dict(env):
    result = {}
    for key, value in env.items():
        parts = key.split("_")
        current = result
        while len(parts) > 1:
            part = normalize_key(parts.pop(0))
            current = current.setdefault(part, {})
        current[normalize_key(parts[0])] = value
    return result


def load_var_file(f):
    f = pathlib.Path(f)
    ext = f.suffix
    if ext == ".env":
        data = os_env_to_dict(DotEnv(f).dict())
    else:
        with open(f) as fh:
            if ext == ".json":
                data = json.load(fh,)
            else:
                data = yaml.safe_load(fh)
        data = normalize_object(data)
    return data


def load_vars(var_files, os_environ):
    vars = [load_var_file(f) for f in var_files]
    os_environ = {
        k: v
        for k, v in os_environ.items()
        if k.split("_")[0] not in ("NOMAD", "CONSUL")
    }
    vars.append(os_env_to_dict(os_environ))
    return functools.reduce(merge_dict, vars)


def merge_dict(d1, d2):
    d1 = d1.copy()
    for key, value in d2.items():
        if isinstance(value, dict) and isinstance(d1.get(key, None), dict):
            d1[key] = merge_dict(d1[key], value)
        else:
            d1[key] = value
    return d1


def normalized_lookup_dict(d):
    return NormalizedLookupDict(
        {
            k: normalized_lookup_dict(v) if isinstance(v, dict) else v
            for k, v in d.items()
        }
    )


class NormalizedLookupDict(dict):
    def __init__(self, d):
        super().__init__(d)

    def __getitem__(self, key):
        return super().__getitem__(normalize_key(key))


class NormalizedLookupContext(Context):
    def resolve(self, key):
        return super().resolve(normalize_key(key))


def render(hcl_file, var_files, os_environ=os.environ):
    p = pathlib.Path(hcl_file)
    template_name = p.name
    search_path = p.parent

    env = Environment(
        loader=FileSystemLoader(search_path),
        autoescape=False,
        block_start_string="[%",
        block_end_string="%]",
        variable_start_string="[[",
        variable_end_string="]]",
        comment_start_string="[#",
        comment_end_string="#]",
        undefined=StrictUndefined,
    )
    # NormalizedLookupContext is needed because jinja will reconstruct the context :/
    env.context_class = NormalizedLookupContext
    template = env.get_template(template_name)
    # Call `normalized_lookup_dict` so all lookups are normalized to the correct form
    variables = normalized_lookup_dict(load_vars(var_files, os_environ))
    return template.render(variables)
