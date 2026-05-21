import ast
import logging
import os

import anthropic
from dotenv import load_dotenv
from langfuse import get_client, observe

load_dotenv()
logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

tools = [
    {
        "name": "calculator",
        "description": "Calcule une expression",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
    {
        "name": "echo",
        "description": "Echo en majuscules",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
]


def calculator(expression):
    try:
        return str(
            eval(compile(ast.parse(expression, mode="eval"), "<string>", "eval"))
        )
    except Exception as e:
        return f"Erreur: {e}"


def echo(message):
    return f"ECHO: {message.upper()}"


@observe()
def run_agent(prompt):
    logger.info("Prompt: %s", prompt)
    messages = [{"role": "user", "content": prompt}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1024, tools=tools, messages=messages
        )
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    logger.info("Reponse: %s", block.text)
            break
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                logger.info("Tool: %s(%s)", block.name, block.input)
                result = (
                    calculator(**block.input)
                    if block.name == "calculator"
                    else echo(**block.input)
                )
                logger.info("  -> %s", result)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    get_client().flush()
    logger.info("Trace envoyee a Langfuse!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_agent("Calcule 42 * 7 puis fais un echo du resultat")
