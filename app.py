import enum
import json

from flask import Flask
from flask_restplus import Api, Resource, fields
from flask_sqlalchemy import SQLAlchemy
import requests


app = Flask(__name__)
api = Api(app)
db = SQLAlchemy(app)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pottyapi.db"


class Potty(db.Model):

    __tablename__ = "potty"

    class Status(enum.Enum):
        OCCUPIED = "OCCUPIED"
        VACANT = "VACANT"

    class Location(enum.Enum):
        NORTH = "NORTH"
        SOUTH = "SOUTH"
        EAST = "EAST"
        WEST = "WEST"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(Status))
    location = db.Column(db.Enum(Location))


class Subscriber(db.Model):

    __tablename__ = "subscriber"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text)


POTTY = api.model("Potty", {
    "id": fields.String,
    "status": fields.String(attribute="status.value"),
    "location": fields.String(attribute="location.value")
})


@api.route("/api/potties")
class PottiesResource(Resource):

    @api.marshal_list_with(POTTY)
    def get(self):
        params = self.get_request_query_params()
        return Potty.query.filter_by(**params).all()

    @api.marshal_with(POTTY)
    def post(self):
        args = self.get_request_args()
        potty = Potty(status=args["status"], location=args["location"])
        db.session.add(potty)
        db.session.commit()
        return potty

    def get_request_args(self):
        parser = api.parser()
        parser.add_argument("status", type=Potty.Status)
        parser.add_argument("location", type=Potty.Location)
        args = parser.parse_args()
        return args

    def get_request_query_params(self):
        parser = api.parser()
        parser.add_argument("status", type=Potty.Status, location="args", store_missing=False)
        params = parser.parse_args()
        return params


@api.route("/api/potties/<int:potty_id>")
class PottyResource(Resource):

    @api.marshal_with(POTTY)
    def get(self, potty_id):
        return Potty.query.filter_by(id=potty_id).first_or_404()

    @api.marshal_with(POTTY)
    def patch(self, potty_id):
        potty = Potty.query.filter_by(id=potty_id).first_or_404()
        old_status = potty.status
        args = self.get_request_args()
        # Update db with new values
        for arg, val, in args.items():
            setattr(potty, arg, val)
        db.session.add(potty)
        db.session.commit()
        # Inform subscribers
        subs = Subscriber.query.all()
        if old_status is not potty.status and subs != []:
            for sub in subs:
                data = {
                    "id": potty.id,
                    "old_status": old_status.name,
                    "current_status": potty.status.name,
                    "location": potty.location.name
                }
                try:
                    resp = requests.post(
                        sub.url,
                        json=data
                    )
                except:
                    # Delete sub since invalid url
                    db.session.delete(sub)
                    db.session.commit()
        return potty

    def get_request_args(self):
        parser = api.parser()
        parser.add_argument("status", type=Potty.Status)
        args = parser.parse_args()
        return args


SUBSCRIBER = api.model("Subscriber", {
    "id": fields.String,
    "url": fields.String
})


@api.route("/subscribers")
class SubscribersResource(Resource):

    @api.marshal_with(SUBSCRIBER)
    def post(self):
        args = self.get_request_args()
        sub = Subscriber(url=args["url"])
        db.session.add(sub)
        db.session.commit()
        return sub

    def get_request_args(self):
        parser = api.parser()
        parser.add_argument("url", required=True)
        args = parser.parse_args()
        return args


@api.route('/subscribers/<int:subscriber_id>')
class SubscriberResource(Resource):

    def delete(self, subscriber_id):
        sub = Subscriber.query.filter_by(id=subscriber_id).first_or_404()
        db.session.delete(sub)
        db.session.commit()


if __name__  == "__main__":
    app.run(debug=True)
