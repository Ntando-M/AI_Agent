from dotenv import load_dotenv
import json

from groq import Groq
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage
)

# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

GROQ_MODEL = "openai/gpt-oss-20b"


# ============================================================
# GROQ CLIENT
# ============================================================

groq_client = Groq()


# ============================================================
# JSON SCHEMA
# ============================================================

AI_RESPONSE_SCHEMA = {
    "type": "object",

    "properties": {

        "answer": {
            "type": "string",
            "description": (
                "The complete answer to the user's question"
            )
        },

        "topic": {
            "type": "string",
            "description": (
                "The main topic of the user's question"
            )
        },

        "difficulty": {
            "type": "string",
            "enum": [
                "beginner",
                "intermediate",
                "advanced"
            ],
            "description": (
                "The estimated difficulty of the user's question"
            )
        },

        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": (
                "The model's confidence in the answer "
                "from 0.0 to 1.0"
            )
        }
    },

    "required": [
        "answer",
        "topic",
        "difficulty",
        "confidence"
    ],

    "additionalProperties": False
}


# ============================================================
# CONVERT LANGCHAIN MESSAGES TO GROQ FORMAT
# ============================================================

def convert_messages(messages):
    """
    Convert LangChain message objects into the format
    expected by the Groq Chat Completions API.
    """

    converted_messages = []

    for message in messages:

        if isinstance(message, SystemMessage):

            role = "system"

        elif isinstance(message, HumanMessage):

            role = "user"

        elif isinstance(message, AIMessage):

            role = "assistant"

        else:

            continue

        converted_messages.append(
            {
                "role": role,
                "content": message.content
            }
        )

    return converted_messages

# ============================================================
# Groq raw response
# ============================================================

def get_groq_raw_response(messages):
    groq_messages = convert_messages(
        messages
    )

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=groq_messages,
        temperature=0,
    )

    content = response.choices[
        0
    ].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty response."
        )

    return content
# ============================================================
# CALL GROQ
# ============================================================

def get_groq_response(messages):
    """
    Send the conversation to Groq.

    Returns the raw JSON response as a Python dictionary.
    Validation is handled by main.py using the AIResponse
    Pydantic model.
    """

    groq_messages = convert_messages(
        messages
    )

    response = groq_client.chat.completions.create(

        model=GROQ_MODEL,

        messages=groq_messages,

        temperature=0,

        response_format={
            "type": "json_schema",

            "json_schema": {

                "name": "ai_response",

                "strict": True,

                "schema": AI_RESPONSE_SCHEMA
            }
        }
    )

    content = response.choices[
        0
    ].message.content

    if not content:

        raise ValueError(
            "Groq returned an empty response."
        )

    return json.loads(content)

def get_groq_model():
    return GROQ_MODEL