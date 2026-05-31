"""Smoke test JM Partners — vérifie la connexion Supabase et les vars d'env."""
import os
import sys

REQUIRED_VARS = [
    "ANTHROPIC_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


def check_env():
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        print(f"❌ Variables manquantes : {', '.join(missing)}")
        sys.exit(1)
    print("✅ Toutes les variables d'env présentes")


def check_supabase():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    try:
        sb = create_client(url, key)
        sb.table("documents").select("id").limit(1).execute()
        print("✅ Supabase connecté — table documents accessible")
    except Exception as e:
        print(f"❌ Supabase erreur : {e}")
        sys.exit(1)


def check_anthropic():
    import anthropic

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        print(f"✅ Claude API connectée — model={msg.model}")
    except Exception as e:
        print(f"❌ Claude API erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    check_env()
    check_supabase()
    check_anthropic()
    print("\n✅ Smoke test JM Partners — tous les checks passent")
