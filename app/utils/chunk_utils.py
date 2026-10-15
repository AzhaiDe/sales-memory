#!/usr/bin/env python
# -*- coding: UTF-8 -*-


def chunk_chat_history(chat_history: list, data, token, system_token, limit):
    data_len = len(data)
    token = float(token - system_token)
    limit = float(limit - system_token)
    x_len = ((token - limit) / token) * data_len * 1.2
    if x_len > len(chat_history):
        return chat_history
    msg_new = chat_history[x_len:]
    lf = msg_new.find('\n')
    if lf > -1:
        msg_new = msg_new[lf + 1:]
    else:
        return chat_history
    return msg_new
