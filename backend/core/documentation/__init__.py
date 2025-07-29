"""
Documentation and API specification modules
"""
from .openapi import (
    get_openapi_schema,
    custom_openapi,
    add_api_route_tags,
    generate_api_docs
)
from .versioning import (
    APIVersion,
    VersionedRoute,
    version_route,
    get_api_version
)
from .schemas import (
    create_example_schema,
    document_endpoint,
    add_response_examples
)

__all__ = [
    "get_openapi_schema",
    "custom_openapi",
    "add_api_route_tags",
    "generate_api_docs",
    "APIVersion",
    "VersionedRoute",
    "version_route",
    "get_api_version",
    "create_example_schema",
    "document_endpoint",
    "add_response_examples"
]