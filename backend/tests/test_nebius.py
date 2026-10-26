import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")
model = os.getenv("NEBIUS_MODEL")

if not api_key or not model:
    raise SystemExit(
        "Missing NEBIUS_API_KEY or NEBIUS_MODEL in .env"
    )

client = OpenAI(
    api_key=api_key,
    base_url="https://api.tokenfactory.nebius.com/v1/",
    timeout=60.0,
)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: NEBIUS CONNECTION OK"
            }
        ],
        max_tokens=30,
    )

    print("Connection successful!")
    print("Model:", response.model)
    print("Response:", response.choices[0].message.content)

except Exception as error:
    print("Connection failed.")
    print(type(error).__name__ + ":", str(error))
