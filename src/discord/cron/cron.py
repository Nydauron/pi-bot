import asyncio
from datetime import datetime, timedelta
from src.discord.globals import SERVER_TZ
from typing import Dict, Tuple, Optional

from bot import PiBot
from src.mongo import mongo

from typing import Any
from src.discord.cron.action import CronJob, ACTION_BINDINGS

class TaskAlreadyScheduledError(Exception):
    pass

class TaskDelayTooLongError(Exception):
    pass

class CronManager():
    __max_days_delay = 30
    __next_id = 1
    __tasks: Dict[int, Tuple[CronJob, Optional[asyncio.Task]]] # [id (prob some counter that inc by 1 starting from 1 or somethin)] -> (CronJob, Optional[Task])

    def __init__(self):
        self.__tasks = {}

    @staticmethod
    async def new(bot: PiBot):
        manager = CronManager()
        await manager.__init_read_db(bot)
        return manager

    async def __init_read_db(self, bot: PiBot):
        crons = []
        async with await mongo.start_session() as s:
            async with s.start_transaction():
                # Downside of this is that we need to make n database calls given n different types of actions in order for this to work
                # This also needs to be within a transaction to ensure atomicity across all the reads
                for action, cls in ACTION_BINDINGS.items():
                    crons.extend(await CronJob.find(CronJob.action_type == action, session=s).project(cls).to_list())
                s.commit_transaction()

        crons.sort(key=lambda x: x.id)

        tasks = {}
        for i, c in enumerate(crons, start=1):
            tasks[i] = (c, None)

        self.__tasks, self.__next_id = tasks, len(crons) + 1
        self.batch_schedule_jobs(bot)

    # spawns an async thread to handle
    def schedule_job(self, bot: PiBot, job_id: int):
        (job, t) = self.__tasks[job_id] # KeyError can be raised
        if t:
            raise TaskAlreadyScheduledError(f"Task id {job_id} has already been scheduled")

        diff = job.exec_at - SERVER_TZ.localize(datetime.now())
        if diff > timedelta(days=self.__max_days_delay):
            raise TaskDelayTooLongError(f"Task id {job_id} has a wait time longer than {self.__max_days_delay} days")

        task = asyncio.create_task(job.wait(bot))

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

    await mongo.setup()
    await init_beanie(database=mongo.client["data"], document_models=[CronJob])

    manager = await CronManager.new(bot)

    c1 = MuteAction.new(user=169985743987408897, exec_at=SERVER_TZ.localize(datetime.now() + timedelta(seconds=60)))
    c2 = UnmuteAction.new(user=169985743987408897, exec_at=SERVER_TZ.localize(datetime.now() + timedelta(seconds=30)))
    
    tid1, ok = await manager.add_task(bot, c1)
    tid2, ok = await manager.add_task(bot, c2)
    
    if not ok:
        return
    
    await asyncio.sleep(1)
    ok = manager.cancel_task(tid1)
    if ok:
        print(f"Cancelled task id {tid1}")
    await asyncio.sleep(9)

async def test_add_from_db():
    from src.discord.cron.action import MuteAction, UnmuteAction
    from bot import bot
    from beanie import init_beanie

    await mongo.setup()
    await init_beanie(database=mongo.client["data"], document_models=[CronJob])

    manager = await CronManager.new(bot)

    await asyncio.sleep(100)
