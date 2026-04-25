# ADR #5 — Stateful avec snapshots Supabase

## Statut
Accepté — 23 avril 2026

## Contexte
Les agents doivent conserver leur état entre les étapes pour
permettre la reprise sur erreur (ADR #1) et la scalabilité
horizontale (ADR #4). Le choix stateful/stateless impacte
le schéma Supabase et le code de chaque agent.

## Décision
Pattern "stateless process, stateful data" :
- État sérialisé en JSON dans Supabase après chaque étape
- Reprise possible depuis n'importe quel checkpoint
- N'importe quelle instance Railway/Cloud Run peut reprendre un agent

### Structure du snapshot :
```json
{
  "agent_id": "uuid",
  "step": 3,
  "total_steps": 7,
  "context": {},
  "memory": {},
  "status": "running|paused|done|error",
  "updated_at": "2026-04-23T23:00:00Z"
}
```

## Justification
Cohérent avec ADR #4 (agents stateless en mémoire = scalable)
et ADR #2 (mémoire persistante). L'état dans Supabase permet
à n'importe quel worker de reprendre n'importe quel agent.
Standard industrie "stateless process, stateful data".

## Conséquences
### Positives
- Reprise sur erreur sans perte de travail
- Compatible scalabilité horizontale ADR #4
- État lisible dans Supabase pour debug
- Compatible long-running futur ADR #1

### Négatives
- Latence légère à chaque étape (~50ms écriture Supabase)
- Volume données Supabase croît avec le nombre d'agents
- Sérialisation JSON complexe pour certains objets Python
