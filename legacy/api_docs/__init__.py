"""API Documentation Generator - Auto-generates OpenAPI/Swagger documentation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional


_TYPE_MAP = {
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "bytes": bytes, "bytearray": bytearray,
    "None": type(None), "NoneType": type(None),
}

def _safe_resolve_type(type_str: str):
    resolved = _TYPE_MAP.get(type_str)
    if resolved is not None:
        return resolved
    if "." in type_str:
        parts = type_str.rsplit(".", 1)
        import importlib
        try:
            mod = importlib.import_module(parts[0])
            return getattr(mod, parts[1], str)
        except (ImportError, AttributeError):
            return str
    return str


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class APIParameter:
    name: str
    param_type: str
    location: str
    required: bool = True
    description: str = ""
    default: Any = None
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIResponse:
    status_code: int
    description: str
    content_type: str = "application/json"
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIEndpoint:
    path: str
    method: HTTPMethod
    handler: Callable
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: list[APIParameter] = field(default_factory=list)
    request_body: dict[str, Any] | None = None
    responses: dict[int, APIResponse] = field(default_factory=dict)
    deprecated: bool = False


@dataclass
class APISchema:
    title: str
    version: str
    description: str = ""
    base_url: str = ""
    endpoints: list[APIEndpoint] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)


def api_endpoint(
    path: str,
    method: HTTPMethod,
    summary: str = "",
    description: str = "",
    tags: list[str] | None = None,
    parameters: list[APIParameter] | None = None,
    request_body: dict[str, Any] | None = None,
    responses: dict[int, APIResponse] | None = None,
    deprecated: bool = False,
):
    def decorator(func: Callable) -> Callable:
        func._api_endpoint = APIEndpoint(
            path=path,
            method=method,
            handler=func,
            summary=summary,
            description=description or func.__doc__ or "",
            tags=tags or [],
            parameters=parameters or [],
            request_body=request_body,
            responses=responses or {200: APIResponse(200, "Success")},
            deprecated=deprecated,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._api_endpoint = func._api_endpoint
        return wrapper

    return decorator


class TypeMapper:
    PYTHON_TO_OPENAPI = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        bytes: "string",
        datetime: "string",
    }

    @classmethod
    def map_type(cls, python_type: type) -> dict[str, Any]:
        if python_type in cls.PYTHON_TO_OPENAPI:
            openapi_type = cls.PYTHON_TO_OPENAPI[python_type]
            if python_type == datetime:
                return {"type": openapi_type, "format": "date-time"}
            return {"type": openapi_type}

        if hasattr(python_type, "__origin__"):
            origin = python_type.__origin__

            if origin is list or origin is list:
                args = getattr(python_type, "__args__", (str,))
                return {
                    "type": "array",
                    "items": cls.map_type(args[0]) if args else {"type": "string"}
                }

            if origin is dict or origin is dict:
                return {"type": "object"}

            if origin is Optional:
                args = getattr(python_type, "__args__", (str,))
                return cls.map_type(args[0]) if args else {"type": "string"}

        return {"type": "object"}

    @classmethod
    def model_to_schema(cls, model_class: type) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }

        if hasattr(model_class, "__dataclass_fields__"):
            for field_name, field_info in model_class.__dataclass_fields__.items():
                field_type = field_info.type
                schema["properties"][field_name] = cls.map_type(field_type)
                if field_info.default is field_info.default_factory is NotImplemented:
                    schema["required"].append(field_name)

        elif hasattr(model_class, "__annotations__"):
            for field_name, field_type in model_class.__annotations__.items():
                schema["properties"][field_name] = cls.map_type(field_type)

        return schema


class DocumentationGenerator:
    def __init__(self, title: str = "Idle-Sense API", version: str = "1.0.0"):
        self.schema = APISchema(title=title, version=version)
        self.type_mapper = TypeMapper()

    def add_endpoint(self, endpoint: APIEndpoint):
        self.schema.endpoints.append(endpoint)

    def scan_module(self, module) -> int:
        count = 0
        for name in dir(module):
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, "_api_endpoint"):
                self.add_endpoint(obj._api_endpoint)
                count += 1
        return count

    def scan_class(self, cls: type) -> int:
        count = 0
        for name in dir(cls):
            obj = getattr(cls, name)
            if callable(obj) and hasattr(obj, "_api_endpoint"):
                self.add_endpoint(obj._api_endpoint)
                count += 1
        return count

    def add_component(self, name: str, schema: dict[str, Any]):
        self.schema.components[name] = schema

    def register_model(self, model_class: type, name: str | None = None):
        component_name = name or model_class.__name__
        schema = self.type_mapper.model_to_schema(model_class)
        self.add_component(component_name, schema)

    def _endpoint_to_openapi(self, endpoint: APIEndpoint) -> dict[str, Any]:
        path_item = {
            "summary": endpoint.summary,
            "description": endpoint.description,
            "tags": endpoint.tags,
            "deprecated": endpoint.deprecated,
            "parameters": [
                {
                    "name": p.name,
                    "in": p.location,
                    "required": p.required,
                    "description": p.description,
                    "schema": p.schema or self.type_mapper.map_type(
                        _safe_resolve_type(p.param_type) if isinstance(p.param_type, str) else str
                    )
                }
                for p in endpoint.parameters
            ],
            "responses": {
                str(code): {
                    "description": resp.description,
                    "content": {
                        resp.content_type: {
                            "schema": resp.schema
                        }
                    }
                }
                for code, resp in endpoint.responses.items()
            }
        }

        if endpoint.request_body:
            path_item["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": endpoint.request_body
                    }
                }
            }

        return path_item

    def generate_openapi(self) -> dict[str, Any]:
        paths = {}

        for endpoint in self.schema.endpoints:
            if endpoint.path not in paths:
                paths[endpoint.path] = {}

            paths[endpoint.path][endpoint.method.value.lower()] = self._endpoint_to_openapi(endpoint)

        return {
            "openapi": "3.0.3",
            "info": {
                "title": self.schema.title,
                "version": self.schema.version,
                "description": self.schema.description
            },
            "servers": [
                {"url": self.schema.base_url}
            ] if self.schema.base_url else [],
            "paths": paths,
            "components": {
                "schemas": self.schema.components
            }
        }

    def generate_swagger_html(self, openapi_json: str | None = None) -> str:
        spec = openapi_json or json.dumps(self.generate_openapi(), indent=2)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.schema.title} - Swagger UI</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        const spec = {spec};
        SwaggerUIBundle({{
            spec: spec,
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ]
        }});
    </script>
</body>
</html>"""

    def generate_redoc_html(self, openapi_json: str | None = None) -> str:
        spec = openapi_json or json.dumps(self.generate_openapi(), indent=2)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.schema.title} - ReDoc</title>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</head>
<body>
    <div id="redoc-container"></div>
    <script>
        const spec = {spec};
        Redoc.init(spec, {{}}, document.getElementById('redoc-container'));
    </script>
</body>
</html>"""

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.generate_openapi(), indent=indent)

    def to_yaml(self) -> str:
        try:
            import yaml
            return yaml.dump(self.generate_openapi(), default_flow_style=False)
        except ImportError:
            return self.to_json()


class MarkdownGenerator:
    def __init__(self, doc_generator: DocumentationGenerator):
        self.doc = doc_generator

    def generate(self) -> str:
        lines = [
            f"# {self.doc.schema.title}",
            f"\n**Version:** {self.doc.schema.version}",
            ""
        ]

        if self.doc.schema.description:
            lines.extend([
                "## Overview",
                self.doc.schema.description,
                ""
            ])

        endpoints_by_tag = {}
        for endpoint in self.doc.schema.endpoints:
            tag = endpoint.tags[0] if endpoint.tags else "default"
            if tag not in endpoints_by_tag:
                endpoints_by_tag[tag] = []
            endpoints_by_tag[tag].append(endpoint)

        for tag, endpoints in endpoints_by_tag.items():
            lines.extend([
                f"## {tag.title()}",
                ""
            ])

            for endpoint in endpoints:
                method_badge = f"`{endpoint.method.value}`"
                lines.extend([
                    f"### {method_badge} {endpoint.path}",
                    ""
                ])

                if endpoint.summary:
                    lines.extend([f"**Summary:** {endpoint.summary}", ""])

                if endpoint.description:
                    lines.extend([endpoint.description, ""])

                if endpoint.parameters:
                    lines.extend([
                        "**Parameters:**",
                        "",
                        "| Name | Location | Type | Required | Description |",
                        "|------|----------|------|----------|-------------|"
                    ])
                    for p in endpoint.parameters:
                        lines.append(
                            f"| {p.name} | {p.location} | {p.param_type} | "
                            f"{'Yes' if p.required else 'No'} | {p.description} |"
                        )
                    lines.append("")

                if endpoint.request_body:
                    lines.extend([
                        "**Request Body:**",
                        "```json",
                        json.dumps(endpoint.request_body, indent=2),
                        "```",
                        ""
                    ])

                lines.extend([
                    "**Responses:**",
                    ""
                ])
                for code, resp in sorted(endpoint.responses.items()):
                    lines.append(f"- **{code}:** {resp.description}")

                lines.append("")

        return "\n".join(lines)


__all__ = [
    "HTTPMethod",
    "APIParameter",
    "APIResponse",
    "APIEndpoint",
    "APISchema",
    "api_endpoint",
    "TypeMapper",
    "DocumentationGenerator",
    "MarkdownGenerator",
]
