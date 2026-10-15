#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from transformers import AutoTokenizer


def system_tokens(tokenizer: AutoTokenizer, primary, critic):
    system_text = primary if len(primary) > len(critic) else critic
    turns_token = 1024
    return len(tokenizer.tokenize(system_text)) + turns_token


def user_tokens(tokenizer: AutoTokenizer, data: list | str):
    token = 0
    if isinstance(data, list):
        for d in data:
            token += len(tokenizer.tokenize(d))
    else:
        token += len(tokenizer.tokenize(data))
    return token
