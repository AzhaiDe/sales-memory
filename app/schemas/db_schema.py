#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from sqlalchemy import String, Column, BigInteger, Text, TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    updated_by = Column(String(255), nullable=False, comment='更新者')
    created_by = Column(String(255), nullable=False, comment='创建者')
    create_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False, comment='创建时间')
    update_time = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(),
                         nullable=False, comment='更新时间')


class ActivateMemoryEntity(Base):
    __tablename__ = "t_activate_memory"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(255), nullable=False, comment='标识属于哪个租户')
    prompt_config = Column(Text, nullable=False, comment='prompt 相关的配置，防止 prompt 过长')
    resource_config = Column(Text, nullable=False, comment='外部资源相关的配置，比如引用的知识库等')
