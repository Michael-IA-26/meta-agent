# ADR #2 — Mémoire persistante des agents

## Statut
Accepté — 23 avril 2026

## Contexte
Les agents doivent-ils se souvenir des conversations passées ?
Sans mémoire, chaque conversation repart de zéro — expérience
utilisateur pauvre et perte de contexte métier précieux.

## Décision
- **Sprint 1-2** : mémoire courte uniquement (contexte récent en Supabase)
- **Sprint 3-4** : mémoire longue via RAG (pgvector Supabase)
- Toujours inclure `user_id` et `session_id` dans chaque table dès Sprint 1

## Justification
pgvector est déjà dans la stack Supabase — pas de coût infra
supplémentaire. La mémoire longue est le différenciateur clé vs
un simple chatbot. Elle permet à l'agent de "connaître" le client
au fil du temps.

## Conséquences
### Positives
- Agents qui s'améliorent avec le temps
- pgvector déjà prévu, pas de surprise
- Différenciateur fort vs concurrents

### Négatives
- Coûts Supabase croissants avec le volume
- Embeddings = appels API supplémentaires
- Nécessite une stratégie d'archivage des vieilles mémoires
