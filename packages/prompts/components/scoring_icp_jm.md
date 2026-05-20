# Composant : scoring_icp_jm

## Type
scoring

## Description
Règles de scoring ICP (Ideal Customer Profile) de JM Partners pour qualifier les leads TPE/PME en Île-de-France.
Produit un score de 0 à 100 permettant de prioriser la prospection.

## Contenu
**Définition de l'ICP JM Partners :**
TPE ou PME dont le dirigeant est le décideur principal, implantée en Île-de-France, sans expert-comptable attitré ou insatisfaite de son cabinet actuel, avec un besoin comptable, fiscal ou social actif ou imminent.

**Grille de scoring (total : 100 points) :**

| Critère | Points | Condition |
|---|---|---|
| Localisation IDF | 20 | Siège en 75, 77, 78, 91, 92, 93, 94 ou 95 |
| Taille entreprise | 20 | 1-9 sal. = 20 pts ; 10-49 sal. = 15 pts ; 0 sal. = 10 pts |
| Forme juridique | 15 | SAS/SARL/EURL/SASU = 15 pts ; SCI = 10 pts ; autres = 5 pts |
| Signal création < 6 mois | 20 | Date immatriculation ≤ J-180 |
| Signal changement dirigeant | 15 | Publication BODACC ≤ J-90 |
| Secteur d'activité ciblé | 10 | Commerce, services, BTP, immobilier, santé libérale |

**Seuils de décision :**
- Score ≥ 75 : Lead chaud — email J+0, relance J+7
- Score 50-74 : Lead tiède — email J+0, relance J+14
- Score 30-49 : Lead froid — intégrer au nurturing mensuel
- Score < 30 : Exclure de la prospection active

**Facteurs disqualifiants (score forcé à 0) :**
Voir `exclusions_leads.md`

## Exemples d'utilisation
1. Calculer automatiquement le score d'un lead issu de l'API Pappers avant insertion en CRM
2. Prioriser la file d'envoi d'emails hebdomadaire par ordre de score décroissant
3. Comparer la distribution des scores semaine sur semaine pour détecter des biais de sourcing

## Ne jamais faire
- Contacter un lead avec un score < 30 via une séquence de prospection directe
- Modifier manuellement le score sans tracer la raison dans la fiche lead
- Appliquer ce scoring à des prospects hors Île-de-France
