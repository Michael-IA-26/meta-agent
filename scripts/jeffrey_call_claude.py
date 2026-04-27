"""Premier appel API Claude pour Jeffrey - Sprint 0 Jour 4."""

import os
import sys

import anthropic
from dotenv import load_dotenv


def call_claude(prompt: str) -> str:
    """Envoie un prompt a Claude et retourne sa reponse."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY manquante dans .env")

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )

    text_blocks = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(text_blocks)


if __name__ == "__main__":
    load_dotenv()

    if len(sys.argv) < 2:
        prompt = "Bonjour Claude, peux-tu te presenter en 2 phrases ?"
    else:
        prompt = " ".join(sys.argv[1:])

    print(f">>> Prompt envoye : {prompt}\n")
    answer = call_claude(prompt)
    print(f"<<< Reponse de Claude :\n{answer}")
