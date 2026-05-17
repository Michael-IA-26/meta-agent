# Composant : signal_changement_dirigeant

## Type
signal

## Description
Signal de changement de dirigeant publié au BODACC, indiquant une transition de gouvernance.
Moment clé pour la prospection : le nouveau dirigeant remet souvent en question les prestataires existants.

## Contenu
**Définition du signal :**
Publication d'un acte de modification au BODACC mentionnant un changement de gérant, président, directeur général ou tout mandataire social, dans les 90 jours précédant l'analyse.

**Sources de détection :**
- BODACC série B (modifications diverses)
- API Pappers (champ `representants` avec date de prise de fonction)
- INPI RCS (actes déposés, rubrique modification)

**Critères de qualification du signal :**
- Type d'acte : modification de dirigeant (nomination, cessation, remplacement)
- Date de publication BODACC ≤ 90 jours
- Siège social en Île-de-France
- Société toujours en activité (pas de procédure collective en cours)
- Effectif ≤ 50 salariés

**Niveau de priorité :** HAUTE — fenêtre optimale entre J+7 et J+60 après la publication

**Angle de prospection recommandé :**
Mettre en avant la capacité d'accompagnement en transition : révision des pratiques comptables, mise en conformité, bilan d'entrée.

**Données à extraire pour la fiche lead :**
- SIREN, raison sociale
- Nom de l'ancien dirigeant et du nouveau dirigeant
- Date de prise de fonction
- Référence de la publication BODACC

## Exemples d'utilisation
1. Générer un email de prospection personnalisé adressé au nouveau dirigeant
2. Prioriser les leads à fort score ICP ayant ce signal en combinaison avec une création récente
3. Alerter le commercial JM Partners d'une opportunité sur un compte déjà connu

## Ne jamais faire
- Contacter l'ancien dirigeant après sa cessation de fonction
- Utiliser ce signal sur une société en procédure collective (redressement, liquidation)
- Dépasser J+90 sans requalifier le signal comme obsolète
