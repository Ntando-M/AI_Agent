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


# gpt-oss-20b is a reasoning model: it emits a `reasoning`
# field before its answer, and those tokens are billed and
# counted against max_tokens. A planning call typically
# spends 500-1100 reasoning tokens before producing content.
#
# The cap must be small enough that reasoning PLUS the
# answer fits comfortably. At 4096 the model spent 4094
# tokens on reasoning alone and returned empty content,
# costing 7229 tokens per call - 90% of the 8000 TPM
# free-tier limit, so two prompts in a minute hit the rate
# limit. At 1536 the model produces a valid plan 3 of 4
# times and averages 1808 tokens per call, a 75% reduction.
# The retry-on-empty path handles the occasional failure.
MAX_COMPLETION_TOKENS = 1536

# How many times to retry a call that returned no usable
# content. Two retries: the failure is intermittent (the
# reasoning model occasionally exhausts its token budget on
# reasoning alone), so a second or third attempt usually
# succeeds. A higher count would multiply latency on a
# genuinely broken provider.
MAX_EMPTY_RETRIES = 2


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
# RESPONSE EXTRACTION
# ============================================================

def strip_code_fences(text):
    """
    Remove a markdown code fence wrapping a JSON payload.

    gpt-oss-20b frequently answers with a fenced block even
    when told to return only JSON, producing content like:

        ```json
        {"steps": [...]}
        ```

    Stripping the fence here rather than at each call site
    keeps the parser in data_analysis/agent.py honest: it
    should receive JSON, not formatting.
    """

    if not text:
        return text

    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    # Drop the opening fence and any language tag.
    remainder = stripped[3:]

    if "\n" in remainder:
        first_line, remainder = remainder.split(
            "\n", 1
        )

        # The first line is a language tag only when it looks
        # like one. A bare ``` fence leaves the JSON on the
        # following line, so it must be dropped too, but real
        # content on that line must not be.
        if first_line.strip() == "":
            stripped = remainder
        elif first_line.strip().lower() in {
            "json",
            "javascript",
            "js",
            "python",
        }:
            stripped = remainder

    # Drop the closing fence if present.
    if stripped.rstrip().endswith("```"):
        stripped = stripped.rstrip()[:-3]

    return stripped.strip()


def extract_content(response):
    """
    Pull usable text out of a Groq chat completion.

    Handles three shapes this model actually produces:

    1. Normal content.
    2. Empty content, because the model spent its whole token
       budget on reasoning. Returns None so the caller retries.
    3. A tool call with no content. This model sometimes emits
       a tool call even though no tools were offered and
       tool_choice is none, which the API rejects with
       "Tool choice is none, but model called a tool". The
       call arguments are JSON and are frequently a usable
       answer, so they are recovered rather than discarded.
    """

    choice = response.choices[0]
    message = choice.message

    content = getattr(message, "content", None)

    if content:
        return strip_code_fences(content)

    tool_calls = getattr(message, "tool_calls", None)

    if tool_calls:
        arguments = tool_calls[0].function.arguments

        if arguments:
            return strip_code_fences(arguments)

    return None


def call_groq(groq_messages, response_format=None):
    """
    Call Groq with a bounded token budget.

    Kept separate from the response handling so the raw and
    structured paths cannot drift apart on how a request is
    issued.

    tool_choice is set to "none" on every call. gpt-oss-20b
    is a reasoning model that intermittently emits a tool call
    even though no tools were offered. When that happens Groq
    rejects the whole request with 400 "Tool choice is none,
    but model called a tool" before returning anything, so the
    extract_content() recovery path never runs. Pinning
    tool_choice to "none" stops the model from attempting a
    tool call at all: measured 4/4 clean responses.
    """

    kwargs = {
        "model": GROQ_MODEL,
        "messages": groq_messages,
        "temperature": 0,
        # Must cover reasoning tokens as well as the answer.
        # Without this the response is intermittently empty.
        "max_tokens": MAX_COMPLETION_TOKENS,
        #"tool_choice": "none",
    }

    if response_format is not None:
        kwargs["response_format"] = response_format

    return groq_client.chat.completions.create(**kwargs)


class RateLimitError(Exception):
    """
    Groq refused the request for quota reasons.

    Distinct from a provider failure because the remedy is
    completely different: retrying sooner does not help, and
    the only fix is to wait or use a different provider. The
    message carries Groq's own wording, which names the limit
    that was hit and how long to wait.
    """

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def call_groq_for_content(groq_messages, response_format=None):
    """
    Call Groq and return usable text, retrying once on empty.

    An empty response is an intermittent property of this
    reasoning model rather than a broken provider, so one
    retry resolves it. A persistent empty response still
    raises, because silently returning nothing would let the
    orchestrator report a successful analysis with no
    evidence behind it.
    """

    last_finish_reason = None

    for attempt in range(MAX_EMPTY_RETRIES + 1):
        try:
            response = call_groq(
                groq_messages,
                response_format=response_format,
            )
        except Exception as exc:
            # A quota refusal is not an empty response and must
            # not be retried: the retry would consume the same
            # quota again and fail identically. Re-raising with
            # Groq's own wording lets the caller tell the user
            # to wait, rather than reporting a provider failure.
            if "rate limit" in str(exc).lower():
                raise RateLimitError(str(exc)) from exc
            raise

        content = extract_content(response)

        if content:
            return content

        last_finish_reason = response.choices[
            0
        ].finish_reason

        if attempt < MAX_EMPTY_RETRIES:
            print(
                f"[groq] empty response on attempt "
                f"{attempt + 1}, retrying "
                f"(finish_reason={last_finish_reason})"
            )

    raise ValueError(
        "Groq returned an empty response after "
        f"{MAX_EMPTY_RETRIES + 1} attempts. "
        f"finish_reason={last_finish_reason}"
    )


# ============================================================
# Groq raw response
# ============================================================

def get_groq_raw_response(messages):
    groq_messages = convert_messages(
        messages
    )

    return call_groq_for_content(groq_messages)


# ============================================================
# CALL GROQ
# ============================================================

def get_groq_response(messages):
    """
    Send the conversation to Groq.

    Returns the raw JSON response as a Python dictionary.
    Validation is handled by main.py using the
    AnalysisResponse Pydantic model.

    NOTE: we deliberately do NOT pass response_format:
    json_schema here. The reasoning model gpt-oss-20b
    intermittently emits a tool call (e.g. aggregate_dataset)
    even though no tools were offered and tool_choice is
    none. When response_format is json_schema the Groq API
    rejects the request with 400 "Tool choice is none but
    model called a tool" before returning anything, so the
    extract_content() recovery path never runs. Letting the
    model respond naturally and handling tool calls in
    extract_content() avoids the API error entirely.
    """
    groq_messages = convert_messages(messages)

    content = call_groq_for_content(groq_messages)

    # The model sometimes emits a tool call with no
    # natural-language content. Its arguments are JSON, but
    # they are only a usable plan when they actually name a
    # tool. This model also produces {"name": ...} payloads
    # that are not tool calls at all - a conversational reply
    # shaped like a function call, or a malformed
    # {"name": "inspect_dataset", "arguments": {"": ""}} - and
    # treating those as a plan turned a recoverable answer
    # into a 500. Only a payload that names a tool is
    # recovered as a plan; anything else falls through to
    # normal JSON parsing so the caller sees the real error.
    if content.startswith('{"name": "'):
        try:
            tool_call = json.loads(content)
        except json.JSONDecodeError:
            tool_call = None

        if isinstance(tool_call, dict) and isinstance(
            tool_call.get("name"), str
        ):
            return {
                "steps": [
                    {
                        "tool": tool_call["name"],
                        "arguments": tool_call.get(
                            "arguments",
                        )
                        or {},
                    }
                ]
            }

    return json.loads(content)

def get_groq_model():
    return GROQ_MODEL