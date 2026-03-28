"""Test Generator - Auto-generates tests from code analysis."""

from __future__ import annotations

import ast
import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class TestType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    EDGE_CASE = "edge_case"
    ERROR_HANDLING = "error_handling"
    PROPERTY = "property"


@dataclass
class ParameterInfo:
    name: str
    type_hint: str | None = None
    default_value: str | None = None
    is_required: bool = True


@dataclass
class FunctionInfo:
    name: str
    module: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    return_type: str | None = None
    docstring: str | None = None
    is_async: bool = False
    is_method: bool = False
    decorators: list[str] = field(default_factory=list)
    raises: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    module: str
    methods: list[FunctionInfo] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    docstring: str | None = None


@dataclass
class GeneratedTest:
    test_name: str
    test_type: TestType
    test_code: str
    imports: list[str] = field(default_factory=list)
    fixtures: list[str] = field(default_factory=list)
    description: str = ""


class CodeAnalyzer:
    def __init__(self):
        self._type_map = {
            "int": "0",
            "float": "0.0",
            "str": '""',
            "bool": "False",
            "list": "[]",
            "dict": "{}",
            "set": "set()",
            "tuple": "()",
            "None": "None",
        }

    def analyze_function(self, func: Callable) -> FunctionInfo:
        sig = inspect.signature(func)
        params = []

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            type_hint = None
            if param.annotation != inspect.Parameter.empty:
                type_hint = str(param.annotation)

            default_value = None
            is_required = True
            if param.default != inspect.Parameter.empty:
                default_value = repr(param.default)
                is_required = False

            params.append(ParameterInfo(
                name=name,
                type_hint=type_hint,
                default_value=default_value,
                is_required=is_required
            ))

        return_type = None
        if sig.return_annotation != inspect.Signature.empty:
            return_type = str(sig.return_annotation)

        return FunctionInfo(
            name=func.__name__,
            module=func.__module__,
            parameters=params,
            return_type=return_type,
            docstring=inspect.getdoc(func),
            is_async=inspect.iscoroutinefunction(func)
        )

    def analyze_class(self, cls: type) -> ClassInfo:
        methods = []
        attributes = []

        for name in dir(cls):
            if name.startswith("_") and not name.startswith("__"):
                continue

            obj = getattr(cls, name)

            if callable(obj):
                try:
                    func_info = self.analyze_function(obj)
                    func_info.is_method = True
                    methods.append(func_info)
                except Exception:
                    pass
            else:
                attributes.append(name)

        bases = [base.__name__ for base in cls.__bases__]

        return ClassInfo(
            name=cls.__name__,
            module=cls.__module__,
            methods=methods,
            attributes=attributes,
            bases=bases,
            docstring=inspect.getdoc(cls)
        )

    def analyze_file(self, file_path: str) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        functions = []
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    func_info = self._parse_function(node)
                    functions.append(func_info)
            elif isinstance(node, ast.ClassDef):
                class_info = self._parse_class(node)
                classes.append(class_info)

        return functions, classes

    def _parse_function(self, node: ast.FunctionDef) -> FunctionInfo:
        params = []

        for arg in node.args.args:
            if arg.arg == "self":
                continue

            type_hint = None
            if arg.annotation:
                type_hint = ast.unparse(arg.annotation)

            params.append(ParameterInfo(
                name=arg.arg,
                type_hint=type_hint,
                is_required=True
            ))

        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                param_idx = len(params) - len(defaults) + i
                if param_idx >= 0:
                    params[param_idx].default_value = ast.unparse(default)
                    params[param_idx].is_required = False

        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        decorators = []
        for dec in node.decorator_list:
            decorators.append(ast.unparse(dec))

        return FunctionInfo(
            name=node.name,
            module="",
            parameters=params,
            return_type=return_type,
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators
        )

    def _parse_class(self, node: ast.ClassDef) -> ClassInfo:
        methods = []
        attributes = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                func_info = self._parse_function(item)
                func_info.is_method = True
                methods.append(func_info)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)

        bases = []
        for base in node.bases:
            bases.append(ast.unparse(base))

        return ClassInfo(
            name=node.name,
            module="",
            methods=methods,
            attributes=attributes,
            bases=bases,
            docstring=ast.get_docstring(node)
        )


class TestGenerator:
    def __init__(self, framework: str = "pytest"):
        self.framework = framework
        self.analyzer = CodeAnalyzer()
        self._type_values = {
            "int": [0, 1, -1, 100, -100],
            "float": [0.0, 1.0, -1.0, 0.5, 100.0],
            "str": ["", "test", "hello world", "a" * 100],
            "bool": [True, False],
            "list": [[], [1], [1, 2, 3], ["a", "b", "c"]],
            "dict": [{}, {"key": "value"}, {"a": 1, "b": 2}],
            "set": [set(), {1}, {1, 2, 3}],
            "tuple": [(), (1,), (1, 2, 3)],
        }

    def generate_for_function(
        self,
        func_info: FunctionInfo,
        module_path: str = ""
    ) -> list[GeneratedTest]:
        tests = []

        tests.append(self._generate_basic_test(func_info, module_path))
        tests.extend(self._generate_edge_case_tests(func_info, module_path))
        tests.extend(self._generate_error_tests(func_info, module_path))

        return tests

    def _generate_basic_test(
        self,
        func_info: FunctionInfo,
        module_path: str
    ) -> GeneratedTest:
        test_name = f"test_{func_info.name}_basic"

        args = []
        for param in func_info.parameters:
            args.append(self._get_default_value(param))

        args_str = ", ".join(str(a) for a in args)

        if func_info.is_async:
            test_code = f"""
async def {test_name}():
    \"\"\"Basic test for {func_info.name}.\"\"\"
    from {module_path} import {func_info.name}

    result = await {func_info.name}({args_str})
    assert result is not None
"""
        else:
            test_code = f"""
def {test_name}():
    \"\"\"Basic test for {func_info.name}.\"\"\"
    from {module_path} import {func_info.name}

    result = {func_info.name}({args_str})
    assert result is not None
"""

        return GeneratedTest(
            test_name=test_name,
            test_type=TestType.UNIT,
            test_code=test_code.strip(),
            description=f"Basic functionality test for {func_info.name}"
        )

    def _generate_edge_case_tests(
        self,
        func_info: FunctionInfo,
        module_path: str
    ) -> list[GeneratedTest]:
        tests = []

        for param in func_info.parameters:
            if not param.type_hint:
                continue

            type_name = self._extract_type_name(param.type_hint)
            if type_name not in self._type_values:
                continue

            for value in self._type_values[type_name]:
                test_name = f"test_{func_info.name}_{param.name}_{repr(value).replace(' ', '_')}"

                args = []
                for p in func_info.parameters:
                    if p.name == param.name:
                        args.append(repr(value))
                    else:
                        args.append(str(self._get_default_value(p)))

                args_str = ", ".join(args)

                if func_info.is_async:
                    test_code = f"""
async def {test_name}():
    \"\"\"Edge case test for {func_info.name} with {param.name}={repr(value)}.\"\"\"
    from {module_path} import {func_info.name}

    result = await {func_info.name}({args_str})
    assert result is not None
"""
                else:
                    test_code = f"""
def {test_name}():
    \"\"\"Edge case test for {func_info.name} with {param.name}={repr(value)}.\"\"\"
    from {module_path} import {func_info.name}

    result = {func_info.name}({args_str})
    assert result is not None
"""

                tests.append(GeneratedTest(
                    test_name=test_name,
                    test_type=TestType.EDGE_CASE,
                    test_code=test_code.strip(),
                    description=f"Edge case test for {func_info.name}"
                ))

        return tests[:5]

    def _generate_error_tests(
        self,
        func_info: FunctionInfo,
        module_path: str
    ) -> list[GeneratedTest]:
        tests = []

        test_name = f"test_{func_info.name}_invalid_input"

        if func_info.is_async:
            test_code = f"""
@pytest.mark.parametrize("invalid_input", [None, "", -1])
async def {test_name}(invalid_input):
    \"\"\"Error handling test for {func_info.name}.\"\"\"
    from {module_path} import {func_info.name}

    with pytest.raises((ValueError, TypeError, Exception)):
        await {func_info.name}(invalid_input)
"""
        else:
            test_code = f"""
@pytest.mark.parametrize("invalid_input", [None, "", -1])
def {test_name}(invalid_input):
    \"\"\"Error handling test for {func_info.name}.\"\"\"
    from {module_path} import {func_info.name}

    with pytest.raises((ValueError, TypeError, Exception)):
        {func_info.name}(invalid_input)
"""

        tests.append(GeneratedTest(
            test_name=test_name,
            test_type=TestType.ERROR_HANDLING,
            test_code=test_code.strip(),
            imports=["import pytest"],
            description=f"Error handling test for {func_info.name}"
        ))

        return tests

    def generate_for_class(
        self,
        class_info: ClassInfo,
        module_path: str = ""
    ) -> list[GeneratedTest]:
        tests = []

        test_name = f"test_{class_info.name}_instantiation"
        test_code = f"""
def {test_name}():
    \"\"\"Test {class_info.name} can be instantiated.\"\"\"
    from {module_path} import {class_info.name}

    instance = {class_info.name}()
    assert instance is not None
    assert isinstance(instance, {class_info.name})
"""
        tests.append(GeneratedTest(
            test_name=test_name,
            test_type=TestType.UNIT,
            test_code=test_code.strip(),
            description=f"Instantiation test for {class_info.name}"
        ))

        for method in class_info.methods:
            if method.name.startswith("_"):
                continue

            method_tests = self.generate_for_function(method, module_path)
            for test in method_tests:
                test.test_name = f"test_{class_info.name}_{method.name}"
                test.test_code = test.test_code.replace(
                    f"from {module_path} import {method.name}",
                    f"from {module_path} import {class_info.name}"
                )
                test.test_code = test.test_code.replace(
                    f"{method.name}(",
                    f"{class_info.name}().{method.name}("
                )
            tests.extend(method_tests)

        return tests

    def generate_for_file(
        self,
        file_path: str,
        output_dir: str | None = None
    ) -> str:
        functions, classes = self.analyzer.analyze_file(file_path)

        module_name = Path(file_path).stem
        module_path = module_name

        all_tests = []

        for func in functions:
            tests = self.generate_for_function(func, module_path)
            all_tests.extend(tests)

        for cls in classes:
            tests = self.generate_for_class(cls, module_path)
            all_tests.extend(tests)

        return self._assemble_test_file(all_tests, module_name)

    def _assemble_test_file(
        self,
        tests: list[GeneratedTest],
        module_name: str
    ) -> str:
        lines = [
            f'"""Auto-generated tests for {module_name}."""',
            "",
            "import pytest",
            "from unittest.mock import Mock, patch, MagicMock",
            "",
        ]

        imports = set()
        for test in tests:
            imports.update(test.imports)

        for imp in sorted(imports):
            if imp not in lines:
                lines.append(imp)

        lines.append("")

        for test in tests:
            lines.append(test.test_code)
            lines.append("")

        return "\n".join(lines)

    def _get_default_value(self, param: ParameterInfo) -> Any:
        if param.default_value is not None:
            return param.default_value

        if param.type_hint:
            type_name = self._extract_type_name(param.type_hint)
            if type_name in self._type_values:
                return self._type_values[type_name][0]

        return None

    def _extract_type_name(self, type_hint: str) -> str:
        if not type_hint:
            return ""

        match = re.match(r"(\w+)", type_hint)
        if match:
            return match.group(1)
        return ""


__all__ = [
    "TestType",
    "ParameterInfo",
    "FunctionInfo",
    "ClassInfo",
    "GeneratedTest",
    "CodeAnalyzer",
    "TestGenerator",
]
