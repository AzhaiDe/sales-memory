#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
from datetime import datetime
import re
import pytz

from app.enums.mem_types import MemType


def timestamp_to_datetime(timestamp_ms):
    timestamp = timestamp_ms / 1000.0
    shanghai_tz = pytz.timezone('Asia/Shanghai')
    dt_object = datetime.fromtimestamp(timestamp, shanghai_tz)
    return dt_object.strftime('%Y-%m-%d %H:%M:%S')


def prompt_log(task_name: str, **kwargs):
    log_dict = {"task_name": task_name}
    if kwargs:
        for key, value in kwargs.items():
            log_dict[key] = value
    return json.dumps(log_dict, ensure_ascii=False)


def extract_content(text):
    pattern = r'<answer.*?>(.*?)</answer>'
    matches = re.findall(pattern, text)
    return ''.join(matches)


def get_memory_type(memory_type: int):
    if MemType.ONLINE.value == memory_type:
        return "_online"
    elif MemType.ACTIVATE.value == memory_type:
        return "_activate"
    elif MemType.MERGE.value == memory_type:
        return "_merge"
    else:
        return ""
