import os

from dotenv import load_dotenv

load_dotenv()


IS_RAILWAY = (
    os.getenv("RAILWAY_ENVIRONMENT")
    is not None
)


if IS_RAILWAY:

    DATABASE_URL = os.getenv(
        "DATABASE_URL"
    )

else:

    DATABASE_URL = (
        "sqlite:///planner.db"
    )


WEBHOOK_BASE_URL = os.getenv(
    "WEBHOOK_BASE_URL"
)


TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)


OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY"
)