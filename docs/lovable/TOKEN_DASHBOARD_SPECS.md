# Specs — Vue Token Dashboard (Lovable)

> Composant : `<TokenDashboard />`
> Route : `/tokens`
> Source : `GET /dashboard/tokens`
> Stack : React + Lovable + Recharts

---

## 1. Données

```typescript
interface TokenDashboard {
  by_agent: AgentStats[];
  totals: {
    today:  Period;
    week:   Period;
    month:  Period;
  };
  history_30d: { date: string; cost_eur: number }[];
}

interface AgentStats {
  agent_name: string;
  today: Period;
  week:  Period;
  month: Period;
}

interface Period {
  input:    number;
  output:   number;
  cost_eur: number;
  calls:    number;
}
```

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────┐
│  Token Dashboard — Consommation Anthropic               │
│  Actualisé toutes les 60 s                             │
├──────────┬──────────┬──────────┬──────────┬────────────┤
│  Coût    │  Coût    │  Coût    │  Appels  │  Tokens    │
│  Jour    │  Semaine │  Mois    │  Mois    │  Mois      │
│  €0.04   │  €0.28   │  €1.12   │  147     │  2.4M      │
├─────────────────────────────────────────────────────────┤
│  Graphe 30 jours — Coût journalier (€)                 │
│  ▁▂▃▁▂▅▆▃▂▁▂▃▄▅▃▂▁▄▅▆▇▅▃▂▁▂▃▁▂▄                       │
├─────────────────────────────────────────────────────────┤
│  Tableau par agent (cliquable, triable)                 │
│                                                         │
│  Agent             │ Jour  │ Semaine │ Mois  │ Alertes │
│  email_analyzer    │ €0.02 │ €0.14   │ €0.56 │         │
│  relance_handler   │ €0.01 │ €0.07   │ €0.28 │         │
│  mail_handler      │ €0.01 │ €0.07   │ €0.28 │  ⚠️ J7  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Composants

### 3.1 KPI Cards (5 cartes)

| KPI | Calcul | Couleur |
|-----|--------|---------|
| Coût Jour (€) | `totals.today.cost_eur` | neutre → rouge si > seuil |
| Coût Semaine (€) | `totals.week.cost_eur` | neutre |
| Coût Mois (€) | `totals.month.cost_eur` | neutre |
| Appels Mois | `totals.month.calls` | neutre |
| Tokens Mois | `totals.month.input + output` | neutre |

### 3.2 Graphe 30 jours

- Composant : `<AreaChart>` (Recharts)
- X-axis : date (format `DD MMM`)
- Y-axis : coût en € (format `€0.00`)
- `history_30d` comme data source
- Tooltip sur hover : date + coût exact
- Couleur area : `#2563a8` avec fill opacity 0.15

### 3.3 Tableau agents

Colonnes : Agent | Appels (mois) | Input tokens | Output tokens | Coût jour | Coût semaine | Coût mois | Alerte

Tri par défaut : coût mois DESC.

Tri cliquable : toutes colonnes numériques.

Pagination : 10 agents par page.

---

## 4. Alertes par seuil

Variable d'environnement (configurable) : `TOKEN_COST_THRESHOLD_EUR_DAY=0.50`

Logique d'alerte :
- `agent.today.cost_eur > seuil` → badge **⚠️** rouge dans le tableau + toast
- `totals.today.cost_eur > seuil × nombre_agents` → bannière rouge en haut de page

Seuil par défaut : **€0.50/agent/jour** si variable absente.

---

## 5. Actualisation

```typescript
useEffect(() => {
  const load = () => fetch('/dashboard/tokens').then(r => r.json()).then(setData);
  load();
  const id = setInterval(load, 60_000);
  return () => clearInterval(id);
}, []);
```

---

## 6. SQL de référence (endpoint `/dashboard/tokens`)

```sql
-- Coût total par agent sur 30 jours
SELECT
    agent_name,
    SUM(input_tokens)                    AS total_input,
    SUM(output_tokens)                   AS total_output,
    ROUND(SUM(cost_eur)::NUMERIC, 4)     AS total_cost_eur,
    COUNT(*)                             AS calls
FROM token_usage
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY agent_name
ORDER BY total_cost_eur DESC;

-- Historique journalier 30 jours
SELECT
    date,
    ROUND(SUM(cost_eur)::NUMERIC, 4) AS cost_eur
FROM token_usage
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date ASC;
```

---

## 7. États

| État | Affichage |
|------|-----------|
| Chargement initial | Skeleton loaders dans les KPI cards + tableau |
| Erreur API | Bannière rouge "Dashboard indisponible — données en cache" |
| Aucune donnée | Message "Aucune consommation enregistrée sur les 30 derniers jours" |
| Alerte dépassement | Toast + badge rouge sur la ligne agent concernée |
