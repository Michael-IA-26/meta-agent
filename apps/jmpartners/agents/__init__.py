"""Agents spécialisés JM Partners.

Agents prévus (11) :
  01. mail_handler        — réception et routage des mails clients
  02. document_receiver   — réception et stockage des pièces justificatives
  03. document_analyzer   — extraction IA (factures, relevés bancaires)
  04. ecriture_generator  — génération des écritures comptables
  05. tva_declarator      — préparation et dépôt TVA
  06. is_tracker          — suivi des acomptes IS
  07. deadline_monitor    — surveillance du calendrier fiscal
  08. validation_agent    — validation des écritures par le gestionnaire
  09. report_builder      — génération rapports mensuels / annuels
  10. supabase_writer     — persistance transversale Supabase
  11. notifier            — alertes clients et équipe (email + Telegram)
"""
