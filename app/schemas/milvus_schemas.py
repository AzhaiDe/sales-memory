#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from dataclasses import dataclass, asdict
from pymilvus import FieldSchema, CollectionSchema, DataType


@dataclass
class MemorySchemaBase:
    def to_dict(self):
        return asdict(self)


@dataclass
class MemorySchemaData(MemorySchemaBase):
    tenant_id: str
    account_id: str
    contact_id: str
    category: str
    theme: str
    fact: list
    history: list
    occur_time: int
    expire_time: int
    update_time: int
    theme_vector: list
    fact_vector: list


def get_memory_schema():
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="account_id", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="contact_id", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=1000),
        FieldSchema(name="theme", dtype=DataType.VARCHAR, max_length=1000),
        FieldSchema(name="fact", dtype=DataType.ARRAY, max_capacity=4096, element_type=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="history", dtype=DataType.ARRAY, max_capacity=4096, element_type=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="occur_time", dtype=DataType.INT64),
        FieldSchema(name="expire_time", dtype=DataType.INT64),
        FieldSchema(name="update_time", dtype=DataType.INT64),
        FieldSchema(name="theme_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(name="fact_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
    ]
    return CollectionSchema(fields=fields, description="销售记忆体集合")
