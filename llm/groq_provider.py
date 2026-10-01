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

ANALYSIS_RESPONSE_SCHEMA = {
    "type": "object",

    "properties": {

        "answer": {
            "type": "string",
            "description": (
                "The complete answer to the user's question, "
                "written in clear natural language"
            )
        },

        "analysis_type": {
            "type": "string",
            "enum": [
                "general",
                "document",
                "dataset",
                "database",
                "visualisation"
            ],
            "description": (
                "The kind of analysis performed"
            )
        },

        "datasets_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The names of the datasets or database tables "
                "used to produce the answer"
            )
        },

        "calculations_performed": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "A description of each deterministic calculation "
                "or query that was actually executed"
            )
        },

        "key_findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The most important findings, each stated as a "
                "concrete result supported by the evidence"
            )
        },

        "sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The documents, filenames or database tables that "
                "provided the evidence"
            )
        },

        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": (
                "The model's confidence in the answer, from 0.0 "
                "to 1.0. Reduce this when the evidence is incomplete."
            )
        }
    },

    "required": [
        "answer",
        "analysis_type",
        "datasets_used",
        "calculations_performed",
        "key_findings",
        "sources",
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
    Validation is handled by main.py using the
    AnalysisResponse Pydantic model.
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

                "name": "analysis_response",

                "strict": True,

                "schema": ANALYSIS_RESPONSE_SCHEMA
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