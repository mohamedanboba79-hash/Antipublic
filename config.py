import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "8823800504:AAGrWZWcIYi-j_rXRsAWvf7EZcxsRW8jN0g")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://antipublic.onrender.com")

MAX_FILE_SIZE = 10 * 1024 * 1024
