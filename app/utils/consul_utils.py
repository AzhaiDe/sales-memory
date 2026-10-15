#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
import random
import re
import socket

import consul

from app.config.logger_setup import logger
from app.config.setting import consul_param, server_param


def extract_ip_port(url):
    match = re.search(r'//(\d+\.\d+\.\d+\.\d+:\d+)', url)
    if match:
        return match.group(1)
    return None


def get_service_ip_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip_address = sock.getsockname()[0]
    except Exception as ex:
        logger.error(f"获取当前服务的IP地址失败, Error: {ex}")
        raise Exception(f"获取当前服务的IP地址失败, Error: {ex}")
    finally:
        sock.close()
    logger.info(f"获取当前服务的IP为 {ip_address}")
    return ip_address


def check_advert_host(ip):
    if "default".__eq__(ip):
        ip = get_service_ip_address()
    return ip


def get_available_consul():
    host = consul_param.consul_host
    port = consul_param.consul_port
    try:
        cs = consul.Consul(host=host, port=port)
    except Exception as ex:
        logger.error(f"连接consul服务器失败. Host: {host}. Error: {ex}")
        raise consul.ConsulException(f"连接consul服务器失败. Host: {host}. Error: {ex}")
    return cs


def get_service_instance_id():
    if consul_param.consul_enable_service_name:
        ip = consul_param.consul_discovery_ip_address or get_service_ip_address()
        port = server_param.port
        return f'{consul_param.consul_discovery_service_name}-{ip}-{port}'
    else:
        return consul_param.consul_discovery_instance_id


def microservice_register():
    cs = get_available_consul()
    ip = consul_param.consul_discovery_ip_address or get_service_ip_address()
    service_name = consul_param.consul_discovery_service_name
    instance_id = consul_param.consul_discovery_instance_id
    check = consul.Check.tcp(host=ip, port=server_param.port,
                             interval=f"{consul_param.consul_config_check_timeout}s",
                             deregister=f"{consul_param.consul_config_register_timeout}s")
    try:
        cs.agent.service.register(name=service_name, service_id=instance_id, address=ip, port=server_param.port,
                                  check=check, tags=['grpc'], timeout=consul_param.consul_config_register_timeout)
        logger.info(f"注册服务{service_name}成功，instance_id为{instance_id}")
    except Exception as ex:
        logger.error(f"注册服务{service_name}失败，Error: {ex}")
        raise Exception(f"注册服务{service_name}失败，Error: {ex}")
    return instance_id


def microservice_unregister():
    service_id = consul_param.consul_discovery_instance_id
    cs = get_available_consul()
    try:
        cs.agent.service.deregister(service_id=service_id)
        logger.info(f"注销服务{service_id}成功")
    except Exception as ex:
        logger.error(f"注销服务{service_id}失败, Error: {ex}")
        raise Exception(f"注销服务{service_id}失败, Error: {ex}")


def get_available_service(name, token=None):
    cs = get_available_consul()
    datacenters = cs.catalog.service(name)[1]
    dc_list = set()
    service_list = list()
    for datacenter in datacenters:
        dc_list.add(datacenter['Datacenter'])
    for dc in dc_list:
        health_service = cs.health.service(service=name, dc=dc, token=token)[1]
        for service in health_service:
            status = service['Checks'][1]['Status']
            if status == 'passing':
                service_list.append({'ip': service['Service']['Address'], 'port': service['Service']['Port']})
    if len(service_list) <= 0:
        raise Exception(f'没有可用的{name}服务实例，请检查{name}服务是否正常运行')
    return service_list


def select_node_strategy(service_list, method='default'):
    node = 0
    if method == 'default':
        node = random.randint(0, len(service_list) - 1)
    return service_list[node]


def get_service(name, token=None, method='default', https_flag=False, only_host=False):
    try:
        service_list = get_available_service(name=name, token=token)
    except Exception as ex:
        logger.error(f'没有可用的{name}服务实例，请检查{name}服务是否正常运行, Error: {ex}')
        raise Exception(f'没有可用的{name}服务实例，请检查{name}服务是否正常运行, Error: {ex}')
    service = select_node_strategy(service_list=service_list, method=method)
    host = service['ip'] + ":" + str(service['port'])
    url = "https://" + host if https_flag else "http://" + host
    logger.info(f"成功获取{name}服务, URL: {url}")
    return host if only_host else url
