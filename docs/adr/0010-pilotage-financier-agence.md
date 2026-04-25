# ADR #10 — Pilotage financier et qualité agence

## Statut
Accepté — 23 avril 2026

## Contexte
Michael et Jeffrey ont besoin d'une vue consolidée de tous
les agents chaque semaine pour piloter la rentabilité de
l'agence et détecter les problèmes avant les clients.

## Décision
Rapport de pilotage hebdomadaire automatique :

### Envoi :
- Dimanche 8h00
- Canal : Email + Telegram
- Destinataires : Michael + Jeffrey

### Contenu :
- Tableau de bord global (agents actifs, alertes, tâches)
- Performance par agent (validité %, coût réel, facturé, ROI)
- Alertes rentabilité (agent déficitaire, validité < 70%)
- Finances semaine (coût LLM, CA facturé, marge brute)
- Marge cumulée depuis lancement
- Recommandations automatiques Claude

### Table Supabase agent_weekly_stats :
```json
{
  "agent_id": "email_vesper",
  "week": "2026-W17",
  "validity_score": 0.94,
  "cost_eur": 2.30,
  "billed_eur": 45.00,
  "tasks_processed": 127,
  "time_saved_min": 312
}
```

### Alertes automatiques :
- Validité < 70% → révision prompt requise
- Coût > facturation → agent déficitaire
- 2 sprints ratés → recadrage plan

### Calcul validité % :
- LLM-as-a-judge score moyen (ADR #7)
- Feedback client 👍👎 pondéré
- Malus erreurs Sentry

## Justification
Sans pilotage financier hebdo, un agent déficitaire peut
coûter des semaines avant d'être détecté. Le rapport dimanche
permet d'agir le lundi matin avant que le client soit impacté.

## Conséquences
### Positives
- Zéro surprise financière
- Clients facturables précisément
- Détection précoce des régressions
- Vision globale de la santé de l'agence

### Négatives
- Rapport à construire et maintenir
- Données financières sensibles à sécuriser
- Alertes mal calibrées = faux positifs stressants
