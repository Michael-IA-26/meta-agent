# Champs utiles — API Pappers v2 pour LeadCommercial

**Document** : `docs/leadcommercial/sirene-pappers-champs-utiles.md`  
**Auteur** : Jeffrey (JeffAgentia93-coder)  
**Sprint** : S2 — J7  
**Statut** : Brouillon — testé manuellement via curl  
**Dernière mise à jour** : 2026-05-10

---

## 1. Contexte

Test manuel de l'API Pappers v2 effectué le 10/05/2026 avec le SIREN 
443061841 (Google France). Ce document identifie les champs à exploiter 
dans le Signal Agent (Agent 1) pour le scoring et la qualification des leads.

Endpoint utilisé :
```
GET https://api.pappers.fr/v2/entreprise?siren={SIREN}&api_token={TOKEN}
```

---

## 2. Champs retenus pour le scorer

### 2.1 Identification de l'entreprise

| Champ JSON | Exemple (Google France) | Usage dans le scorer |
|---|---|---|
| `siren` | `"443061841"` | Clé primaire du lead, déduplication |
| `denomination` | `"GOOGLE FRANCE"` | Nom affiché dans les alertes |
| `forme_juridique` | `"SARL, société à responsabilité limitée"` | Filtrage ICP (SARL/SAS/EURL/SASU/EI) |
| `categorie_juridique` | `"5499"` | Code INSEE forme juridique — plus précis pour le scorer |
| `code_naf` | `"62.02A"` | Filtrage sectoriel + scoring NAF |
| `libelle_code_naf` | `"Conseil en systèmes et logiciels informatiques"` | Affichage humain dans les fiches leads |
| `date_creation` | `"2002-05-16"` | ⭐ Signal principal : création < 6 mois |
| `entreprise_cessee` | `false` | Exclusion automatique si `true` |
| `statut_rcs` | `"Inscrit"` | Vérification activité |

### 2.2 Localisation (filtrage géographique IDF)

| Champ JSON | Exemple | Usage |
|---|---|---|
| `siege.ville` | `"PARIS"` | Filtrage zone IDF |
| `siege.code_postal` | `"75009"` | Filtrage par département (75/77/78/91/92/93/94/95) |
| `siege.adresse_ligne_1` | `"8 RUE DE LONDRES"` | Adresse complète dans la fiche lead |
| `siege.latitude` | `48.876...` | Géolocalisation optionnelle |
| `siege.longitude` | `2.329...` | Géolocalisation optionnelle |

### 2.3 Taille de l'entreprise (filtrage TPE/PME)

| Champ JSON | Exemple | Usage |
|---|---|---|
| `effectif` | `"Entre 1 000 et 1 999 salariés"` | Label lisible |
| `effectif_min` | `1000` | ⭐ Filtrage numérique : garder si < 50 |
| `effectif_max` | `1999` | Filtrage numérique |
| `tranche_effectif` | `"42"` | Code INSEE tranches (voir table ci-dessous) |

**Table des tranches effectif INSEE utiles pour l'ICP JM :**

| Code | Tranche | Inclure ? |
|---|---|---|
| `00` | 0 salarié | ✅ Oui (EI/SASU solo) |
| `01` | 1-2 salariés | ✅ Oui |
| `02` | 3-5 salariés | ✅ Oui |
| `03` | 6-9 salariés | ✅ Oui |
| `11` | 10-19 salariés | ✅ Oui |
| `12` | 20-49 salariés | ✅ Oui |
| `21` | 50-99 salariés | ❌ Hors ICP |
| `22`+ | 100+ salariés | ❌ Hors ICP |

### 2.4 Dirigeant (enrichissement pour la prise de contact)

| Champ JSON | Exemple | Usage |
|---|---|---|
| `representants[0].nom_complet` | `"Paul Manicle"` | Personnalisation cold email |
| `representants[0].prenom` | `"Paul"` | Prénom pour l'email |
| `representants[0].nom` | `"Manicle"` | Nom pour l'email |
| `representants[0].qualite` | `"Gérant"` | Vérifier que c'est bien le décideur |
| `representants[0].date_prise_de_poste` | `"2019-05-03"` | Signal changement de dirigeant (S3+) |

> ⚠️ **RGPD** : les données des représentants sont des données personnelles.  
> Leur traitement doit être conforme à l'ADR-002 (issue #34).  
> Conserver uniquement ce qui est nécessaire à la prospection B2B.

### 2.5 Signaux BODACC (à activer S3+)

| Champ JSON | Usage |
|---|---|
| `publications_bodacc` | Liste des publications BODACC |
| `publications_bodacc[n].type` | `"Modification"` → signal changement dirigeant |
| `publications_bodacc[n].date` | Date de la publication |
| `publications_bodacc[n].description` | Texte libre — détecter "administration" |

### 2.6 Situation juridique (exclusions)

| Champ JSON | Valeur à exclure | Raison |
|---|---|---|
| `procedure_collective_en_cours` | `true` | Lead hors périmètre |
| `entreprise_cessee` | `true` | Société fermée |
| `siege.etablissement_cesse` | `true` | Établissement fermé |

---

## 3. Champs ignorés (trop riches / hors périmètre S2-S3)

Ces champs existent dans la réponse API mais ne sont pas utiles pour 
le scorer à ce stade :

- `finances` : données financières détaillées (utile S4+ pour scoring CA)
- `depots_actes` : actes juridiques complets
- `comptes` : bilans comptables
- `conventions_collectives` : hors périmètre
- `etablissements` : liste tous les établissements (garder uniquement `siege`)

---

## 4. Exemple de réponse minimale attendue par le scorer

```json
{
  "siren": "123456789",
  "denomination": "MON ENTREPRISE SARL",
  "forme_juridique": "SARL, société à responsabilité limitée",
  "categorie_juridique": "5499",
  "code_naf": "56.10A",
  "libelle_code_naf": "Restauration traditionnelle",
  "date_creation": "2026-01-15",
  "entreprise_cessee": false,
  "procedure_collective_en_cours": false,
  "effectif_min": 2,
  "effectif_max": 5,
  "siege": {
    "ville": "PARIS",
    "code_postal": "75011",
    "adresse_ligne_1": "12 RUE DE LA ROQUETTE"
  },
  "representants": [
    {
      "qualite": "Gérant",
      "nom_complet": "Jean Dupont",
      "prenom": "Jean",
      "nom": "Dupont"
    }
  ]
}
```

---

## 5. Limites de l'API Pappers (plan gratuit)

| Limite | Valeur |
|---|---|
| Appels/mois | 500 |
| Appels/minute | Non documenté — prévoir un sleep(1) entre appels |
| Champs disponibles | Tous sur le plan gratuit |
| Historique BODACC | Oui, complet |

> Pour la production (dry_run puis live), prévoir un plan payant Pappers  
> ou basculer sur l'API INSEE Sirene directe (gratuite, sans limite,  
> mais authentification OAuth2 requise — à prévoir en S4).

---

## 6. Prochaines étapes

- [ ] S3 : Mika intègre ces champs dans `scorer.py` (issue #35)
- [ ] S3 : Tester sur 50 SIREN IDF réels pour valider le filtrage ICP
- [ ] S4 : Évaluer passage API INSEE directe pour la production
- [ ] S4 : Tester Dropcontact pour enrichissement email dirigeant

---

## 7. Historique des révisions

| Version | Date | Auteur | Changements |
|---|---|---|---|
| v0.1 | 2026-05-10 | Jeffrey | Création — test manuel API Pappers, identification champs scorer |