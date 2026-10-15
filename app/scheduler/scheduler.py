#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config.setting import schedule_param
from app.scheduler.base import Singleton
from app.scheduler.delete_expired_memory import delete_schedule_task


class SchedulerTask(object, metaclass=Singleton):
    def __init__(self):
        self.scheduler = None

    def init_schedule(self):
        self.scheduler = BackgroundScheduler(
            executors={'default': ThreadPoolExecutor(10)},
            job_defaults={'coalesce': False, 'max_instances': 1}
        )

    def add_scheduler_task(self):
        self.scheduler.add_job(
            delete_schedule_task,
            CronTrigger(hour=schedule_param.delete_expired_memory_trigger.get("hour"),
                        minute=schedule_param.delete_expired_memory_trigger.get("minute")),
            kwargs={"delete_info": schedule_param.delete_expired_memory_param}
        )

    def start(self):
        self.init_schedule()
        self.add_scheduler_task()
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()
