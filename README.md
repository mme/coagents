# Athena: Remote Actions Preview

## Preview Packages:

```jsx
@copilotkit/react-core@1.1.1-feat-runtime-remote-actions.0
@copilotkit/react-textarea@1.1.1-feat-runtime-remote-actions.0
@copilotkit/react-ui@1.1.1-feat-runtime-remote-actions.0
@copilotkit/runtime@1.1.1-feat-runtime-remote-actions.0
@copilotkit/runtime-client-gql@1.1.1-feat-runtime-remote-actions.0
@copilotkit/shared@1.1.1-feat-runtime-remote-actions.0
```

## How to run the demo

Check out this branch of CopilotKit:

https://github.com/CopilotKit/CopilotKit/tree/feat/runtime-remote-actions

Check out this branch of the python SDK

https://github.com/mme/coagents/tree/athena-preview

1. In CopilotKit
   1. `turbo run dev`
   2. `cd examples/next-openai && pnpm example-dev`
2. In the python SDK
   1. `poetry install`
   2. `poetry run demo`
3. Go to http://localhost:3000/presentation
4. Ask “What is the weather in Vienna?”
5. Answer comes from Python (Cloudy with a chance of hail)
6. Relevant code:
   1. https://github.com/mme/coagents/blob/43c73377f01c25e332f187fb88013d7c36d0daff/coagents/demo.py#L16
      1. This is where the remote functions are set up `CopilotKitSDK`
      2. Add the endpoint to FastAPI `add_fastapi_endpoint(app, sdk, "/copilotkit")`
   2. https://github.com/CopilotKit/CopilotKit/blob/00be2037ed24e8cdf5d3b0a879a774bcacd13d50/CopilotKit/examples/next-openai/src/app/api/copilotkit/route.ts#L45
      1. Remote actions url is defined here: `remoteActions: [{ url: "http://localhost:8000/copilotkit" }],`
