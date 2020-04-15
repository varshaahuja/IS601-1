import enum
from datetime import datetime

from app import db


class PurchaseType(enum.Enum):
    LAND = 1
    WORKER = 2
    WORKER_LFG = 3
    LAND_SURVEY = 4
    SMELTER = 5

    def __str__(self):
        return self.name  # value string

    def __html__(self):
        return self.value  # label string


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cost = db.Column(db.Integer, default=0)
    created = db.Column(db.DateTime, default=datetime.utcnow())
    # do we need to know about modified?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    purchase_type = db.Column(db.Enum(PurchaseType, create_constraint=False))





