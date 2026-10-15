#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from enum import IntEnum, Enum


class MemType(IntEnum):
    ONLINE = 0
    ACTIVATE = 1
    MERGE = 2


class ActionType(Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    NONE = "NONE"
