"""Agents"""

from typing import Optional, List
from abc import ABC, abstractmethod
import uuid
from langgraph.graph.graph import CompiledGraph
from langchain.load.dump import dumps as langchain_dumps
from langchain.load.load import load as langchain_load

from langchain.schema import SystemMessage

from partialjson.json_parser import JSONParser

from .types import Message
from .langchain import copilotkit_messages_to_langchain


class Agent(ABC):
    """Agent class for CopilotKit"""
    def __init__(
            self,
            *,
            name: str,
            description: Optional[str] = None,
            merge_state: Optional[callable] = None
        ):
        self.name = name
        self.description = description
        self.merge_state = merge_state

    @abstractmethod
    def execute(
        self,
        *,
        state: dict,
        messages: List[Message],
        thread_id: Optional[str] = None,
        node_name: Optional[str] = None,
    ):
        """Execute the agent"""

    def dict_repr(self):
        """Dict representation of the action"""
        return {
            'name': self.name,
            'description': self.description or ''
        }

def langgraph_default_merge_state( # pylint: disable=unused-argument
        *,
        state: dict,
        messages: List[Message],
        actions: List[any]
    ):
    """Default merge state for LangGraph"""
    if len(messages) > 0 and isinstance(messages[0], SystemMessage):
        # remove system message
        messages = messages[1:]

    # merge with existing messages
    merged_messages = list(map(langchain_load, state.get("messages", [])))
    existing_message_ids = {message.id for message in merged_messages}

    for message in messages:
        if message.id not in existing_message_ids:
            merged_messages.append(message)

    return {
        **state,
        "messages": merged_messages,
        "copilotkit": {
            "actions": actions
        }
    }

class LangGraphAgent(Agent):
    """LangGraph agent class for CopilotKit"""
    def __init__(
            self,
            *,
            name: str,
            agent: CompiledGraph,
            description: Optional[str] = None,
            merge_state: Optional[callable] = langgraph_default_merge_state
        ):
        super().__init__(
            name=name,
            description=description,
            merge_state=merge_state
        )
        self.agent = agent

    def _emit_state_sync_event(
            self,
            *,
            thread_id: str,
            run_id: str,
            node_name: str,
            state: dict,
            running: bool,
            active: bool
        ):
        return langchain_dumps({
            "event": "on_copilotkit_state_sync",
            "thread_id": thread_id,
            "run_id": run_id,
            "agent_name": self.name,
            "node_name": node_name,
            "active": active,
            "state": state,
            "running": running,
            "role": "assistant"
        })

    def execute( # pylint: disable=too-many-arguments
        self,
        *,
        state: dict,
        messages: List[Message],
        thread_id: Optional[str] = None,
        node_name: Optional[str] = None,
        actions: Optional[List[any]] = None,
    ):

        langchain_messages = copilotkit_messages_to_langchain(messages)
        state = self.merge_state(
            state=state,
            messages=langchain_messages,
            actions=actions
        )

        mode = "continue" if thread_id and node_name != "__end__" else "start"
        thread_id = thread_id or str(uuid.uuid4())

        config = {"configurable": {"thread_id": thread_id}}
        if mode == "continue":
            self.agent.update_state(config, state, as_node=node_name)

        return self._stream_events(
            mode=mode,
            thread_id=thread_id,
            state=state,
            node_name=node_name
        )

    async def _stream_events(
            self,
            *,
            mode: str,
            thread_id: str,
            state: dict,
            node_name: Optional[str] = None
        ):

        config = {"configurable": {"thread_id": thread_id}}
        streaming_state_extractor = _StreamingStateExtractor({})
        initial_state = state if mode == "start" else None
        prev_node_name = None
        emit_state_until_end = None

        async for event in self.agent.astream_events(initial_state, config, version="v1"):
            current_node_name = event.get("name")
            event_type = event.get("event")
            run_id = event.get("run_id")

            metadata = event.get("metadata")
            emit_state = metadata.get("copilotkit:emit-state")


            # we only want to update the node name under certain conditions
            # since we don't need any internal node names to be sent to the frontend
            if current_node_name in self.agent.nodes.keys():
                node_name = current_node_name

            # we don't have a node name yet, so we can't update the state
            if node_name is None:
                continue

            if emit_state and emit_state_until_end is None:
                emit_state_until_end = node_name

            if emit_state and event_type == "on_chat_model_start":
                # reset the streaming state extractor
                streaming_state_extractor = _StreamingStateExtractor(emit_state)

            updated_state = self.agent.get_state(config).values

            if emit_state and event_type == "on_chat_model_stream":
                streaming_state_extractor.buffer_tool_calls(event)

            if emit_state_until_end is not None:
                updated_state = {
                    **updated_state,
                    **streaming_state_extractor.extract_state()
                }

            if (not emit_state and
                current_node_name == emit_state_until_end and 
                event_type == "on_chain_end"):
                # stop emitting function call state
                emit_state_until_end = None

            exiting_node = node_name == current_node_name and event_type == "on_chain_end"

            # we send state sync events when:
            #   a) the state has changed
            #   b) the node has changed
            #   c) the node is ending
            if updated_state != state or prev_node_name != node_name or exiting_node:
                state = updated_state
                prev_node_name = node_name
                yield self._emit_state_sync_event(
                    thread_id=thread_id,
                    run_id=run_id,
                    node_name=node_name,
                    state=state,
                    running=True,
                    active=not exiting_node
                ) + "\n"

            yield langchain_dumps(event) + "\n"

        state = self.agent.get_state(config)
        is_end_node = state.next == ()

        node_name = list(state.metadata["writes"].keys())[0]
        yield self._emit_state_sync_event(
            thread_id=thread_id,
            run_id=run_id,
            node_name=node_name if not is_end_node else "__end__",
            state=state.values,
            # For now, we assume that the agent is always running
            # In the future, we will have a special node that will
            # indicate that the agent is done
            running=True,

            # at this point, the node is ending so we set active to false
            active=False
        ) + "\n"



    def dict_repr(self):
        super_repr = super().dict_repr()
        return {
            **super_repr,
            'type': 'langgraph'
        }

class _StreamingStateExtractor:
    def __init__(self, emit_state: dict):
        self.emit_state = emit_state
        self.tool_call_buffer = {}
        self.current_tool_call = None

        self.previously_parsable_state = {}

    def buffer_tool_calls(self, event: dict):
        """Buffer the tool calls"""
        if len(event["data"]["chunk"].tool_call_chunks) > 0:
            chunk = event["data"]["chunk"].tool_call_chunks[0]
            if chunk["name"] is not None:
                self.current_tool_call = chunk["name"]
                self.tool_call_buffer[self.current_tool_call] = chunk["args"]
            elif self.current_tool_call is not None:
                self.tool_call_buffer[self.current_tool_call] = (
                    self.tool_call_buffer[self.current_tool_call] + chunk["args"]
                )

    def get_emit_state_config(self, current_tool_name):
        """Get the emit state config"""

        for key, value in self.emit_state.items():
            if current_tool_name == value.get("tool"):
                return (value.get("argument"), key)

        return (None, None)


    def extract_state(self):
        """Extract the streaming state"""
        parser = JSONParser()

        state = {}

        for key, value in self.tool_call_buffer.items():
            argument_name, state_key = self.get_emit_state_config(key)

            if state_key is None:
                continue

            try:
                parsed_value = parser.parse(value)
            except Exception as _exc: # pylint: disable=broad-except
                if key in self.previously_parsable_state:
                    parsed_value = self.previously_parsable_state[key]
                else:
                    continue

            self.previously_parsable_state[key] = parsed_value

            if argument_name is None:
                state[state_key] = parsed_value
            else:
                state[state_key] = parsed_value.get(argument_name)

        return state
