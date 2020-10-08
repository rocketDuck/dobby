from pathlib import Path

import pytest
from dobby.templates import load_var_file, load_vars, os_env_to_dict, render


@pytest.fixture
def root():
    return Path(__file__).parent


def test_env_to_dict():
    source = {"JOB_NAME": "test", "SOME-other_var": "test", "SOMEOTHER_YETANOTHER": 42}
    result = os_env_to_dict(source)
    assert result == {
        "job": {"name": "test"},
        "someother": {"var": "test", "yetanother": 42},
    }


def test_env_to_dict_overlap():
    source = {"HOME": 42, "HOME_PATH": "test"}
    result = os_env_to_dict(source)
    assert result == {"home": {"path": "test"}}


def test_load_json(root):
    json = root / "vars/vars.json"
    data = load_var_file(json)
    assert data == {"test": {"value": 42}, "test1": 1, "test2": 2, "test3": 3}


def test_load_yaml(root):
    yaml = root / "vars/vars.yml"
    data = load_var_file(yaml)
    assert data == {"test": {"othervalue": 42}, "test1": 1, "test2": 2, "test3": 3}


def test_load_vars(root):
    yaml = root / "vars/vars.yml"
    json = root / "vars/vars.json"
    data = load_vars([yaml, json], {"teSt2": 42})
    print(data)
    assert data == {
        "test": {"value": 42, "othervalue": 42},
        "test1": 1,
        "test2": 42,
        "test3": 3,
    }


def test_simple_render(root):
    simple_template = root / "templates/simple.txt"
    simple_vars = root / "vars/simple.yml"
    data = render(simple_template, [simple_vars]).splitlines()
    assert data[0] == "job_name = test"
    assert data[1] == "database_url = testurl@yaml"


def test_env_override(root):
    simple_template = root / "templates/simple.txt"
    simple_vars = root / "vars/simple.yml"
    data = render(
        simple_template,
        [simple_vars],
        {"JOBNAME": "testenv", "ENV_PRODUCTION_DATABASEURL": "testurl@env"},
    ).splitlines()
    assert data[0] == "job_name = testenv"
    assert data[1] == "database_url = testurl@env"
