# Specs Techniques — Vue "En attente" (Lovable)

> Document destiné à Jeffrey pour l'implémentation dans Lovable.

---

## 1. CONTEXTE TECHNIQUE

### Tables Supabase utilisées

**`documents`**
| Colonne | Type | Description |
|---|---|---|
| `id` | uuid | Identifiant unique |
| `nom_fichier` | text | Nom du fichier |
| `statut` | text | Statut du document |
| `raison_attente` | text | Raison de mise en attente |
| `contenu_extrait` | text | Contenu extrait par OCR |
| `score_detection` | float | Score de confiance OCR/classification |
| `expediteur` | text | Adresse email ou source d'envoi |
| `date_reception` | timestamptz | Date de réception |
| `dossier_id` | uuid | FK vers `dossiers.id` |

**`dossiers`**
| Colonne | Type | Description |
|---|---|---|
| `id` | uuid | Identifiant unique |
| `nom` | text | Nom du dossier client |
| `type_dossier` | text | Type (comptabilité, juridique…) |

**`journaux`**
| Colonne | Type | Description |
|---|---|---|
| `id` | uuid | Identifiant unique |
| `agent` | text | Agent ayant effectué l'action |
| `action` | text | Type d'action effectuée |
| `statut` | text | Statut de l'action |
| `document_id` | uuid | FK vers `documents.id` |
| `created_at` | timestamptz | Date de création |

### Variables d'environnement

- URL Supabase : `VITE_SUPABASE_URL`
- Authentification : `VITE_SUPABASE_ANON_KEY` (anon key côté Lovable)

---

## 2. REQUÊTE PRINCIPALE

```sql
SELECT 
  d.id,
  d.nom_fichier,
  d.raison_attente,
  d.score_detection,
  d.expediteur,
  d.date_reception,
  d.contenu_extrait,
  dos.nom as dossier_suggere
FROM documents d
LEFT JOIN dossiers dos ON d.dossier_id = dos.id
WHERE d.statut = 'en_attente_collaborateur'
ORDER BY d.date_reception ASC
```

Cette requête retourne tous les documents en attente d'action manuelle, enrichis du nom du dossier suggéré. Le tri ASC garantit que les documents les plus anciens apparaissent en premier (priorité de traitement).

---

## 3. ACTIONS DISPONIBLES PAR DOCUMENT

### Valider
Marque le document comme validé dans son dossier actuel.

```sql
UPDATE documents SET statut='valide', updated_at=NOW() WHERE id=?
```

### Réassigner
Ouvre une modale de sélection de dossier, puis réassigne le document.

```sql
UPDATE documents SET dossier_id=?, statut='a_trier', updated_at=NOW() WHERE id=?
```

### Demander au client
Crée une entrée dans les journaux pour tracer la demande au client.

```sql
INSERT INTO journaux (agent, action, document_id) VALUES ('collaborateur', 'demande_client', ?)
```

### Rejeter
Marque le document comme rejeté.

```sql
UPDATE documents SET statut='rejete', updated_at=NOW() WHERE id=?
```

---

## 4. PASTILLE ORANGE (compteur temps réel)

### Requête compteur

```sql
SELECT COUNT(*) FROM documents WHERE statut = 'en_attente_collaborateur'
```

### Subscription Realtime Supabase

- Activer le Realtime sur la table `documents`
- Filtre : `statut='en_attente_collaborateur'`
- Écouter les événements `INSERT`, `UPDATE`, `DELETE`
- Mise à jour automatique du compteur sans rechargement de page

```typescript
const subscription = supabase
  .channel('en-attente-count')
  .on(
    'postgres_changes',
    {
      event: '*',
      schema: 'public',
      table: 'documents',
      filter: "statut=eq.en_attente_collaborateur",
    },
    () => refetchCount()
  )
  .subscribe()
```

---

## 5. COMPOSANTS UI À CRÉER

### `EnAttentePage`
Page principale accessible via la route `/en-attente`.

| Prop | Type | Description |
|---|---|---|
| — | — | Pas de props externes, gère son propre état |

### `DocumentEnAttenteCard`
Carte affichant les informations d'un document en attente avec ses 4 actions.

| Prop | Type | Description |
|---|---|---|
| `document` | `DocumentEnAttente` | Objet document complet |
| `onValider` | `(id: string) => void` | Callback validation |
| `onReassigner` | `(id: string, dossierId: string) => void` | Callback réassignation |
| `onDemanderClient` | `(id: string) => void` | Callback demande client |
| `onRejeter` | `(id: string) => void` | Callback rejet |

### `BadgeRaison`
Badge coloré indiquant la raison de mise en attente du document.

| Prop | Type | Description |
|---|---|---|
| `raison_attente` | `string` | Code de la raison d'attente |

### `CompteurEnAttente`
Pastille orange affichée dans la navigation sidebar avec le nombre de documents en attente.

| Prop | Type | Description |
|---|---|---|
| `count` | `number` | Nombre de documents en attente |

### `ModalReassignation`
Modale permettant de sélectionner un dossier cible pour réassigner un document.

| Prop | Type | Description |
|---|---|---|
| `documentId` | `string` | ID du document à réassigner |
| `onConfirm` | `(dossierId: string) => void` | Callback confirmation avec dossier sélectionné |
| `onCancel` | `() => void` | Callback annulation |

### `ConfirmationDialog`
Dialog générique de confirmation utilisé pour les actions irréversibles (valider, rejeter).

| Prop | Type | Description |
|---|---|---|
| `action` | `'valider' \| 'rejeter' \| 'demander_client'` | Type d'action à confirmer |
| `onConfirm` | `() => void` | Callback confirmation |
| `onCancel` | `() => void` | Callback annulation |

---

## 6. BADGES DE RAISON

Mapping exact des codes `raison_attente` vers labels et couleurs :

| Code | Couleur | Label affiché |
|---|---|---|
| `"score_insuffisant"` | 🟡 Jaune | `"Score OCR faible"` |
| `"illisible"` | 🔴 Rouge | `"Document illisible"` |
| `"multi_dossiers"` | 🟠 Orange | `"Multi-dossiers"` |
| `"score_confiance_insuffisant"` | 🟡 Jaune | `"Classification ambiguë"` |
| *(default)* | ⚪ Gris | `"En attente"` |

```typescript
const BADGE_CONFIG: Record<string, { color: string; label: string }> = {
  score_insuffisant: { color: 'yellow', label: 'Score OCR faible' },
  illisible: { color: 'red', label: 'Document illisible' },
  multi_dossiers: { color: 'orange', label: 'Multi-dossiers' },
  score_confiance_insuffisant: { color: 'yellow', label: 'Classification ambiguë' },
}

function getBadgeConfig(raison: string) {
  return BADGE_CONFIG[raison] ?? { color: 'gray', label: 'En attente' }
}
```

---

## 7. WIREFRAME ASCII

```
┌─────────────────────────────────────────────────────────┐
│ 🟠 En attente (12)                      [Filtres ▼]    │
├─────────────────────────────────────────────────────────┤
│ [PDF]  facture_cihan_mai.pdf                            │
│ 📁 Dossier suggéré : CIHAN              🟠 Multi-dossier│
│ 👤 De : factures@fournisseur.fr                         │
│ 📅 Reçu : 27 mai 2026 09:14                             │
│ 💰 Montant détecté : 1 200,00 €                         │
│                                                         │
│ [✅ Valider] [📁 Réassigner] [💬 Demander] [❌ Rejeter] │
├─────────────────────────────────────────────────────────┤
│ [PDF]  releve_bancaire_mai.pdf                          │
│ 📁 Dossier suggéré : CIHAN              🟡 Score faible │
│ 👤 De : (import automatique)                             │
│ 📅 Reçu : 27 mai 2026 08:30                             │
│                                                         │
│ [✅ Valider] [📁 Réassigner] [💬 Demander] [❌ Rejeter] │
└─────────────────────────────────────────────────────────┘
```

---

## 8. CHECKLIST JEFFREY

- [ ] Créer la page `/en-attente` dans Lovable
- [ ] Connecter Supabase Realtime (subscription sur documents)
- [ ] Implémenter les 4 actions avec confirmation dialog
- [ ] Ajouter la pastille 🟠 dans le layout principal (nav sidebar)
- [ ] Test sur dossier CIHAN avec les 3 docs de test du seed
- [ ] Vérifier que les actions mettent bien à jour le compteur en temps réel
- [ ] Responsive mobile : cartes empilées sur petit écran
