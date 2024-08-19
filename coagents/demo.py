"""Demo"""


from fastapi import FastAPI
import uvicorn
from .copilotkit.integrations.fastapi import add_fastapi_endpoint
from .copilotkit import CopilotKitSDK, Action


def check_weather(query: str): #pylint: disable=unused-argument
    """Check the weather"""
    return "The weather is cloudy with a chance of hail."

app = FastAPI()
sdk = CopilotKitSDK(
    actions=[
        Action(
            name="checkWeather",
            description="Check the weather.",
            parameters=[{
                "name": "query",
                "type": "string",
                "description": "The query to check the weather for."
            }],
            handler=check_weather,
        )
    ],
)

add_fastapi_endpoint(app, sdk, "/copilotkit")

def main():
    """Run the uvicorn server."""
    uvicorn.run("coagents.demo:app", host="127.0.0.1", port=8000, reload=True)
