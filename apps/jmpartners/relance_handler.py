class RelanceHandler:
    def send_relance(self, email: str, niveau: int = 1) -> str:
        return f"relance_{niveau}_sent_to_{email}"

    def send_second_reminder(self, email: str) -> str:
        return self.send_relance(email, niveau=2)
