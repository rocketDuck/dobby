import functools
import json
import os
import pathlib

import yaml
from dotenv.main import DotEnv
from jinja2 import Environment, FileSystemLoader
from jinja2 import StrictUndefined as JinjaUndefined
from jinja2 import UndefinedError
from jinja2.runtime import Context
from jinja2.utils import missing

ENV_TRANS_TABLE = str.maketrans({"_": "", "-": "", ".": "_"})


def to_env_name(key):
    return key.upper().translate(ENV_TRANS_TABLE)


class StrictUndefined(JinjaUndefined):
    __slots__ = (
        "_undefined_hint",
        "_undefined_obj",
        "_undefined_name",
        "_undefined_exception",
        "_previous",
        "_os_environ",
    )

    def __init__(
        self,
        hint=None,
        obj=missing,
        name=None,
        exc=UndefinedError,
        previous=None,
        os_environ=None,
    ):
        self._previous = previous or []
        self._os_environ = os_environ or {}
        super().__init__(hint, obj, name, exc)

    def __getattr__(self, key):
        parts = self._previous + [key]
        env_name = to_env_name(".".join(parts))
        if env_name in self._os_environ:
            return self._os_environ[env_name]
        else:
            return StrictUndefined(
                self._undefined_hint,
                self._undefined_obj,
                self._undefined_name,
                self._undefined_exception,
                parts,
                self._os_environ,
            )

    __getitem__ = __getattr__


class EnvLookupDict(dict):
    def __init__(self, data, previous, os_environ):
        self._previous = previous
        self._os_environ = os_environ
        super().__init__(data)

    def __getitem__(self, key):
        parts = self._previous + [key]
        env_name = to_env_name(".".join(parts))
        if env_name in self._os_environ:
            return self._os_environ[env_name]
        try:
            result = super().__getitem__(key)
        except KeyError:
            return StrictUndefined(
                name=key, previous=parts, os_environ=self._os_environ
            )
        if isinstance(result, dict):
            result = EnvLookupDict(result, parts, self._os_environ)
        return result


class EnvLookupContext(Context):
    def resolve(self, key):
        env_name = to_env_name(key)
        if env_name in self.environment.os_environ:
            return self.environment.os_environ[env_name]
        result = super().resolve(key)
        if isinstance(result, dict):
            result = EnvLookupDict(result, [key], self.environment.os_environ)
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
    env = os.environ
    vars = []
    for fname in var_files:
        if fname.endswith(".env"):
            env.update(DotEnv(fname).dict())
        else:
            with open(fname) as f:
                if fname.endswith(".json"):
                    vars.append(json.load(f))
                else:
                    vars.append(yaml.safe_load(f))

    if not vars:
        return {}, env
    elif len(vars) == 1:
        return vars[0], env
    else:
        return functools.reduce(merge_dict, vars), env


def render(hcl_file, var_files):
    vars, os_environ = merge_var_files(*var_files)
    os_environ = {
        k: v
        for k, v in os_environ.items()
        if k.split("_")[0] not in ("NOMAD", "CONSUL")
    }
    vars = merge_dict(vars, os_environ)

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
    )
    env.context_class = EnvLookupContext
    env.os_environ = os_environ
    template = env.get_template(template_name)
    return template.render(vars)
