#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
from datetime import datetime

import orjson

from app.config.logger_setup import logger
from app.tool.ybx_contact_info import get_contact_info_ybx
from app.tool.ybx_good_info import get_good_info_ybx
from app.tool.ybx_order_info import get_order_info_ybx


def __extract_child(note, order_child):
    tm_fmt = "%Y-%m-%d"
    current_str = datetime.now().strftime('%Y-%m-%d')
    current = datetime.strptime(current_str, tm_fmt)
    note_child = {}
    if note.get('最小宝宝生日', ""):
        birthday = note["最小宝宝生日"].strip().split(' ')[0]
        b = datetime.strptime(birthday, tm_fmt)
        month = (current.year - b.year) * 12 + current.month - b.month
        note_child = {"出生日期": birthday, "月龄": month if month >= 0 else ""}

    tmp = []
    for c in order_child:
        d = datetime.strptime(c['date'], tm_fmt)
        m = c['month']
        m_div = (current.year - d.year) * 12 + current.month - d.month
        tmp.append({'month': [m[0] + m_div, m[1] + m_div], 'i': c['i']})

    child_res = []
    if tmp:
        tmp.sort(key=lambda x: x['month'][0])
        current_start, current_end = tmp[0]['month']
        tmp_result = []
        for i in range(1, len(tmp)):
            start, end = tmp[i]['month']
            if start <= current_end:
                current_start = max(current_start, start)
                current_end = min(current_end, end)
            else:
                if current_start <= current_end:
                    tmp_result.append([current_start, current_end])
                current_start, current_end = start, end
        if current_start <= current_end:
            tmp_result.append([current_start, current_end])

        result = []
        start, end = tmp_result[0]
        for i in range(1, len(tmp_result)):
            if tmp_result[i][0] - tmp_result[i - 1][1] < 12:
                end = tmp_result[i][1]
            else:
                result.append({"min": start, "max": end})
                start = i
        if end == tmp_result[-1][1]:
            result.append({"min": start, "max": end})

        c_id = 'A'
        for c in result:
            if note_child and c['min'] <= note_child['月龄'] <= c['max']:
                child_res.append({"宝宝ID": c_id, "月龄": str(note_child['月龄']) + f"(截至{current_str})"})
                note_child = {}
            else:
                child_res.append({"宝宝ID": c_id, "月龄": '-'.join([str(c['min']), str(c['max'])]) + f"(截至{current_str})"})
            c_id = chr(ord(c_id) + 1)

    if note_child:
        note_child['月龄'] = str(note_child['月龄']) + f"(截至{current_str})"
        child_res.append(note_child)

    return child_res


async def get_info_ybx(contact_id: str, tenant_id: str = "ybx", contact_name: str = "客户信息",
                       order_name: str = "订单信息", good_name: str = "商品信息") -> dict[str, str]:
    forget_cycle = 30
    nearly = 10
    goods_limit = 15

    order_raw_list = await get_order_info_ybx(contact_id, tenant_id, order_name)
    logger.info(f"order_raw_list={json.dumps(order_raw_list, ensure_ascii=False)}")

    if len(order_raw_list) == 0:
        return {"good_info": "", "order_info": "", "child_info": ""}

    order_list = []
    for item in order_raw_list:
        amount = item.get('成交金额', None)
        count = item.get("商品成交数量", None)
        price = None
        if (count is not None and count != 0 and count != '') and (amount is not None and amount != ''):
            price = float(amount) / float(count)
        order_list.append({'time': item.get('成交时间', ""), '商品条码': item.get("商品ID", ""),
                           '单价': price, '数量': count, '总价': amount})

    goods = {}
    for i in range(len(order_list) - 1, -1, -1):
        if i > len(order_list) - 1 - nearly:
            order_list[i]['nearly'] = True
        gid = order_list[i]['商品条码']
        if gid not in goods:
            good_raw_info: dict = await get_good_info_ybx(gid, tenant_id, good_name)
            good_info = {'商品条码': gid, '名称': good_raw_info.get("子规格名称", ""), '分类': good_raw_info.get("分类", ""),
                         '品牌': good_raw_info.get('品牌', ""), '适用月龄': good_raw_info.get('适用月龄', ""),
                         '单件消耗': good_raw_info.get('消耗预估', ""), '适用症状': good_raw_info.get('适用症状', "")}
            goods[gid] = {'gid': gid, 'cnt': 0, 'detail': good_info, 'order': []}
        goods[gid]['cnt'] += 1
        goods[gid]['order'].append(order_list[i])

    time_format = "%Y-%m-%d %H:%M:%S"
    start = datetime.strptime(order_list[-1]['time'], time_format)
    goods_start = []
    for i in range(len(order_list) - 1, -1, -1):
        gid = order_list[i]['商品条码']
        if gid not in goods_start:
            goods_start.append(gid)
            tm_div = start - datetime.strptime(order_list[i]['time'], time_format)
            if tm_div.days > 0:
                goods[gid]['cnt'] -= int(tm_div.days / forget_cycle)

    order_new = []
    goods_added = {}
    for i in range(len(order_list) - 1, max(len(order_list) - 1 - nearly, -1), -1):
        gid = order_list[i]['商品条码']
        if gid not in goods_added:
            goods_added[gid] = 0
        else:
            if goods[gid]['detail']:
                if goods_added[gid] > 5:
                    continue
            else:
                if goods_added[gid] > 3:
                    continue
        goods_added[gid] += 1
        order_new.append(order_list[i])

    for g in sorted(goods.values(), key=lambda x: x['cnt'], reverse=True):
        gid = g['gid']
        for o in g['order']:
            if gid in goods_added:
                if goods[gid]['detail']:
                    if goods_added[gid] > 5:
                        break
                else:
                    if goods_added[gid] > 3:
                        break
            else:
                goods_added[gid] = 0
            if o.get('nearly', False):
                continue
            goods_added[gid] += 1
            order_new.append(o)
        if len(goods_added.keys()) > goods_limit:
            logger.warning("good list is chunked")
            break

    child = []
    for i in range(len(order_new)):
        o = order_new[i]
        gid = o['商品条码']
        for key, value in goods[gid]["detail"].items():
            if key.strip() != "适用月龄":
                continue
            month = str(value).strip()
            if '-' in month:
                month = month.split('-')
                month = [month[0].strip(), month[1].strip()]
                if month[0].isdigit() and month[1].isdigit():
                    child.append({'month': [int(month[0]), int(month[1])], 'date': o['time'].split(' ')[0].strip(), 'i': i})
            elif month.isdigit():
                child.append({'month': [int(month), int(month)], 'date': o['time'].split(' ')[0].strip(), 'i': i})

    good_info_text = ''
    for gid in goods_added.keys():
        detail = goods[gid]['detail']
        if detail:
            good_info_text += orjson.dumps(detail).decode('utf-8') + '\n'

    order_infos = sorted(order_new, key=lambda x: datetime.strptime(x['time'], time_format))
    order_info_text = '\n'.join([orjson.dumps(o).decode('utf-8') for o in order_infos])

    contact_raw_info = await get_contact_info_ybx(contact_id, tenant_id, contact_name)
    child = __extract_child(note=contact_raw_info, order_child=child)
    child_info_text = '\n'.join([orjson.dumps(c).decode('utf-8') for c in child])

    return {"good_info": good_info_text, "order_info": order_info_text, "child_info": child_info_text}
