import os
import sys
import logging

from autogen_core import TRACE_LOGGER_NAME, ROOT_LOGGER_NAME
from loguru import logger
from datetime import timedelta

from app.config.setting import log_param


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(enable_trace: bool = False, console_output: bool = False):
    log_path = log_param.path
    os.makedirs(log_path, exist_ok=True)
    logger.remove()
    if console_output:
        logger.add(
            sys.stderr,
            level="DEBUG" if enable_trace else log_param.level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}:{line}</cyan> - <level>{message}</level>",
            filter=lambda record: (
                (record["name"] == TRACE_LOGGER_NAME and enable_trace) or
                (record["name"] != TRACE_LOGGER_NAME)
            )
        )
    else:
        logger.add(
            os.path.join(log_path, "{time:YYYY-MM-DD}.log"),
            level=log_param.level,
            rotation=log_param.max_size * 1024 * 1024,
            retention=timedelta(days=log_param.keep_days),
            compression="gz" if log_param.compress else None,
            enqueue=True,
            filter=lambda record: (
                (record["name"] == TRACE_LOGGER_NAME and enable_trace) or
                (record["name"] != TRACE_LOGGER_NAME))
        )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    logging.getLogger(ROOT_LOGGER_NAME).setLevel(logging.WARNING)


configure_logging(enable_trace=log_param.autogen_logging == 'trace', console_output=log_param.mod == 'console')
