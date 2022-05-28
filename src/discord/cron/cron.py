import asyncio
from datetime import datetime, timedelta
from src.discord.cron.action import CronAction
from typing import Dict, Tuple, Optional
from bot import PiBot
from src.mongo import mongo
from beanie import Document

class TaskAlreadyScheduledError(Exception):
    pass

class TaskDelayTooLongError(Exception):
    pass

class CronJob(Document):
    job: CronAction
    exec_at: datetime

    class Settings:
        name = "cron"

    async def exec(self, bot: PiBot):
        # When exec is called, we are assuming that self.exec_datetime - datetime.now() is <= 30 days

        # Since there is an upper limit of 48 days for asyncio.sleep(), we need to find a way to circumvent this for larger wait times
        # An easy solution might be to just poll once every 30 days to see if there are any upcoming jobs and schedule them

        diff = self.exec_at - datetime.now()
        while diff > timedelta():
            await asyncio.sleep(diff.total_seconds())
            diff = self.exec_at - datetime.now()

        await self.exec_now(bot)

    async def exec_now(self, bot: PiBot):
        await self.job.exec(bot)

class CronManager():
    __max_days_delay = 30
    __next_id = 1
    __tasks: Dict[int, Tuple[CronJob, Optional[asyncio.Task]]]

    def __init__(self):
        self.__tasks: Dict[int, Tuple[CronJob, Optional[asyncio.Task]]] = {} # [id (prob some counter that inc by 1 starting from 1 or somethin)] -> (CronJob, Optional[Task])
        pass
    
    # spawns an async thread to handle
    def schedule_job(self, bot: PiBot, job_id: int):
        (job, t) = self.__tasks[job_id] # KeyError can be raised
        if t:
            raise TaskAlreadyScheduledError(f"Task id {job_id} has already been scheduled")

        diff = job.exec_at - datetime.now()
        if diff > timedelta(days=self.__max_days_delay):
            raise TaskDelayTooLongError(f"Task id {job_id} has a wait time longer than {self.__max_days_delay} days")

        task = asyncio.create_task(job.exec(bot))
        
        self.__tasks[job_id] = (job, task)
        asyncio.create_task(self.__cleanup_task(job_id, task))
    
    async def __cleanup_task(self, job_id: int, task: asyncio.Task):
        await asyncio.wait({task})

        if job_id in self.__tasks and self.__tasks[job_id][1] == task:
            # do some logging here as well idk
            await self.__tasks[job_id][0].delete()
            del self.__tasks[job_id]

    async def add_task_no_db(self, bot: PiBot, job: CronJob) -> Tuple[int, bool]:
        '''
        (id, ok): Tuple[int, bool]
        id == human indentifiable id
        ok == True == task was written to database successfully, ok == False == task was not written successfully

        if ok == False, id should be ignored
        '''

        id = self.__next_id
        self.__tasks[id] = (job, None)
        self.__next_id += 1

        # Schedule the task with schedule_job
        try:
            self.schedule_job(bot, id)
        except KeyError:
            # if this error occurs, idk what to say
            return (0, False)
        except TaskAlreadyScheduledError: # if it has already been scheduled, then the db insert is redundant
            pass # need to go over logic to be sure this is correct
        except TaskDelayTooLongError:
            pass
        return (id, True)

    async def add_task(self, bot: PiBot, job: CronJob) -> Tuple[int, bool]:
        '''
        (id, ok): Tuple[int, bool]
        id == human indentifiable id (NOT mongo id)
        ok == True == task was written to database successfully, ok == False == task was not written successfully

        if ok == False, id should be ignored
        '''
        
        async with await mongo.start_session() as s:
            async with s.start_transaction():
                try:
                    # this needs to happen early bc mongo needs to generate _id
                    # this is mainly the reason why we are using a transaction here
                    await job.insert(session=s)
                except Exception:
                    # add some logging stuff here
                    s.abort_transaction()
                    return (0, False)
                print(job)
                tid, ok = await self.add_task_no_db(bot, job)
                
                if not ok:
                    # more logging stuff
                    s.abort_transaction()
                    return (0, False)
                s.commit_transaction()
                return (tid, True)

    def cancel_task(self, job_id) -> bool:
        if job_id not in self.__tasks:
            return False
        self.__tasks[job_id][1].cancel()
        return True

    # Should run every 30 days to circumvent asyncio.sleep restrictions
    def batch_schedule_jobs(self, bot: PiBot):
        for id, t in self.__tasks.items():
            if not t[1]:
                self.schedule_job(bot, id)

async def test_add():
    from src.discord.cron.action import MuteAction, UnmuteAction
    from bot import bot
    from beanie import init_beanie
    
    manager = CronManager()

    await mongo.setup()
    await init_beanie(database=mongo.client["data"], document_models=[CronJob])

    c1 = CronJob(job=MuteAction(169985743987408897), exec_at=datetime.now() + timedelta(seconds=2))
    c2 = CronJob(job=UnmuteAction(169985743987408897), exec_at=datetime.now() + timedelta(seconds=4))
    
    tid1, ok = await manager.add_task(bot, c1)
    tid2, ok = await manager.add_task(bot, c2)
    
    if not ok:
        return
    
    await asyncio.sleep(1)
    ok = manager.cancel_task(tid1)
    if ok:
        print(f"Cancelled task id {tid1}")
    await asyncio.sleep(9)
