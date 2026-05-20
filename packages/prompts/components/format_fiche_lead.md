# Composant : format_fiche_lead

## Type
format

## Description
Format standard d'une fiche lead complète pour la prospection JM Partners.
Centralise les données d'identification, de scoring et de suivi d'un prospect.

## Contenu
**Structure de la fiche lead :**

```
## Fiche Lead — [Raison sociale]

### Identification
- SIREN          : [9 chiffres]
- SIRET siège    : [14 chiffres]
- Raison sociale : [nom légal]
- Forme juridique: [SAS / SARL / EURL / SASU / SCI / ...]
- Code NAF       : [code] — [libellé]
- Adresse siège  : [numéro, rue, CP, ville]
- Date création  : [JJ/MM/AAAA]
- Effectif déclaré: [tranche INSEE]

### Dirigeant
- Nom / Prénom   : [nom prénom]
- Qualité        : [Gérant / Président / DG]
- Date de prise de fonction : [JJ/MM/AAAA]
- Email professionnel : [si disponible via source publique]
- Téléphone      : [si disponible]

### Scoring ICP
- Score total    : [0-100]
- Localisation IDF : [oui/non] — [pts]
- Taille         : [X salariés] — [pts]
- Forme juridique: [pts]
- Signal détecté : [création / changement dirigeant / autre] — [pts]
- Secteur        : [pts]

### Signal(s) déclencheur(s)
- Type           : [création entreprise / changement dirigeant]
- Date détection : [JJ/MM/AAAA]
- Source         : [BODACC / Pappers / INSEE]
- Référence      : [N° annonce BODACC ou ID Pappers]

### Suivi prospection
- Statut         : [nouveau / email envoyé / relance J+7 / RDV planifié / sans suite]
- Date 1er contact: [JJ/MM/AAAA]
- Canal          : [email / téléphone]
- Prochaine action: [description + date]
- Notes          : [observations libres]
```

## Exemples d'utilisation
1. Générer automatiquement une fiche lead depuis les données Pappers après scoring ICP
2. Mettre à jour le statut prospection après chaque interaction avec le prospect
3. Exporter les fiches leads au format CSV pour import CRM

## Ne jamais faire
- Laisser le champ SIREN vide ou approximatif
- Saisir un score sans renseigner le détail de chaque critère
- Stocker des données personnelles non publiques sans base légale (voir `contraintes_rgpd.md`)
