# ADR #6 — Système de prompts 3 niveaux

## Statut
Accepté — 23 avril 2026

## Contexte
Les prompts sont le cœur de la valeur des agents. Ils doivent
être versionnés, personnalisables par client et adaptables
aux ICPs (Ideal Customer Profile) sans être trop génériques.

## Décision
Architecture 3 niveaux fusionnés au runtime :

### Niveau 1 — GitHub (logique système)
- Prompts techniques de l'agent
- Versionnés via Git, modifiables uniquement par Michael/Jeffrey via PR
- Stockés dans `packages/prompts/agents/`

### Niveau 2 — Supabase (personnalisation client)
- Ton, style, langue, signature
- Modifiable par le client sans déploiement
- Interface client Sprint 4

### Niveau 3 — Supabase (ICPs/use cases)
- Templates réutilisables par secteur métier
- Vocabulaire spécifique, priorités métier
- Bibliothèque construite au fil des clients
- Stockés dans `packages/prompts/icps/`

### Processus de génération en 3 passes :
1. Assemblage depuis bibliothèque (composants génériques)
2. Enrichissement métier (questions ciblées au client)
3. Validation qualité (LLM-as-a-judge, score minimum 8/10)

### Structure fichiers :
packages/prompts/
components/
tone_professional.md
tone_friendly.md
output_json.md
language_french.md
agents/
email_analyzer/
system.md
analyze.md
icps/
agence_immobiliere.md
cabinet_comptable.md

## Justification
La bibliothèque d'ICPs est l'effet de levier de l'agence.
Premier client = 80% génération. Dixième client = 20% génération,
80% assemblage. Score LLM-as-a-judge minimum 8/10 garantit
la qualité avant tout déploiement.

## Conséquences
### Positives
- Chaque client enrichit la bibliothèque
- Jeffrey améliore les prompts sans toucher au code Python
- Prompts non génériques grâce aux questions métier ciblées
- Effet boule de neige — plus de clients = meilleure bibliothèque

### Négatives
- Bibliothèque vide au Sprint 1 à construire progressivement
- Changer un prompt système = PR obligatoire
- Risque de sur-assemblage sans personnalisation suffisante
