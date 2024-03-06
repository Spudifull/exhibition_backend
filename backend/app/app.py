import logging.config
import asyncio
import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .db.mongodb_utils import close_mongo_connection, connect_to_mongo
from .routers.estimate import router as estimates_router
from .logging.logging_config import LOGGING
from .s3.file_ops import daily_backup_file
from .routers.order import router as orders_router
from .routers.room import router as rooms_router
from .routers.user import router as users_router
from .repair_tools.repare import router as repair_router
from .shedule.json_check_schedule import get_fpo_list_with_pdf
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

title = ""
app = FastAPI(
    title=title,
    servers=[
        {"url": "", "description": ""},
    ],
    root_path="/estimator-api",
    root_path_in_servers=False,
)

# TODO: set up origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()

app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("startup", lambda: scheduler.start())
app.add_event_handler("shutdown", close_mongo_connection)
app.add_event_handler("shutdown", lambda: scheduler.shutdown())


@app.on_event("startup")
async def schedule_periodic_tasks():
    """
    For example, the scheduler will run twice a day at 8 a.m. and 8 p.m.
    scheduler.add_job(periodic_task, CronTrigger(hour="8,20"))
    """
    # This cod will run the planner every hour
    scheduler.add_job(periodic_task, "interval", hours=1)
    scheduler.add_job(backup_damage_file, CronTrigger(hour=7, timezone=timezone('Europe/Moscow')))


async def periodic_task():
    try:
        await get_fpo_list_with_pdf(offset=10)
    except asyncio.CancelledError:
        logger.critical(f"The task was cancelled. Detail: "
                        f"{traceback.format_exc()}")


async def backup_damage_file():
    try:
        await daily_backup_file()
        logger.success(f"Successfully back up the damage file")
    except asyncio.CancelledError:
        logger.critical(f"The task was cancelled. Detail: "
                        f"{traceback.format_exc()}")


routers = (orders_router, rooms_router, users_router, repair_router)
for router in routers:
    app.include_router(router)


@app.get("/")
async def welcome():
    welcome_msg = f"Welcome to {title}"
    html_content = f"""
    <html>
        <head>
            <title>{title}</title>
        </head>
        <body>
            <h1>{welcome_msg}</h1>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
