# ADR #3 — Orchestration multi-agents

## Statut
Accepté — 23 avril 2026

## Contexte
Les agents doivent pouvoir s'orchestrer entre eux pour traiter
des tâches complexes. Le choix du framework d'orchestration
impacte la vélocité, la flexibilité et la maintenabilité.

## Décision
- **Sprint 1-3** : Claude Agent SDK natif (orchestration intégrée)
- **Sprint 4** : évaluation LangGraph si workflows trop complexes
- Pas de Manager Agent custom — le SDK gère la délégation nativement
- Principe : pas d'over-engineering, on upgrade si le besoin est prouvé

## Justification
Claude Agent SDK permet l'orchestration multi-agents sans code
custom. Chaque sous-agent = un agent SDK avec ses propres tools.
LangGraph sera introduit uniquement si la complexité des workflows
le justifie sur données réelles.

## Conséquences
### Positives
- Zéro code de plomberie à maintenir
- Compatible avec la méta-récursivité (ADR #8)
- Migration vers LangGraph possible sans refactoring majeur
- Anthropic maintient et optimise le SDK en continu

### Négatives
- Vendor lock-in Anthropic sur le SDK
- LangGraph plus flexible si besoin de mixer plusieurs LLMs
- Courbe d'apprentissage LangGraph si migration nécessaire en Sprint 4
