#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from dataclasses import dataclass, asdict
from typing import List, Any


@dataclass
class PromptInputBase:
    def to_dict(self):
        return asdict(self)


@dataclass
class ExtractFactData(PromptInputBase):
    context: str


@dataclass
class ResolveConflictData(PromptInputBase):
    old_memory: List[Any]
    new_info: List[Any]


@dataclass
class RewriteQueryData(PromptInputBase):
    context: str
    latest_msg: str


@dataclass
class PromptConfig(object):
    role: str
    name: str
    config: any

    def to_dict(self):
        return asdict(self)

    @classmethod
    def to_class(cls, content: dict) -> 'PromptConfig':
        return PromptConfig(**content)


@dataclass
class ResourceConfig(object):
    @dataclass
    class Knowledge(object):
        name: str
        role: str
        tool: str
        params: any

        @classmethod
        def to_class(cls, content: dict) -> 'ResourceConfig.Knowledge':
            return ResourceConfig.Knowledge(**content)

    knowledge: list

    def to_dict(self):
        return asdict(self)

    @classmethod
    def to_class(cls, content: dict) -> 'ResourceConfig':
        knowledges: list = []
        for item in content.get("knowledge", []):
            knowledges.append(ResourceConfig.Knowledge.to_class(item))
        return ResourceConfig(knowledge=knowledges)
