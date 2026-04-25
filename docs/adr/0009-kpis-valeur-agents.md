# ADR #9 — KPIs et valeur mesurée par agent

## Statut
Accepté — 23 avril 2026

## Contexte
Chaque agent doit prouver sa valeur de façon mesurable.
Sans KPIs, impossible de justifier le pricing, d'améliorer
les agents ou de démontrer le ROI au client.

## Décision
Tout agent déployé doit mesurer et rapporter :

### KPIs obligatoires :
```json
{
  "agent_id": "email_analyzer_vesper",
  "kpis": {
    "temps_theorique_min": 45,
    "temps_agent_min": 2,
    "temps_gagne_min": 43,
    "gain_pourcentage": 95,
    "taches_traitees": 127,
    "valeur_estimee_eur": 215
  },
  "periode": "semaine_17_2026"
}
```

### Calcul des KPIs :
- Temps théorique : défini lors du setup client
- Temps agent : mesuré automatiquement par Langfuse
- Valeur estimée : temps gagné x TJM client

### Rapport hebdo client :
- Temps économisé cette semaine
- Valeur estimée en euros
- Top 3 actions réalisées
- Comparaison semaine précédente

### Table Supabase agent_weekly_stats :
- Stockage hebdo par agent
- Historique complet depuis le déploiement
- Base pour le rapport pilotage agence (ADR #10)

## Justification
Les KPIs sont le nerf de la guerre pour la rétention client.
Un client qui voit 5h23 économisées cette semaine renouvelle
et recommande. Langfuse mesure déjà le temps agent — il suffit
d'agréger et de comparer au temps théorique.

## Conséquences
### Positives
- Client voit la valeur concrète chaque semaine
- Données pour améliorer et optimiser les agents
- Justification du pricing de l'agence
- Identification des agents à meilleur ROI

### Négatives
- Temps théorique mal calibré au départ
- Valeur en euros subjective selon le TJM client
- Volume de données Supabase croissant
