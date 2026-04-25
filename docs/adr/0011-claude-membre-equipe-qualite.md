# ADR #11 — Claude membre automatisé équipe qualité

## Statut
Accepté — 23 avril 2026

## Contexte
Michael et Jeffrey sont 2 personnes. Sans processus automatisé,
la qualité du code et la veille technologique dépendent
entièrement de leur disponibilité et de leur vigilance.

## Décision
Claude joue 3 rôles automatisés dans l'équipe :

### Rôle 1 — Code Reviewer (chaque PR)
- Trigger : chaque PR GitHub via GitHub Actions
- Claude analyse le diff et commente :
  - Cohérence avec les ADRs
  - Couverture des golden tests
  - Qualité de la gestion d'erreur
  - Respect des principes async/stateless
- Prompt : esprit senior critique, pas complaisant

### Rôle 2 — Sprint Reviewer (vendredi 18h)
- Analyse les PRs mergées de la semaine
- Analyse les KPIs agents (ADR #9)
- Analyse les erreurs Sentry (ADR #7)
- Produit un rapport critique :
  - Ce qui a bien marché / ce qui a raté
  - Dettes techniques identifiées
  - Recommandations sprint suivant

### Rôle 3 — Veille technologique (dimanche 8h)
- Intégré au rapport pilotage (ADR #10)
- Nouveautés Claude SDK / Anthropic
- Nouveaux modèles disponibles
- Nouvelles pratiques d'orchestration
- Failles de sécurité dans la stack
- Format : 5 bullets actionnables maximum

### Prompt systématique Claude :
Tu es l'architecte technique senior du projet Meta-Agent.
Tu as accès complet au code, aux ADRs et aux métriques.
Tu n'es pas là pour féliciter — tu es là pour identifier
ce qui va casser dans 3 sprints si on ne le corrige pas.
Sois direct, précis et actionnable.

## Justification
Claude API est déjà dans la stack. Zéro nouvelle dépendance.
Un reviewer automatique sur chaque PR = qualité maintenue
même quand Michael et Jeffrey manquent de temps.

## Conséquences
### Positives
- Qualité maintenue sans effort humain constant
- Veille techno automatique = toujours à jour
- Zéro nouvelle dépendance — Claude API déjà là
- Sprint review objective et sans biais émotionnel

### Négatives
- Claude peut générer des faux positifs en code review
- Coût API supplémentaire pour les reviews automatiques
- Prompt à affiner au fil des sprints pour rester pertinent
