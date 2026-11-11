"""Keep public type contracts enforced in addition to runtime behavior."""

import inspect
import shutil
import subprocess
from pathlib import Path
from typing import Any, TypeAliasType, get_args, get_type_hints

import pytest

import kara_templater


def contains_any(annotation: object) -> bool:
    if annotation is Any:
        return True
    if isinstance(annotation, TypeAliasType):
        return contains_any(annotation.__value__)
    return any(contains_any(argument) for argument in get_args(annotation))


def test_exported_callables_declare_parameters_and_return_types():
    missing = []
    for name in kara_templater.__all__:
        value = getattr(kara_templater, name)
        if inspect.isfunction(value):
            methods = [(name, value)]
        elif inspect.isclass(value):
            methods = []
            for method_name, member in vars(value).items():
                if method_name.startswith("_") and method_name not in {
                    "__init__",
                    "__iter__",
                    "__getitem__",
                    "__call__",
                }:
                    continue
                if isinstance(member, (classmethod, staticmethod)):
                    member = member.__func__
                elif isinstance(member, property):
                    member = member.fget
                if inspect.isfunction(member):
                    methods.append((f"{name}.{method_name}", member))
        else:
            continue
        for label, function in methods:
            # Protocol installs a typing-owned synthetic constructor.
            if not function.__module__.startswith("kara_templater"):
                continue
            signature = inspect.signature(function)
            for parameter in signature.parameters.values():
                if (
                    parameter.name not in {"self", "cls"}
                    and parameter.annotation is inspect.Parameter.empty
                ):
                    missing.append(f"{label}: {parameter.name}")
            if signature.return_annotation is inspect.Signature.empty:
                missing.append(f"{label}: return")
            namespace = {**vars(kara_templater), **function.__globals__}
            for parameter, annotation in get_type_hints(
                function, globalns=namespace
            ).items():
                if contains_any(annotation):
                    missing.append(f"{label}: {parameter} contains Any")
    assert not missing, "Missing public annotations:\n" + "\n".join(missing)


def test_public_inference_and_expected_type_errors():
    ty = shutil.which("ty")
    if ty is None:
        pytest.skip("install the checks dependency group to run type contracts")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [ty, "check", "tests/typing", "--output-format", "concise"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
