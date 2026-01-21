
from pydantic import BaseModel, Extra


class AiAssistantInputData(BaseModel, extra=Extra.forbid):
    """A class to validate the input data that creates an AiAssistant agent instance.

    Args:
        BaseModel: _BaseModel_ from pydantic library.
        extra (Extra, optional): _Extra_ from pydantic library. Defaults to Extra.forbid.
    """
    broker: str
    port: int
    user_id: int
    session_id: str
    input_topic: str
    output_topic: str
    inference_model_name: str


class AiAssistantKillData(BaseModel, extra=Extra.forbid):
    """A class to validate the input data that kills an AiAssistant agent instance.

    Args:
        BaseModel: _BaseModel_ from pydantic library.
        extra (Extra, optional): _Extra_ from pydantic library. Defaults to Extra.forbid.
    """
    user_id: int
    session_id: str


def generate_docker_name(session_id: str) -> str:
    """Generates a unique name for the docker container based on session_id.

    Args:
        session_id (str): The session ID for which to generate the container name.

    Returns:
        str: The generated container name.
    """
    # Replace special characters with underscores to make it Docker-safe
    safe_session_id = session_id.replace("-", "_").replace(":", "_").replace(".", "_")
    return f"ai_assistant_{safe_session_id}"
