# ADR #1 — Agent long-running vs synchrone

## Statut
Accepté — 23 avril 2026

## Contexte
Les agents cibles peuvent nécessiter des temps d'exécution très variables :
quelques secondes pour une classification email, plusieurs heures pour
une recherche approfondie. Ce choix impacte radicalement l'architecture
(API directe vs queue system).

## Décision
- **Sprint 1-2** : 100% synchrone (requête → réponse < 30s)
- **Sprint 3+** : introduction du long-running uniquement si un cas métier le justifie
- Pas de queue system avant que le besoin soit prouvé en production

## Justification
Le synchrone permet de valider la valeur produit sans complexité
infrastructure. Railway + asyncio suffisent pour les premiers cas d'usage.
Le long-running sera introduit sur données réelles, pas sur hypothèses.

## Conséquences
### Positives
- Architecture simple dès le départ
- Livrable fonctionnel dès Sprint 1
- Pas de dette infrastructure prématurée

### Négatives
- Si un cas long-running émerge en Sprint 2, refactoring nécessaire
- Agents limités à 30s de temps de réponse en V1
