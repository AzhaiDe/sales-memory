"""集中管理所有prompt模板名称"""
from enum import Enum


class PromptType(Enum):
    EXTRACT_FACT = "extract_fact"
    RESOLVE_CONFLICT = "resolve_conflict"
    REWRITE_QUERY = "rewrite_query"
