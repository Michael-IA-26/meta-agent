# ADR #4 — Scalabilité runtime

## Statut
Accepté — 23 avril 2026

## Contexte
Le runtime doit supporter 100 agents simultanés à 6 mois,
1000 à 12 mois, et être architecturé pour tenir 10 000 à terme.
Ce choix impacte le déploiement, les coûts et l'architecture asyncio.

## Décision
- **Sprint 1-2** : Railway + asyncio (0-100 agents)
- **Sprint 5+** : migration Google Cloud Run (100-1000 agents)
- **Sprint 8+** : Cloud Run + Google Pub/Sub (1000-10 000 agents)

### Principes immédiats (dès Sprint 1) :
- Tout le code en async/await — zéro code bloquant
- Agents stateless — état dans Supabase, jamais en mémoire
- Docker dès Sprint 2 — même image Railway et Cloud Run
- Interface queue-compatible — zéro refactoring jusqu'à 10 000 agents

## Justification
Railway permet de valider le produit sans ops. Google Cloud Run
est serverless, scale automatiquement et accepte les mêmes
containers Docker que Railway — migration en 1 semaine max.
Les 4 principes immédiats garantissent zéro refactoring majeur
jusqu'à 10 000 agents simultanés.

## Conséquences
### Positives
- Pas de Kubernetes à gérer avant Sprint 8
- Migration Railway → Cloud Run = changer 2 lignes de config
- Coût proportionnel à l'usage réel (serverless)
- Scalabilité horizontale infinie sur Cloud Run

### Négatives
- Google Cloud Run = nouveau fournisseur à Sprint 5
- Pub/Sub = complexité ops à Sprint 8
- Coûts Cloud Run significatifs à 10 000 agents simultanés
- async/await partout = debugging plus
