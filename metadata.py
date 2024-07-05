
class Metadata():
    def __init__(self, su_id: str, description: str):
        self.su_id = su_id
        self.description = description
        self.channels = set()
