#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from enum import Enum


class SenderType(Enum):
    SALESMAN = 'salesman'
    CUSTOMER = 'customer'

    def get_value(self) -> str:
        if self == SenderType.SALESMAN:
            return '销售'
        elif self == SenderType.CUSTOMER:
            return '客户'
