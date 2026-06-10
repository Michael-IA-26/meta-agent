"""Dashboard FastAPI — JM Partners (démo beta 8 juin)."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

__all__ = ["app"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ---------------------------------------------------------------------------
# Mock data (utilisé si Supabase non disponible)
# ---------------------------------------------------------------------------

_TODAY = date.today()

_MOCK_DOSSIERS: list[dict[str, Any]] = [
    {
        "id": "d001",
        "contact_id": "c001",
        "contact_nom": "Dupont SARL",
        "type": "bilan",
        "statut": "actif",
        "deadline": (_TODAY + timedelta(days=12)).isoformat(),
        "documents_manquants": ["Grand Livre", "Balance"],
        "documents_presents": ["Factures Achats", "Relevés Bancaires"],
        "alertes": ["J-15"],
    },
    {
        "id": "d002",
        "contact_id": "c002",
        "contact_nom": "Martin & Associés",
        "type": "tva",
        "statut": "actif",
        "deadline": (_TODAY + timedelta(days=5)).isoformat(),
        "documents_manquants": ["CA Mensuel"],
        "documents_presents": ["Factures TVA", "Relevés Bancaires"],
        "alertes": ["J-7"],
    },
    {
        "id": "d003",
        "contact_id": "c003",
        "contact_nom": "Lemaire SAS",
        "type": "is",
        "statut": "actif",
        "deadline": (_TODAY + timedelta(days=2)).isoformat(),
        "documents_manquants": ["Liasse Fiscale"],
        "documents_presents": ["Résultat Comptable", "Bilan N-1"],
        "alertes": ["J-3"],
    },
    {
        "id": "d004",
        "contact_id": "c004",
        "contact_nom": "Bernard & Fils",
        "type": "bilan",
        "statut": "actif",
        "deadline": (_TODAY + timedelta(days=20)).isoformat(),
        "documents_manquants": [],
        "documents_presents": [
            "Grand Livre",
            "Balance",
            "Factures Achats",
            "Factures Ventes",
            "Relevés Bancaires",
        ],
        "alertes": [],
    },
    {
        "id": "d005",
        "contact_id": "c005",
        "contact_nom": "Petit Négoce",
        "type": "paie",
        "statut": "actif",
        "deadline": (_TODAY + timedelta(days=8)).isoformat(),
        "documents_manquants": ["Déclarations Sociales"],
        "documents_presents": ["Contrats Travail", "Bulletins Salaire"],
        "alertes": [],
    },
]


def _next_tva_deadlines() -> list[dict[str, Any]]:
    """Calcule les prochaines échéances TVA (le 20 du mois suivant)."""
    deadlines = []
    today = date.today()
    for delta_months in range(2):
        month = today.month + delta_months
        year = today.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        next_month = month + 1
        next_year = year + (next_month - 1) // 12
        next_month = ((next_month - 1) % 12) + 1
        deadline = date(next_year, next_month, 20)
        jours = (deadline - today).days
        if 0 <= jours <= 30:
            urgence = (
                "J-3"
                if jours <= 3
                else ("J-7" if jours <= 7 else ("J-15" if jours <= 15 else None))
            )
            deadlines.append(
                {
                    "type": "TVA",
                    "label": f"TVA {year}-{month:02d}",
                    "deadline": deadline.isoformat(),
                    "jours_restants": jours,
                    "urgence": urgence,
                    "couleur": "rouge"
                    if jours <= 3
                    else ("orange" if jours <= 7 else "jaune"),
                }
            )
    return deadlines


def _next_is_deadlines() -> list[dict[str, Any]]:
    """Calcule les prochaines échéances IS (15 mars/juin/sep/dec)."""
    today = date.today()
    is_months = [3, 6, 9, 12]
    deadlines = []
    for year in [today.year, today.year + 1]:
        for month in is_months:
            deadline = date(year, month, 15)
            jours = (deadline - today).days
            if 0 <= jours <= 30:
                urgence = (
                    "J-3"
                    if jours <= 3
                    else ("J-7" if jours <= 7 else ("J-15" if jours <= 15 else None))
                )
                trimestre = {3: "T1", 6: "T2", 9: "T3", 12: "T4"}[month]
                deadlines.append(
                    {
                        "type": "IS",
                        "label": f"Acompte IS {trimestre} {year}",
                        "deadline": deadline.isoformat(),
                        "jours_restants": jours,
                        "urgence": urgence,
                        "couleur": "rouge"
                        if jours <= 3
                        else ("orange" if jours <= 7 else "jaune"),
                    }
                )
    return deadlines


def _supabase_available() -> bool:
    """Vérifie que les variables Supabase sont configurées."""
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"))


def _get_supabase_client() -> Any:
    """Retourne un client Supabase ou lève une ValueError si manquant."""
    from supabase import create_client  # type: ignore[import-untyped]

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant")
    return create_client(url, key)


def _compute_alertes(deadline_str: str | None) -> list[str]:
    """Calcule les alertes J-3/J-7/J-15 depuis une deadline ISO."""
    if not deadline_str:
        return []
    try:
        dl = date.fromisoformat(str(deadline_str))
    except ValueError:
        return []
    jours = (dl - date.today()).days
    if jours <= 3:
        return ["J-3"]
    if jours <= 7:
        return ["J-7"]
    if jours <= 15:
        return ["J-15"]
    return []


def _fetch_dossiers_from_supabase() -> list[dict[str, Any]]:
    """Récupère les dossiers actifs depuis Supabase."""
    client = _get_supabase_client()
    resp = (
        client.table("dossiers")
        .select("id, contact_id, type, statut, deadline, contacts(nom)")
        .eq("statut", "actif")
        .execute()
    )
    dossiers: list[dict[str, Any]] = []
    for row in resp.data or []:
        contacts_field = row.get("contacts")
        contact_nom: str | None = None
        if isinstance(contacts_field, dict):
            contact_nom = contacts_field.get("nom")

        deadline_val = row.get("deadline")
        alertes = _compute_alertes(deadline_val)

        # Fetch documents for this dossier
        docs_manquants: list[str] = []
        docs_presents: list[str] = []
        try:
            docs_resp = (
                client.table("documents")
                .select("nom_document, type_document, statut")
                .eq("dossier_id", row.get("id"))
                .execute()
            )
            for doc in docs_resp.data or []:
                nom = doc.get("nom_document") or doc.get("type_document", "")
                if doc.get("statut") in ("recu", "valide"):
                    docs_presents.append(nom)
                else:
                    docs_manquants.append(nom)
        except Exception as exc:
            logger.warning(
                "Erreur fetch documents pour dossier %s: %s", row.get("id"), exc
            )

        dossier: dict[str, Any] = {
            "id": row.get("id"),
            "contact_id": row.get("contact_id"),
            "contact_nom": contact_nom,
            "type": row.get("type", ""),
            "statut": row.get("statut", ""),
            "deadline": deadline_val,
            "documents_manquants": docs_manquants,
            "documents_presents": docs_presents,
            "alertes": alertes,
        }
        dossiers.append(dossier)
    return dossiers


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>JM Partners — Dashboard</title>
  <style>
    :root {
      --primary: #1a3a5c;
      --primary-light: #2563a8;
      --accent: #e8b84b;
      --bg: #f5f7fa;
      --card-bg: #ffffff;
      --border: #dde1e8;
      --text: #1e2d40;
      --text-muted: #6b7a90;
      --red: #dc2626;
      --orange: #ea580c;
      --yellow: #ca8a04;
      --green: #16a34a;
      --red-bg: #fef2f2;
      --orange-bg: #fff7ed;
      --yellow-bg: #fefce8;
      --green-bg: #f0fdf4;
      --radius: 8px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    /* Header */
    header {
      background: var(--primary);
      color: white;
      padding: 0 2rem;
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 8px rgba(0,0,0,.25);
    }
    .header-left { display: flex; align-items: center; gap: 12px; }
    .logo {
      width: 38px; height: 38px;
      background: var(--accent);
      border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 800; font-size: 1.1rem; color: var(--primary);
    }
    .cabinet-name { font-size: 1.15rem; font-weight: 600; letter-spacing: .3px; }
    .header-right { display: flex; align-items: center; gap: 16px; font-size: .85rem; opacity: .85; }
    #header-date { font-weight: 500; }

    /* Main */
    main { padding: 2rem; max-width: 1400px; margin: 0 auto; }

    /* KPI Cards */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem 1.5rem;
      display: flex; align-items: center; gap: 1rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.06);
    }
    .kpi-icon {
      width: 44px; height: 44px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.4rem; flex-shrink: 0;
    }
    .kpi-icon.blue { background: #eff6ff; }
    .kpi-icon.orange { background: var(--orange-bg); }
    .kpi-icon.red { background: var(--red-bg); }
    .kpi-icon.green { background: var(--green-bg); }
    .kpi-info { flex: 1; }
    .kpi-value { font-size: 2rem; font-weight: 700; line-height: 1; }
    .kpi-label { font-size: .8rem; color: var(--text-muted); margin-top: 2px; }

    /* Section titles */
    .section-title {
      font-size: 1rem; font-weight: 600;
      color: var(--primary);
      margin-bottom: 1rem;
      display: flex; align-items: center; gap: 8px;
    }

    /* Kanban */
    .kanban {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem;
      margin-bottom: 2rem;
    }
    @media (max-width: 900px) { .kanban { grid-template-columns: 1fr; } }
    .kanban-col {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,.06);
    }
    .kanban-col-header {
      padding: .75rem 1rem;
      font-size: .85rem; font-weight: 600;
      display: flex; align-items: center; justify-content: space-between;
    }
    .kanban-col-header.col-missing { background: #fef2f2; color: var(--red); border-bottom: 2px solid #fca5a5; }
    .kanban-col-header.col-waiting { background: #fff7ed; color: var(--orange); border-bottom: 2px solid #fdba74; }
    .kanban-col-header.col-complete { background: #f0fdf4; color: var(--green); border-bottom: 2px solid #86efac; }
    .kanban-badge {
      background: rgba(0,0,0,.12);
      border-radius: 20px;
      padding: 1px 8px;
      font-size: .75rem;
    }
    .kanban-cards { padding: .5rem; display: flex; flex-direction: column; gap: .5rem; min-height: 80px; }
    .kanban-card {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: .75rem;
      font-size: .83rem;
    }
    .kanban-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
    .kanban-card-name { font-weight: 600; }
    .kanban-card-type {
      background: var(--primary);
      color: white;
      border-radius: 4px;
      padding: 1px 6px;
      font-size: .7rem;
      text-transform: uppercase;
    }
    .kanban-card-docs { color: var(--text-muted); font-size: .78rem; }
    .kanban-card-deadline { font-size: .75rem; color: var(--text-muted); margin-top: 4px; }
    .alert-badge {
      display: inline-block;
      border-radius: 4px;
      padding: 1px 6px;
      font-size: .7rem;
      font-weight: 600;
      margin-right: 4px;
    }
    .alert-j15 { background: #fef9c3; color: var(--yellow); }
    .alert-j7  { background: #ffedd5; color: var(--orange); }
    .alert-j3  { background: #fee2e2; color: var(--red); }
    .relance-btn {
      margin-top: 6px;
      background: var(--primary-light);
      color: white;
      border: none;
      border-radius: 4px;
      padding: 3px 10px;
      font-size: .75rem;
      cursor: pointer;
      transition: opacity .2s;
    }
    .relance-btn:hover { opacity: .85; }

    /* Bottom grid */
    .bottom-grid {
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 1rem;
    }
    @media (max-width: 1100px) { .bottom-grid { grid-template-columns: 1fr; } }

    /* Calendar */
    .calendar-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.06);
    }
    .calendar-grid {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 4px;
      margin-top: .75rem;
    }
    .cal-day-name {
      text-align: center; font-size: .7rem;
      font-weight: 600; color: var(--text-muted);
      padding: 4px 0;
    }
    .cal-day {
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 4px;
      min-height: 52px;
      font-size: .7rem;
      position: relative;
      transition: background .15s;
    }
    .cal-day:hover { background: var(--bg); }
    .cal-day.today { border-color: var(--primary-light); background: #eff6ff; }
    .cal-day.other-month { opacity: .35; }
    .cal-day-num {
      font-weight: 600;
      font-size: .75rem;
      color: var(--text);
      margin-bottom: 2px;
    }
    .cal-badge {
      display: block;
      border-radius: 3px;
      padding: 1px 3px;
      font-size: .62rem;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 2px;
    }
    .cal-badge.tva-j15 { background: #fef9c3; color: #854d0e; }
    .cal-badge.tva-j7  { background: #ffedd5; color: #9a3412; }
    .cal-badge.tva-j3  { background: #fee2e2; color: #991b1b; }
    .cal-badge.is-j15  { background: #dbeafe; color: #1e40af; }
    .cal-badge.is-j7   { background: #e0e7ff; color: #3730a3; }
    .cal-badge.is-j3   { background: #ede9fe; color: #5b21b6; }

    /* Dry run panel */
    .dryrun-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.06);
      display: flex;
      flex-direction: column;
      gap: .75rem;
    }
    .dryrun-desc { font-size: .85rem; color: var(--text-muted); }
    .dryrun-btn {
      background: var(--primary);
      color: white;
      border: none;
      border-radius: var(--radius);
      padding: .75rem 1.25rem;
      font-size: .9rem;
      font-weight: 600;
      cursor: pointer;
      transition: background .2s;
    }
    .dryrun-btn:hover { background: var(--primary-light); }
    .dryrun-btn:disabled { opacity: .55; cursor: default; }
    #dryrun-output {
      background: #1e2d40;
      color: #a8c8e8;
      border-radius: 6px;
      padding: .75rem;
      font-size: .78rem;
      font-family: "SFMono-Regular", Consolas, monospace;
      white-space: pre-wrap;
      min-height: 80px;
      display: none;
    }

    /* Loading / error */
    .loading { text-align: center; padding: 2rem; color: var(--text-muted); font-size: .9rem; }
    .error-msg {
      background: var(--red-bg); color: var(--red);
      border: 1px solid #fca5a5; border-radius: 6px;
      padding: .75rem 1rem; font-size: .85rem;
    }

    /* Toast */
    #toast {
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      background: var(--primary); color: white;
      padding: .7rem 1.2rem; border-radius: var(--radius);
      font-size: .85rem; opacity: 0;
      transition: opacity .3s;
      pointer-events: none;
      z-index: 1000;
    }
    #toast.visible { opacity: 1; }
  </style>
</head>
<body>
<header>
  <div class="header-left">
    <div class="logo">JM</div>
    <span class="cabinet-name">JM Partners — Cabinet Comptable</span>
  </div>
  <div class="header-right">
    <span id="header-date"></span>
    <span>Dashboard v1.0 · Beta 8 juin</span>
  </div>
</header>

<main>
  <!-- KPI Section -->
  <div class="kpi-grid" id="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-icon blue">📁</div>
      <div class="kpi-info">
        <div class="kpi-value" id="kpi-actifs">—</div>
        <div class="kpi-label">Dossiers actifs</div>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon orange">⚠️</div>
      <div class="kpi-info">
        <div class="kpi-value" id="kpi-alertes">—</div>
        <div class="kpi-label">Alertes J-7</div>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon red">🔴</div>
      <div class="kpi-info">
        <div class="kpi-value" id="kpi-urgents">—</div>
        <div class="kpi-label">Urgences J-3</div>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon green">📅</div>
      <div class="kpi-info">
        <div class="kpi-value" id="kpi-echeances">—</div>
        <div class="kpi-label">Échéances 7 jours</div>
      </div>
    </div>
  </div>

  <!-- Kanban -->
  <div class="section-title">
    <span>Vue Kanban — Dossiers</span>
  </div>
  <div class="kanban" id="kanban">
    <div class="kanban-col">
      <div class="kanban-col-header col-missing">
        <span>Documents manquants</span>
        <span class="kanban-badge" id="badge-missing">0</span>
      </div>
      <div class="kanban-cards" id="col-missing"></div>
    </div>
    <div class="kanban-col">
      <div class="kanban-col-header col-waiting">
        <span>En attente</span>
        <span class="kanban-badge" id="badge-waiting">0</span>
      </div>
      <div class="kanban-cards" id="col-waiting"></div>
    </div>
    <div class="kanban-col">
      <div class="kanban-col-header col-complete">
        <span>Complet</span>
        <span class="kanban-badge" id="badge-complete">0</span>
      </div>
      <div class="kanban-cards" id="col-complete"></div>
    </div>
  </div>

  <!-- Bottom: Calendar + Dry Run -->
  <div class="bottom-grid">
    <div class="calendar-card">
      <div class="section-title">Calendrier des 30 prochains jours</div>
      <div id="calendar-legend" style="font-size:.75rem;color:var(--text-muted);margin-bottom:.5rem;">
        <span style="background:#fef9c3;color:#854d0e;border-radius:3px;padding:1px 5px;margin-right:6px;">TVA J-15</span>
        <span style="background:#ffedd5;color:#9a3412;border-radius:3px;padding:1px 5px;margin-right:6px;">TVA J-7</span>
        <span style="background:#fee2e2;color:#991b1b;border-radius:3px;padding:1px 5px;margin-right:6px;">TVA J-3</span>
        <span style="background:#dbeafe;color:#1e40af;border-radius:3px;padding:1px 5px;margin-right:6px;">IS J-15</span>
        <span style="background:#e0e7ff;color:#3730a3;border-radius:3px;padding:1px 5px;margin-right:6px;">IS J-7</span>
        <span style="background:#ede9fe;color:#5b21b6;border-radius:3px;padding:1px 5px;">IS J-3</span>
      </div>
      <div class="calendar-grid" id="cal-grid"></div>
    </div>

    <div class="dryrun-card">
      <div class="section-title">Simulation du cycle</div>
      <p class="dryrun-desc">
        Lance un cycle complet (mail → relances → TVA → échéances)
        en mode <strong>dry-run</strong> : aucun email envoyé, aucune
        écriture en base.
      </p>
      <button class="dryrun-btn" id="dryrun-btn" onclick="runDryRun()">
        ▶ Simuler le cycle (dry-run)
      </button>
      <pre id="dryrun-output"></pre>
    </div>
  </div>
</main>

<div id="toast"></div>

<script>
  // ---- Utilities ----
  function showToast(msg, duration = 3000) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('visible');
    setTimeout(() => t.classList.remove('visible'), duration);
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  }

  // ---- Header date ----
  document.getElementById('header-date').textContent =
    new Date().toLocaleDateString('fr-FR', { weekday:'long', day:'numeric', month:'long', year:'numeric' });

  // ---- Kanban card builder ----
  function buildCard(d) {
    const alerteHtml = (d.alertes || []).map(a => {
      const cls = a === 'J-3' ? 'alert-j3' : (a === 'J-7' ? 'alert-j7' : 'alert-j15');
      return `<span class="alert-badge ${cls}">${a}</span>`;
    }).join('');

    const manqHtml = d.documents_manquants && d.documents_manquants.length
      ? `<div class="kanban-card-docs">Manquants : ${d.documents_manquants.slice(0,3).join(', ')}${d.documents_manquants.length > 3 ? ' +…' : ''}</div>`
      : '';

    const deadlineHtml = d.deadline
      ? `<div class="kanban-card-deadline">Deadline : ${fmtDate(d.deadline)}</div>`
      : '';

    return `
      <div class="kanban-card">
        <div class="kanban-card-header">
          <span class="kanban-card-name">${d.contact_nom || d.contact_id || d.id}</span>
          <span class="kanban-card-type">${d.type}</span>
        </div>
        ${alerteHtml ? `<div>${alerteHtml}</div>` : ''}
        ${manqHtml}
        ${deadlineHtml}
        ${d.documents_manquants && d.documents_manquants.length
          ? `<button class="relance-btn" onclick="relancer('${d.id}')">Relancer</button>`
          : ''}
      </div>`;
  }

  // ---- Load dossiers ----
  async function loadDossiers() {
    const [missingEl, waitingEl, completeEl] = [
      document.getElementById('col-missing'),
      document.getElementById('col-waiting'),
      document.getElementById('col-complete')
    ];
    missingEl.innerHTML = '<div class="loading">Chargement…</div>';
    try {
      const resp = await fetch('/api/dossiers');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const dossiers = await resp.json();

      let missing = [], waiting = [], complete = [];
      dossiers.forEach(d => {
        if (d.documents_manquants && d.documents_manquants.length > 0) missing.push(d);
        else if (d.statut === 'actif' && (!d.documents_manquants || !d.documents_manquants.length)) complete.push(d);
        else waiting.push(d);
      });
      // Heuristic: dossiers with no missing docs but deadline soon → waiting
      complete.forEach((d, i) => {
        if (d.deadline) {
          const days = Math.ceil((new Date(d.deadline) - new Date()) / 86400000);
          if (days <= 15 && days > 0) { waiting.push(d); complete.splice(i, 1); }
        }
      });

      missingEl.innerHTML = missing.length ? missing.map(buildCard).join('') : '<div class="loading">Aucun</div>';
      waitingEl.innerHTML = waiting.length ? waiting.map(buildCard).join('') : '<div class="loading">Aucun</div>';
      completeEl.innerHTML = complete.length ? complete.map(buildCard).join('') : '<div class="loading">Aucun</div>';

      document.getElementById('badge-missing').textContent = missing.length;
      document.getElementById('badge-waiting').textContent = waiting.length;
      document.getElementById('badge-complete').textContent = complete.length;

      // KPIs
      document.getElementById('kpi-actifs').textContent = dossiers.length;
      const j7 = dossiers.filter(d => (d.alertes || []).includes('J-7') || (d.alertes || []).includes('J-3')).length;
      const j3 = dossiers.filter(d => (d.alertes || []).includes('J-3')).length;
      document.getElementById('kpi-alertes').textContent = j7;
      document.getElementById('kpi-urgents').textContent = j3;

    } catch (e) {
      missingEl.innerHTML = `<div class="error-msg">Erreur : ${e.message}</div>`;
      waitingEl.innerHTML = '';
      completeEl.innerHTML = '';
    }
  }

  // ---- Load echeances + calendar ----
  async function loadEcheances() {
    try {
      const resp = await fetch('/api/echeances');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      const echeances = data.echeances || [];
      const dans7j = echeances.filter(e => e.jours_restants <= 7).length;
      document.getElementById('kpi-echeances').textContent = dans7j;

      buildCalendar(echeances);
    } catch (e) {
      console.error('Erreur écheances:', e);
    }
  }

  // ---- Calendar builder ----
  function buildCalendar(echeances) {
    const grid = document.getElementById('cal-grid');
    const today = new Date();
    today.setHours(0,0,0,0);

    // Day names
    const days = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];
    let html = days.map(d => `<div class="cal-day-name">${d}</div>`).join('');

    // Build 5 weeks starting from Monday of current week
    const startOfWeek = new Date(today);
    const dow = (today.getDay() + 6) % 7; // Mon=0
    startOfWeek.setDate(today.getDate() - dow);

    // Build echeance map by date
    const echeanceMap = {};
    echeances.forEach(e => {
      if (!echeanceMap[e.deadline]) echeanceMap[e.deadline] = [];
      echeanceMap[e.deadline].push(e);
    });

    const endDate = new Date(today);
    endDate.setDate(today.getDate() + 30);

    for (let i = 0; i < 35; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      const iso = d.toISOString().slice(0,10);
      const isToday = d.getTime() === today.getTime();
      const inRange = d >= today && d <= endDate;
      const otherMonth = d.getMonth() !== today.getMonth() && !inRange;
      let cls = 'cal-day';
      if (isToday) cls += ' today';
      if (otherMonth) cls += ' other-month';

      let badges = '';
      if (echeanceMap[iso]) {
        echeanceMap[iso].forEach(e => {
          const t = e.type.toLowerCase();
          const j = e.jours_restants;
          const badgeCls = `${t}-${j <= 3 ? 'j3' : (j <= 7 ? 'j7' : 'j15')}`;
          badges += `<span class="cal-badge ${badgeCls}">${e.type} ${e.label ? e.label.split(' ')[1] || '' : ''}</span>`;
        });
      }

      html += `<div class="${cls}">
        <div class="cal-day-num">${d.getDate()}</div>
        ${badges}
      </div>`;
    }
    grid.innerHTML = html;
  }

  // ---- Relance ----
  async function relancer(dossierId) {
    try {
      const resp = await fetch(`/api/relancer/${dossierId}`, { method: 'POST' });
      const data = await resp.json();
      showToast(data.message || 'Relance envoyée');
    } catch (e) {
      showToast('Erreur lors de la relance');
    }
  }

  // ---- Dry Run ----
  async function runDryRun() {
    const btn = document.getElementById('dryrun-btn');
    const output = document.getElementById('dryrun-output');
    btn.disabled = true;
    btn.textContent = '⏳ Simulation en cours…';
    output.style.display = 'block';
    output.textContent = 'Lancement du cycle dry-run…\\n';
    try {
      const resp = await fetch('/api/dry-run', { method: 'POST' });
      const data = await resp.json();
      output.textContent = JSON.stringify(data, null, 2);
      showToast('Simulation terminée');
    } catch (e) {
      output.textContent = 'Erreur : ' + e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = '▶ Simuler le cycle (dry-run)';
    }
  }

  // ---- Init ----
  loadDossiers();
  loadEcheances();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="JM Partners Dashboard",
    description="Dashboard de gestion des dossiers et échéances — JM Partners",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Retourne le dashboard HTML."""
    return HTMLResponse(content=_HTML_TEMPLATE)


@app.get("/api/dossiers")
async def get_dossiers() -> JSONResponse:
    """Retourne tous les dossiers actifs avec alertes documents manquants."""
    if _supabase_available():
        try:
            dossiers = _fetch_dossiers_from_supabase()
            return JSONResponse(content=dossiers)
        except Exception as exc:
            logger.warning(f"Supabase unavailable, using mock data: {exc}")

    return JSONResponse(content=_MOCK_DOSSIERS)


def _urgence_niveau(jours: int) -> str | None:
    """Retourne le niveau d'urgence selon le nombre de jours restants."""
    if jours <= 3:
        return "J-3"
    if jours <= 7:
        return "J-7"
    if jours <= 15:
        return "J-15"
    return None


@app.get("/api/echeances")
async def get_echeances() -> JSONResponse:
    """Retourne les échéances TVA + IS des 30 prochains jours."""
    today = date.today()
    horizon = today + timedelta(days=30)
    echeances: list[dict[str, Any]] = []
    supabase_used = False

    try:
        client = _get_supabase_client()

        # Déclarations TVA depuis Supabase
        resp_tva = (
            client.table("declarations_tva")
            .select("id, dossier_id, periode, statut, deadline, montant_tva")
            .gte("deadline", today.isoformat())
            .lte("deadline", horizon.isoformat())
            .neq("statut", "valide")
            .execute()
        )
        for row in resp_tva.data or []:
            dl_str = row.get("deadline")
            if not dl_str:
                continue
            try:
                dl = date.fromisoformat(str(dl_str))
            except ValueError:
                continue
            jours = (dl - today).days
            echeances.append(
                {
                    "type": "TVA",
                    "label": f"TVA {row.get('periode', '')}",
                    "deadline": dl_str,
                    "jours_restants": jours,
                    "urgence": _urgence_niveau(jours),
                    "niveau": _urgence_niveau(jours),
                    "couleur": "rouge"
                    if jours <= 3
                    else ("orange" if jours <= 7 else "jaune"),
                }
            )

        # Acomptes IS depuis Supabase
        resp_is = (
            client.table("acomptes_is")
            .select("id, dossier_id, exercice, statut, deadline, montant")
            .gte("deadline", today.isoformat())
            .lte("deadline", horizon.isoformat())
            .neq("statut", "paye")
            .execute()
        )
        for row in resp_is.data or []:
            dl_str = row.get("deadline")
            if not dl_str:
                continue
            try:
                dl = date.fromisoformat(str(dl_str))
            except ValueError:
                continue
            jours = (dl - today).days
            echeances.append(
                {
                    "type": "IS",
                    "label": f"Acompte IS {row.get('exercice', '')}",
                    "deadline": dl_str,
                    "jours_restants": jours,
                    "urgence": _urgence_niveau(jours),
                    "niveau": _urgence_niveau(jours),
                    "couleur": "rouge"
                    if jours <= 3
                    else ("orange" if jours <= 7 else "jaune"),
                }
            )

        supabase_used = True
    except Exception as exc:
        logger.warning(
            "Supabase indisponible pour écheances, fallback algorithmique: %s", exc
        )

    # Fallback sur calcul algorithmique si tables vides ou Supabase down
    if not supabase_used or not echeances:
        echeances = []
        echeances.extend(_next_tva_deadlines())
        echeances.extend(_next_is_deadlines())

    echeances.sort(key=lambda e: e["jours_restants"])

    rouge = sum(1 for e in echeances if e["jours_restants"] <= 3)
    orange = sum(1 for e in echeances if 3 < e["jours_restants"] <= 7)
    jaune = sum(1 for e in echeances if 7 < e["jours_restants"] <= 15)

    return JSONResponse(
        content={
            "total": len(echeances),
            "rouge": rouge,
            "orange": orange,
            "jaune": jaune,
            "echeances": echeances,
        }
    )


@app.post("/api/relancer/{dossier_id}")
async def relancer_dossier(dossier_id: str) -> JSONResponse:
    """Déclenche une relance pour un dossier."""
    cabinet_id = os.getenv("CABINET_ID", "")

    # Tente d'utiliser RelanceHandler si disponible
    try:
        from apps.jmpartners.agents.relance_handler import (  # type: ignore[attr-defined]  # noqa: PLC0415
            RelanceHandler,
        )

        handler = RelanceHandler(cabinet_id=cabinet_id)
        handler.run(dossier_id)
        return JSONResponse(
            content={
                "dossier_id": dossier_id,
                "status": "relance_envoyee",
            }
        )
    except ImportError:
        pass
    except Exception as exc:
        logger.error("RelanceHandler erreur pour %s: %s", dossier_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Fallback : utilise les fonctions run() existantes
    try:
        from apps.jmpartners.agents.document_checker import (
            run as check_docs,  # noqa: PLC0415
        )
        from apps.jmpartners.agents.relance_handler import (
            run as send_relance,  # noqa: PLC0415
        )

        doc_result = check_docs(dossier_id, dry_run=False)
        relance_result = send_relance(doc_result, dry_run=False)
        return JSONResponse(
            content={
                "dossier_id": dossier_id,
                "statut": "ok" if relance_result.get("envoye") else "skipped",
                "message": f"Relance envoyée pour le dossier {dossier_id}",
                "details": relance_result,
            }
        )
    except Exception as exc:
        logger.warning("Relance failed for %s, using mock: %s", dossier_id, exc)
        return JSONResponse(
            content={
                "dossier_id": dossier_id,
                "statut": "mock",
                "message": f"Relance simulée pour le dossier {dossier_id} (config email absente)",
            }
        )


_AGENT_NAMES = [
    "mail_handler", "tva_agent", "echeance_agent", "cloture_handler",
    "acompte_is_agent", "bilan_agent", "declaration_is_agent",
    "document_checker", "relance_handler", "notification_agent",
]


@app.get("/health")
async def health() -> JSONResponse:
    """Retourne l'état du service et le dernier run depuis journaux."""
    agents = {name: "ok" for name in _AGENT_NAMES}
    dernier_run: dict[str, Any] | None = None

    if _supabase_available():
        try:
            client = _get_supabase_client()
            resp = (
                client.table("journaux")
                .select("created_at, metadata")
                .eq("type_action", "orchestrator_run")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                row = resp.data[0]
                meta = row.get("metadata") or {}
                dernier_run = {
                    "timestamp": row.get("created_at"),
                    "duree_secondes": meta.get("duree_secondes"),
                    "agents_ok": meta.get("agents_ok"),
                    "agents_ko": meta.get("agents_ko"),
                    "erreurs": meta.get("erreurs", []),
                }
        except Exception as exc:
            logger.warning(f"Health — impossible de lire journaux : {exc}")

    return JSONResponse(content={
        "statut": "ok",
        "agents": agents,
        "dernier_run": dernier_run,
    })


@app.post("/api/dry-run")
async def dry_run() -> JSONResponse:
    """Simule le cycle complet sans envoi ni écriture."""
    try:
        from apps.jmpartners.orchestrator import run as orchestrate  # noqa: PLC0415

        result = orchestrate(dry_run=True)
        return JSONResponse(
            content={
                "dry_run": True,
                "result": result,
                "statut": "ok",
                "erreurs": result.get("erreurs", []),
            }
        )
    except Exception as exc:
        logger.warning("Orchestrateur dry-run failed, using mock: %s", exc)
        return JSONResponse(
            content={
                "dry_run": True,
                "result": {
                    "mail": {"emails": [], "statut": "ok"},
                    "relances": [],
                    "tva": {"declarations_analysees": 3, "alertes": 1, "statut": "ok"},
                    "echeances": {
                        "echeances_total": 4,
                        "rouge": 1,
                        "orange": 2,
                        "vert": 1,
                    },
                    "erreurs": [],
                },
                "statut": "mock",
                "message": "Simulation complète (mode démo)",
                "erreurs": [],
            }
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.jmpartners.dashboard:app", host="0.0.0.0", port=8080, reload=True)
