# ADR #8 — Meta-agent méta-récursif

## Statut
Accepté — 23 avril 2026

## Contexte
Le meta-agent est le cœur du produit. Son architecture définit
toute la proposition de valeur de l'agence : transformer un brief
en langage naturel en un agent opérationnel en 5 minutes.

## Décision
Le meta-agent est lui-même un agent Claude (méta-récursif) :

### Flux de génération :
1. Client soumet un brief en langage naturel
2. Meta-agent analyse le brief
3. Meta-agent pose 2-3 questions si ambigu (mode interactif)
4. Meta-agent génère en 3 passes (ADR #6)
5. Meta-agent produit la config JSON complète
6. Config JSON → Runtime → Agent déployé

### Config JSON générée :
```json
{
  "agent_name": "email_analyzer",
  "tools": ["gmail_reader", "claude_analyzer", "reporter"],
  "prompts": {
    "system": "agents/email/system.md",
    "icp": "icp_agence_conseil"
  },
  "schedule": "08:45",
  "budget_monthly": 50,
  "memory": "short+long",
  "fallback_llm": "openai"
}
```

### Interfaces progressives :
- Maintenant → Sprint 3 : Claude Project (interne)
- Sprint 3 → Sprint 7 : CLI
- Sprint 7 → Sprint 10 : Interface web Next.js
- Sprint 10+ : Console self-service client

## Justification
Un pipeline déterministe ne vaut pas grand chose — n'importe
qui peut en faire un. Un meta-agent qui comprend un brief en
langage naturel et génère un agent opérationnel en 5 minutes
est le vrai différenciateur de l'agence.

## Conséquences
### Positives
- Différenciateur produit majeur
- Config JSON auditable et versionnable
- Mode interactif gère les briefs ambigus
- Compatible Claude Agent SDK (ADR #3)

### Négatives
- Meta-agent peut générer des configs invalides
- Validation JSON stricte obligatoire
- Debugging complexe (agent qui génère des agents)
- Coût LLM doublé (meta-agent + agent généré)œ
œ
≈

