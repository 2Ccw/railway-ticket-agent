import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.getenv("OPENAI_BASE_URL"),
    timeout=20.0,
    max_retries=1,
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")