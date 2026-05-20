# Composant : exclusions_leads

## Type
contraintes

## Description
Critères d'exclusion automatique des leads avant scoring et prospection.
Tout lead répondant à au moins un critère est écarté de la file de prospection active.

## Contenu
**Critères d'exclusion absolus (disqualification immédiate) :**

1. **Procédure collective en cours**
   - Redressement judiciaire, liquidation judiciaire, sauvegarde publiée au BODACC
   - Source : BODACC série C, API Pappers champ `statut_rcs`

2. **Siège social hors Île-de-France**
   - Codes postaux hors 75, 77, 78, 91, 92, 93, 94, 95
   - Exception : siège hors IDF mais établissement principal en IDF (vérifier SIRET actif)

3. **Effectif déclaré > 50 salariés**
   - Source : INSEE SIRENE, tranche d'effectif ≥ 5 (50-99 salariés)
   - Motif : profil PME avec DAF interne, hors cible TPE JM Partners

4. **Société radiée ou cessation d'activité**
   - Statut RCS : radié, dissous, en cours de dissolution
   - Source : API Pappers champ `date_radiation`

5. **Opt-out enregistré**
   - Prospect ayant explicitement demandé à ne plus être contacté
   - Source : liste noire interne CRM JM Partners

6. **Secteurs exclus**
   - Associations loi 1901, fondations, partis politiques
   - Grandes surfaces (NAF 47.11A, 47.11B)
   - Établissements d'enseignement public

7. **Doublon actif**
   - SIREN déjà présent dans le CRM avec statut « client », « en négociation » ou « relance en cours »

**Traitement des leads exclus :**
- Logguer le motif d'exclusion dans le rapport hebdomadaire (`format_rapport_hebdo.md`)
- Ne pas supprimer : archiver avec tag `exclu` et date pour audit

## Exemples d'utilisation
1. Filtrer automatiquement la liste brute issue de l'API Pappers avant scoring
2. Bloquer l'envoi d'un email à un prospect en liquidation détecté en cours de séquence
3. Répondre à un audit interne sur les critères de ciblage de la prospection

## Ne jamais faire
- Contacter une entreprise en procédure collective, même pour un service de restructuration
- Supprimer les leads exclus du log — les archiver pour traçabilité
- Ignorer un opt-out reçu hors CRM (email, téléphone, LinkedIn)
