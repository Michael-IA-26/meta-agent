class EcheanceAgent:
    LATE_FEE_RATE = 0.10

    def get_echeance(self, dossier_id: str) -> dict:
        return {"dossier_id": dossier_id, "echeance": None}

    def compute_late_fee(self, montant: float) -> float:
        return round(montant * self.LATE_FEE_RATE, 2)
