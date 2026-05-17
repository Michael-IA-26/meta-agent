# Composant : format_rapport_hebdo

## Type
format

## Description
Structure du rapport hebdomadaire de suivi des leads qualifiés JM Partners.
Synthétise les signaux détectés, les leads scorés et les actions de prospection en cours.

## Contenu
**En-tête :**
- Semaine N (dates du lundi au vendredi)
- Date de génération
- Périmètre : Île-de-France, TPE/PME, secteurs ciblés

**Section 1 – Résumé exécutif (5 lignes max)**
- Nombre de signaux détectés
- Nombre de leads qualifiés (score ≥ seuil ICP)
- Nombre d'emails envoyés
- Nombre de RDV obtenus
- Taux de conversion signal → RDV

**Section 2 – Tableau des leads qualifiés**
Colonnes : SIREN | Raison sociale | Dirigeant | Score ICP | Signal(s) | Statut prospection | Date dernier contact

**Section 3 – Leads exclus**
Liste courte avec motif d'exclusion (liquidation, hors IDF, > 50 salariés, doublon, opt-out)

**Section 4 – Actions de la semaine suivante**
- Relances planifiées (J+7)
- Nouveaux signaux à traiter
- Alertes BODACC à surveiller

**Format de livraison :** Markdown ou PDF exportable, envoyé chaque vendredi avant 18h

## Exemples d'utilisation
1. Générer le rapport hebdomadaire automatique après le batch de détection de signaux
2. Présenter les résultats de la semaine à l'équipe commerciale JM Partners
3. Alimenter le tableau de bord mensuel de pilotage de la prospection

## Ne jamais faire
- Inclure des données personnelles hors SIREN et nom du dirigeant public
- Laisser le statut prospection vide pour un lead scoré ≥ 70
- Publier le rapport en dehors des canaux internes sécurisés
