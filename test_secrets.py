import os

secrets = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
]

print("=== Vérification des secrets Doppler ===\n")
all_ok = True
for secret in secrets:
    value = os.getenv(secret)
    if value:
        masked = value[:6] + "..." + value[-4:]
        print(f"✅ {secret}: {masked}")
    else:
        print(f"❌ {secret}: NON TROUVÉ")
        all_ok = False

if all_ok:
    print("\n✅ Tous les secrets sont disponibles !")
else:
    print("\n⚠️  Des secrets manquent.")
