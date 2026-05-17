from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

scheduler.start()

async def reminder():

    await bot.send_message(
        chat_id=chat_id,
        text="Reminder: complete your tasks."
    )

scheduler.add_job(
    reminder,
    "interval",
    hours=6
)