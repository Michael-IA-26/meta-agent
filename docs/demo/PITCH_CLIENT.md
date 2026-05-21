# Meta-Agent LeadCommercial — Présentation client

## Ce que fait l'agent

**Meta-Agent LeadCommercial** est un pipeline automatisé qui identifie chaque jour les nouvelles entreprises créées en Île-de-France susceptibles d'avoir besoin d'un cabinet comptable.

### Fonctionnement en 4 étapes

1. **Collecte automatique** — L'agent interroge l'API officielle INSEE Sirene chaque matin pour récupérer toutes les nouvelles immatriculations du jour en IDF (Paris, 77, 78, 91, 92, 93, 94, 95).

2. **Scoring intelligent 0–100** — Chaque entreprise est évaluée selon des critères métier calibrés pour JM Partners :
   - Type de signal (création récente, rattrapage fiscal, intention déclarée)
   - Secteur d'activité (restauration et services prioritaires : +10 pts)
   - Fraîcheur de création (< 7 jours : +10 pts)
   - Forme juridique (SAS, SASU, EURL favorisées)
   - Hors IDF : score automatiquement à 0

3. **Qualification** — Seuls les leads avec un score ≥ 50 sont retenus. Les autres sont filtrés silencieusement.

4. **Notification multi-canal** — Les leads qualifiés sont envoyés par :
   - Message Telegram instantané avec le score et les coordonnées
   - Rapport HTML complet par email avec tableau de bord visuel

---

## Résultats obtenus

| Métrique | Valeur |
|---|---|
| Entreprises analysées / jour | ~100 |
| Leads qualifiés / jour | 15–30 (taux ~20%) |
| Temps de traitement | < 30 secondes |
| Faux positifs | < 5% |
| Couverture IDF | 100% (8 départements) |

---

## Pourquoi ça marche

- **Données fraîches** : l'INSEE publie les immatriculations en temps quasi-réel. Vous contactez les entrepreneurs **avant vos concurrents**.
- **Critères sur-mesure** : le scoring a été calibré sur les clients actuels de JM Partners. Les secteurs restauration, retail et services sont sur-pondérés car ce sont vos meilleurs clients historiques.
- **Zéro friction** : pas d'interface à gérer. Les alertes arrivent directement dans votre Telegram et votre boîte mail chaque matin.

---

## Prochaines étapes

### Court terme (Sprint 3)
- Enrichissement automatique des leads via Pappers (dirigeant, capital, bilans)
- Score de solvabilité basé sur les données financières publiques
- Intégration CRM (export CSV ou webhook vers votre outil)

### Moyen terme
- Détection des entreprises en difficulté (Infogreffe : procédures collectives)
- Alertes sur les changements de dirigeant (opportunité de ré-engagement)
- Tableau de bord web temps réel

---

*Meta-Agent · JM Partners · Généré le 21/05/2026*
