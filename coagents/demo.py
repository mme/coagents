"""Demo"""


from fastapi import FastAPI
import uvicorn
from .copilotkit.integrations.fastapi import add_fastapi_endpoint
from .copilotkit import CopilotKitSDK, Action


def check_weather(city: str):
    """Check the weather"""
    print(f"Checking weather for {city}")
    return f"The weather in {city} is Cloudy with a chance of hail."

app = FastAPI()
sdk = CopilotKitSDK(
    actions=[
        Action(
            name="checkWeather",
            handler=check_weather,
            description="Check the weather",
            parameters=[
                {
                    "name": "city",
                    "type": "string",
                    "description": "The city to check the weather for"
                }
            ]
        )
    ],
)

add_fastapi_endpoint(app, sdk, "/copilotkit")

def main():
    """Run the uvicorn server."""
    uvicorn.run("coagents.demo:app", host="127.0.0.1", port=8000, reload=True)
