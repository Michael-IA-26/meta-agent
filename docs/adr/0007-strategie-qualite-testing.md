# ADR #7 — Stratégie qualité et testing 5 couches

## Statut
Accepté — 23 avril 2026

## Contexte
Les agents LLM sont non-déterministes — les tests classiques
ne suffisent pas. Une régression peut être silencieuse et
n'apparaître qu'en production chez un client.

## Décision
Pipeline de qualité en 5 couches :

### Couche 1 — Tests structurels (chaque commit)
- Vérifie la structure de sortie, pas le contenu
- Coût zéro, vitesse millisecondes
- Ex: assert output["priority"] in ["haute", "moyenne", "basse"]

### Couche 2 — Golden tests Haiku (chaque PR)
- Entrée fixe, sortie évaluée par LLM juge
- Outil : PromptFoo
- Coût ~0.001€ par test
- PR bloquée si score < 80%

### Couche 3 — LLM-as-a-judge (chaque merge)
- Claude évalue la qualité globale de la sortie
- Score minimum 8/10 pour validation
- Langfuse tracke les scores dans le temps

### Couche 4 — Monitoring continu (24/7)
- Langfuse tracke les scores en production réelle
- Alerte si score moyen < seuil sur 24h
- Détecte les dérives progressives

### Couche 5 — Feedback client (temps réel)
- Bouton 👍👎 sur chaque réponse agent
- Thumbs down → ticket Sentry automatique
- Accumulation de 👎 → alerte Michael/Jeffrey

### Rapport qualité quotidien 7h00
- Consolidation des 5 couches
- Envoyé avant rapport email 8h45
- Coût estimé à 250 agents : ~200€/mois refacturé clients

## Justification
Les tests classiques ne détectent pas les régressions LLM.
Les 5 couches couvrent du commit à la production réelle.
PromptFoo et Langfuse sont open source et s'intègrent
dans la CI existante.

## Conséquences
### Positives
- Régressions détectées avant qu'un client les voie
- Jeffrey améliore les prompts en confiance
- Données réelles pour améliorer les fallbacks

### Négatives
- Coût LLM des tests quotidiens
- PromptFoo = nouvelle dépendance à apprendre
- Golden tests non-déterministes = faux positifs possibles
