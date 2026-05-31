# Specs Techniques — Vue "En attente"
> Pour Jeffrey · JM Partners v2.2 · Mai 2026

---

## 1. Objectif & contexte

**Qui** : Collaborateurs JM Partners (Michael + comptables futurs)  
**Quoi** : Arbitrer les documents bloqués par les agents IA  
**Pourquoi** : KPI < 4h ouvrées par document en attente  
**Périmètre** : Documents avec `statut IN ('en_attente_ocr', 'en_attente_collaborateur', 'a_trier')`

---

## 2. Requête SQL principale

```sql
SELECT
  d.id,
  d.nom,
  d.type_document,
  d.statut,
  d.raison_attente,
  d.score_ocr,
  d.score_confiance,
  d.created_at,
  d.updated_at,
  dos.type        AS dossier_type,
  dos.exercice    AS dossier_exercice,
  dos.secteur     AS dossier_secteur,
  c.nom           AS contact_nom,
  c.email         AS contact_email
FROM documents d
JOIN dossiers dos ON d.dossier_id = dos.id
JOIN contacts c   ON dos.contact_id = c.id
WHERE d.statut IN ('en_attente_ocr', 'en_attente_collaborateur', 'a_trier')
ORDER BY d.created_at ASC
LIMIT 50 OFFSET {offset}
```

**Filtres configurables** :
- `dossier_id` = UUID (filtre par dossier)
- `type_document` = TEXT (filtre par type)
- `raison_attente` = TEXT (filtre par raison)

---

## 3. Layout / wireframe ASCII

```
+──────────────────────────────────────────────────────────────────+
│ 🔄 EN ATTENTE (12)   [Dossier ▼]  [Type ▼]  [🔍 Recherche]    │
+──────────────────────────────────────────────────────────────────+
│                         │                                        │
│  PDF preview            │  Facture Metro — mai 2026             │
│  (200x300px)            │  Dossier : CIHAN · TVA 2026           │
│  [thumbnail Supabase    │  Contact : Mohamed Hassani            │
│   Storage]              │  Type    : facture_achat              │
│                         │  Raison  : 🔴 Score OCR 0.62         │
│                         │  Reçu   : 28 mai 2026 · 10h30        │
│                         │                                        │
│                         │  [✅ Valider]  [🔁 Réassigner]       │
│                         │  [❓ Demander] [🗑️ Rejeter]          │
│                         │                                        │
+──────────────────────────────────────────────────────────────────+
│  ◀ Précédent   Doc 1 sur 12   Suivant ▶                        │
+──────────────────────────────────────────────────────────────────+
```

**Composants Tailwind + shadcn/ui** :
- Container : `flex gap-4 p-4 border rounded-lg`
- Preview : `w-48 h-72 object-contain border rounded`
- Badge raison : `inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs`
- Boutons : `Button variant="outline"` (shadcn) sauf Valider = `variant="default"`

---

## 4. Les 4 actions

| Action | Effet DB | Notification | Condition |
|---|---|---|---|
| **Valider** | `statut → a_saisir_sage` | Aucune | `score_ocr > 0.70` ou override manuel |
| **Réassigner** | `dossier_id` changé + `statut → a_trier` | Mail collaborateur dossier cible | `dossier_id` valide |
| **Demander info** | `statut → en_attente_client` + flag dans metadata | Mail contact via Outlook (compta@jmpartners.fr) | `contact.email NOT NULL` |
| **Rejeter** | `statut → archive` + `raison_attente → 'rejete_collaborateur'` | Log dans `apprentissage` | Aucune condition |

**Requêtes de mutation** :

```typescript
// Valider
await supabase
  .from('documents')
  .update({ statut: 'a_saisir_sage', updated_at: new Date().toISOString() })
  .eq('id', documentId)

// Réassigner
await supabase
  .from('documents')
  .update({ dossier_id: newDossierId, statut: 'a_trier', updated_at: new Date().toISOString() })
  .eq('id', documentId)

// Demander info
await supabase
  .from('documents')
  .update({ statut: 'en_attente_client', updated_at: new Date().toISOString() })
  .eq('id', documentId)

// Rejeter
await supabase
  .from('documents')
  .update({ statut: 'archive', raison_attente: 'rejete_collaborateur', updated_at: new Date().toISOString() })
  .eq('id', documentId)
```

---

## 5. Badges raison_attente

| `raison_attente` | Badge | Couleur | Explication |
|---|---|---|---|
| `score_ocr_faible` | 🔴 Score OCR faible | rouge | `score_ocr < 0.70` — document illisible |
| `confiance_faible` | 🟡 Confiance faible | jaune | `score_confiance < 0.80` — classification incertaine |
| `multi_dossiers_ambigu` | 🟠 Multi-dossiers | orange | Le doc appartient à plusieurs dossiers |
| `doublon_potentiel` | 🟣 Doublon potentiel | violet | Déjà reçu (même message_id détecté) |
| `type_inconnu` | 🔵 Type inconnu | bleu | Classification impossible |
| `null` | ⚪ En attente OCR | gris | Pas encore traité |

**Mapping TypeScript** :
```typescript
const BADGE_CONFIG = {
  score_ocr_faible:      { color: 'red',    icon: '🔴', label: 'Score OCR faible' },
  confiance_faible:      { color: 'yellow', icon: '🟡', label: 'Confiance faible' },
  multi_dossiers_ambigu: { color: 'orange', icon: '🟠', label: 'Multi-dossiers' },
  doublon_potentiel:     { color: 'purple', icon: '🟣', label: 'Doublon potentiel' },
  type_inconnu:          { color: 'blue',   icon: '🔵', label: 'Type inconnu' },
} as const
```

---

## 6. Subscription Supabase Realtime

```typescript
const channel = supabase
  .channel('documents_en_attente')
  .on(
    'postgres_changes',
    {
      event: '*',
      schema: 'public',
      table: 'documents',
      filter: "statut=in.(en_attente_ocr,en_attente_collaborateur,a_trier)",
    },
    (payload) => {
      if (payload.eventType === 'INSERT') {
        // Ajouter au début de la liste
        setDocuments(prev => [payload.new as Document, ...prev])
      } else if (payload.eventType === 'UPDATE') {
        // Si un autre user a validé → retirer de la liste
        const newStatut = (payload.new as Document).statut
        if (!['en_attente_ocr', 'en_attente_collaborateur', 'a_trier'].includes(newStatut)) {
          setDocuments(prev => prev.filter(d => d.id !== payload.new.id))
        }
      } else if (payload.eventType === 'DELETE') {
        setDocuments(prev => prev.filter(d => d.id !== payload.old.id))
      }
    }
  )
  .subscribe()

// Cleanup
return () => { supabase.removeChannel(channel) }
```

---

## 7. États UI à gérer

| État | Composant | Comportement |
|---|---|---|
| **Loading** | Skeleton 5 cartes | `animate-pulse`, hauteur fixe |
| **Empty state** | Illustration + message | "✨ Aucun document en attente — les agents travaillent !" |
| **Error state** | Toast rouge | Message d'erreur + bouton "Réessayer" |
| **Optimistic update** | Retrait immédiat du DOM | Rollback si la requête échoue (toast d'erreur) |
| **Action en cours** | Boutons disabled + spinner | Pendant la mutation Supabase |

---

## 8. Permissions / RLS

**Beta** : tous les utilisateurs authentifiés voient tous les dossiers.

```sql
-- Policy actuelle (beta)
CREATE POLICY "beta_auth_all_documents" ON documents
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
```

**Production (à implémenter après la beta)** :
```sql
-- À créer quand multi-utilisateurs
CREATE POLICY "prod_documents_par_responsable" ON documents
  FOR SELECT TO authenticated
  USING (
    dossier_id IN (
      SELECT id FROM dossiers WHERE responsable_id = auth.uid()
    )
  );
```

---

## 9. Checklist Jeffrey (livrables)

- [ ] Composant `<VueEnAttente />` autonome (React + TypeScript)
- [ ] Hook `useDocumentsEnAttente(supabaseClient)` avec Realtime
- [ ] Gestion des 4 actions (mutations Supabase + optimistic updates)
- [ ] Badge mapping `raison_attente` → couleur + icône
- [ ] Skeleton loading (5 cartes)
- [ ] Empty state ("✨ Aucun document en attente")
- [ ] Toast confirmations (shadcn/ui `useToast`)
- [ ] Test manuel avec les 5 docs seed CIHAN (`dossier_id = 'cihan-0000-0000-0000-dossier00001'`)
- [ ] Capture vidéo Loom (2 min — navigation + 1 action Valider)
- [ ] Deploy preview Lovable + URL partagée avec Michael

---

## 10. Hors scope (V1)

- Pas d'édition inline du PDF
- Pas de bulk actions (V2 ultérieure)
- Pas de stats / dashboard (vue dédiée)
- Pas d'export CSV (V2 ultérieure)
- Pas de tri configurable côté client (ORDER BY created_at ASC fixe en V1)

---

## 11. Performance

| Contrainte | Valeur | Justification |
|---|---|---|
| Pagination | 50 docs/page | Éviter rechargement complet |
| Refresh Realtime | Max 1x/500ms | Déduplique les events rapides |
| Cache local | 30s | Évite re-fetch si navigation retour |
| Preview PDF | Lazy load | Seulement si doc visible |
