"""FastAPI dashboard for LeadCommercial demo."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

app = FastAPI(title="LeadCommercial Dashboard")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>LeadCommercial — Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f0f4f8;
      color: #1a202c;
    }
    header {
      background: #2563eb;
      color: white;
      padding: 1.25rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
    }
    header h1 { font-size: 1.5rem; font-weight: 700; }
    header p  { font-size: 0.9rem; opacity: 0.85; }
    .kpis {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1rem;
      padding: 1.5rem 2rem;
    }
    .kpi {
      background: white;
      border-radius: 0.75rem;
      padding: 1.25rem 1.5rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .kpi .label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: .05em; color: #718096; }
    .kpi .value { font-size: 2rem; font-weight: 700; color: #2563eb; margin-top: 0.25rem; }
    .kpi .sub   { font-size: 0.8rem; color: #a0aec0; margin-top: 0.15rem; }
    .actions {
      padding: 0 2rem 1.25rem;
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: center;
    }
    button {
      cursor: pointer;
      border: none;
      border-radius: 0.5rem;
      padding: 0.65rem 1.4rem;
      font-size: 0.9rem;
      font-weight: 600;
      transition: opacity 0.15s;
    }
    button:hover { opacity: 0.85; }
    #btn-run {
      background: #16a34a;
      color: white;
    }
    #btn-run:disabled {
      background: #9ca3af;
      cursor: not-allowed;
    }
    #btn-refresh { background: #e2e8f0; color: #2d3748; }
    #run-status {
      font-size: 0.85rem;
      color: #4a5568;
    }
    .table-wrap {
      padding: 0 2rem 2rem;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: white;
      border-radius: 0.75rem;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
      font-size: 0.875rem;
    }
    thead { background: #f7fafc; }
    th {
      padding: 0.75rem 1rem;
      text-align: left;
      font-weight: 600;
      color: #4a5568;
      border-bottom: 1px solid #e2e8f0;
      white-space: nowrap;
    }
    td {
      padding: 0.65rem 1rem;
      border-bottom: 1px solid #f0f4f8;
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f7fafc; }
    .badge {
      display: inline-block;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.78rem;
      font-weight: 700;
    }
    .score-green  { background: #d1fae5; color: #065f46; }
    .score-orange { background: #fed7aa; color: #9a3412; }
    .score-red    { background: #fee2e2; color: #991b1b; }
    .qualified-yes { color: #16a34a; font-weight: 600; }
    .qualified-no  { color: #9ca3af; }
    #empty-state {
      text-align: center;
      padding: 3rem;
      color: #a0aec0;
      display: none;
    }
    @media (max-width: 640px) {
      header, .kpis, .actions, .table-wrap { padding-left: 1rem; padding-right: 1rem; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>LeadCommercial</h1>
      <p>Pipeline de prospection automatise — demo client</p>
    </div>
    <div id="last-updated" style="font-size:0.8rem;opacity:.75;"></div>
  </header>

  <div class="kpis">
    <div class="kpi">
      <div class="label">Leads aujourd&apos;hui</div>
      <div class="value" id="kpi-today">—</div>
      <div class="sub">entreprises detectees</div>
    </div>
    <div class="kpi">
      <div class="label">Cette semaine</div>
      <div class="value" id="kpi-week">—</div>
      <div class="sub">leads generes</div>
    </div>
    <div class="kpi">
      <div class="label">Qualifies</div>
      <div class="value" id="kpi-qualified">—</div>
      <div class="sub">score &ge; 50</div>
    </div>
    <div class="kpi">
      <div class="label">Taux qualification</div>
      <div class="value" id="kpi-rate">—</div>
      <div class="sub">sur la semaine</div>
    </div>
    <div class="kpi">
      <div class="label">Meilleur score</div>
      <div class="value" id="kpi-best">—</div>
      <div class="sub">/100 cette semaine</div>
    </div>
  </div>

  <div class="actions">
    <button id="btn-run" onclick="runPipeline()">&#9654; Lancer le pipeline maintenant</button>
    <button id="btn-refresh" onclick="loadData()">&#8635; Actualiser</button>
    <span id="run-status"></span>
  </div>

  <div class="table-wrap">
    <table id="leads-table">
      <thead>
        <tr>
          <th>SIREN</th>
          <th>Denomination</th>
          <th>Dept</th>
          <th>Commune</th>
          <th>NAF</th>
          <th>Score</th>
          <th>Qualifie</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody id="leads-body">
        <tr><td colspan="8" style="text-align:center;padding:2rem;color:#a0aec0;">Chargement…</td></tr>
      </tbody>
    </table>
    <p id="empty-state">Aucun lead pour le moment. Lancez le pipeline pour en generer.</p>
  </div>

  <script>
    function scoreClass(score) {
      if (score === null || score === undefined) return "";
      if (score >= 70) return "score-green";
      if (score >= 40) return "score-orange";
      return "score-red";
    }

    function fmtDate(iso) {
      if (!iso) return "—";
      return new Date(iso).toLocaleDateString("fr-FR", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit"
      });
    }

    async function loadLeads() {
      const res = await fetch("/api/leads");
      const leads = await res.json();
      const tbody = document.getElementById("leads-body");
      if (!leads.length) {
        tbody.innerHTML = "";
        document.getElementById("empty-state").style.display = "block";
        return;
      }
      document.getElementById("empty-state").style.display = "none";
      tbody.innerHTML = leads.map(l => {
        const cls = scoreClass(l.score);
        const sc = l.score !== null && l.score !== undefined
          ? `<span class="badge ${cls}">${l.score}</span>` : "—";
        const q = l.qualified
          ? '<span class="qualified-yes">Oui</span>'
          : '<span class="qualified-no">Non</span>';
        return `<tr>
          <td><code>${l.siren || "—"}</code></td>
          <td>${l.denomination || "—"}</td>
          <td>${l.dept || "—"}</td>
          <td>${l.commune || "—"}</td>
          <td>${l.code_naf || "—"}</td>
          <td>${sc}</td>
          <td>${q}</td>
          <td>${fmtDate(l.created_at)}</td>
        </tr>`;
      }).join("");
    }

    async function loadStats() {
      const res = await fetch("/api/stats");
      const s = await res.json();
      document.getElementById("kpi-today").textContent     = s.leads_today ?? "—";
      document.getElementById("kpi-week").textContent      = s.leads_week  ?? "—";
      document.getElementById("kpi-qualified").textContent = s.qualified_week ?? "—";
      const rate = s.qualification_rate;
      document.getElementById("kpi-rate").textContent =
        rate !== null && rate !== undefined ? rate.toFixed(1) + "%" : "—";
      document.getElementById("kpi-best").textContent = s.best_score ?? "—";
    }

    async function loadData() {
      await Promise.all([loadLeads(), loadStats()]);
      document.getElementById("last-updated").textContent =
        "Mis a jour : " + new Date().toLocaleTimeString("fr-FR");
    }

    async function runPipeline() {
      const btn = document.getElementById("btn-run");
      const status = document.getElementById("run-status");
      btn.disabled = true;
      status.textContent = "Pipeline en cours…";
      try {
        const res = await fetch("/api/run", { method: "POST" });
        const data = await res.json();
        if (res.ok) {
          status.textContent = `Pipeline termine — ${data.leads_found} lead(s) qualifie(s)`;
          await loadData();
        } else {
          status.textContent = "Erreur : " + (data.detail || "inconnue");
        }
      } catch (e) {
        status.textContent = "Erreur reseau : " + e.message;
      } finally {
        btn.disabled = false;
      }
    }

    loadData();
  </script>
</body>
</html>
"""


def _get_supabase_client() -> Any:
    """Return a Supabase client or raise if env vars are missing."""
    from supabase import create_client  # type: ignore[import-untyped]

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the dashboard HTML page."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/api/leads")
async def get_leads() -> JSONResponse:
    """Return the 50 leads with highest score from the `leads` table."""
    try:
        client = _get_supabase_client()
        resp = (
            client.table("leads")
            .select("*")
            .order("score", desc=True)
            .limit(50)
            .execute()
        )
        data = resp.data or []
        return JSONResponse(content=data)
    except Exception as exc:
        logger.error("Erreur lecture leads: %s", exc)
        return JSONResponse(content=[])


@app.post("/api/run")
async def run_now() -> JSONResponse:
    """Trigger the LeadCommercial pipeline in a background thread."""
    try:
        import apps.leadcommercial.main as lc_main  # noqa: PLC0415

        thread = threading.Thread(target=lc_main.main, daemon=True)
        thread.start()
        return JSONResponse(content={"status": "started"})
    except Exception as exc:
        logger.error("Erreur demarrage pipeline: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/stats")
async def get_stats() -> JSONResponse:
    """Return global stats: leads today, this week, qualification rate."""
    now = datetime.now(tz=timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    _empty: dict[str, Any] = {
        "leads_today": 0,
        "leads_week": 0,
        "qualified_week": 0,
        "qualification_rate": 0.0,
        "best_score": None,
    }

    try:
        client = _get_supabase_client()

        resp_week = (
            client.table("leads")
            .select("score,qualified,created_at")
            .gte("created_at", week_start.isoformat())
            .execute()
        )
        rows_week = resp_week.data or []

        resp_today = (
            client.table("leads")
            .select("id")
            .gte("created_at", today_start.isoformat())
            .execute()
        )
        leads_today = len(resp_today.data or [])

        leads_week = len(rows_week)
        qualified_week = sum(
            1 for r in rows_week if r.get("qualified") or (r.get("score") or 0) >= 50
        )
        scores = [r["score"] for r in rows_week if r.get("score") is not None]
        best_score = max(scores) if scores else None
        qualification_rate = (
            (qualified_week / leads_week * 100) if leads_week > 0 else 0.0
        )

        return JSONResponse(
            content={
                "leads_today": leads_today,
                "leads_week": leads_week,
                "qualified_week": qualified_week,
                "qualification_rate": qualification_rate,
                "best_score": best_score,
            }
        )
    except Exception as exc:
        logger.error("Erreur stats: %s", exc)
        return JSONResponse(content=_empty)
