from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
db = SQLAlchemy()


def repr(self):
    mapper = inspect(self).mapper
    ent = []
    for col in mapper.column_attrs:
        ent.append("{0}={1}".format(col.key, getattr(self, col.key)))
    return "<{0}(".format(self.__class__.__name__) + ", ".join(ent) + ")>"


db.Model.__repr__ = repr


class AuthLog(db.Model):
    __tablename__ = 'auth_log'

    id = db.Column(db.Integer, primary_key=True)
    time_in = db.Column(db.DateTime, nullable=True,
                        server_default=db.FetchedValue())
    login = db.Column(db.String(32), nullable=False)

    def __init__(self, login=None):
        self.login = login


class CallHistory(db.Model):
    __tablename__ = 'call_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    client_id = db.Column(db.ForeignKey('clients.id'), nullable=False)
    incomming = db.Column(db.Integer, nullable=True,
                          server_default=db.FetchedValue())
    date_call = db.Column(db.DateTime, nullable=True,
                          server_default=db.FetchedValue())
    call_from = db.Column(db.BigInteger)
    call_to = db.Column(db.BigInteger)
    comment = db.Column(db.Text, nullable=True)

    client = db.relationship('Client',
                             primaryjoin='CallHistory.client_id == Client.id',
                             backref='call_history')

    def __init__(self, user_id=None, client_id=None, call_from=None,
                 call_to=None):
        self.user_id = user_id
        self.client_id = client_id
        self.call_from = call_from
        self.call_to = call_to


class CallRemind(db.Model):
    __tablename__ = 'call_remind'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Integer, nullable=False,
                       server_default=db.FetchedValue())
    user_id = db.Column(db.Integer, nullable=False)
    call_date = db.Column(db.DateTime, nullable=False)
    client_id = db.Column(db.ForeignKey('clients.id'), nullable=False)

    client = db.relationship('Client',
                             primaryjoin='CallRemind.client_id == Client.id',
                             backref='call_remind')

    def __init__(self, user_id=None, call_date=None, client_id=None):
        self.user_id = user_id
        self.call_date = call_date
        self.client_id = client_id


class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum('Потенциальный', 'Рабочий'), nullable=True)
    city = db.Column(db.String(32), nullable=True)
    segment = db.Column(db.String(32), nullable=True)
    company_name = db.Column(db.String(255), nullable=False)
    site = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(64), nullable=True)
    comments = db.Column(db.Text, nullable=True)
    create_date = db.Column(db.DateTime, nullable=True)
    last_update = db.Column(db.DateTime, nullable=True)
    loyalty = db.Column(db.Enum('Лояльный', 'Нелояльный'), nullable=True)
    activity = db.Column(db.String(64), nullable=True)

    def __init__(self, user_id=None, status=None, city=None, segment=None,
                 company_name=None, site=None, email=None, comments=None,
                 create_date=None, last_update=None, loyalty=None,
                 activity=None):
        self.user_id = user_id
        self.status = status
        self.city = city
        self.segment = segment
        self.company_name = company_name
        self.site = site
        self.email = email
        self.comments = comments
        self.loyalty = loyalty
        self.activity = activity


class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.ForeignKey('clients.id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    tel = db.Column(db.BigInteger, nullable=False)
    contact_person = db.Column(db.String(255), nullable=True)
    post = db.Column(db.String(64))

    client = db.relationship('Client',
                             primaryjoin='Contact.client_id == Client.id',
                             backref='contacts')

    def __init__(self, client_id=None, user_id=None, tel=None,
                 contact_person=None, post=None):
        self.client_id = client_id
        self.user_id = user_id
        self.tel = tel
        self.contact_person = contact_person
        self.post = post

    def check_uniq(tel):  # Проверка телефона на уникальность
        return Contact.query.filter_by(tel=tel).first()


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    color = db.Column(db.String(10), nullable=False)

    def __init__(self, user_id=None, start=None, end=None, title=None,
                 color=None):
        self.user_id = user_id
        self.start = start
        self.end = end
        self.title = title
        self.color = color


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(32), nullable=False)
    passw = db.Column(db.String(32), nullable=False)
    exten = db.Column(db.Integer, nullable=True)
    prefix = db.Column(db.String(2), nullable=True)
    role = db.Column(db.Enum('manager', 'ruk', 'boss'), nullable=False)
    ruk_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(64), nullable=True)

    def __init__(self, login=None, passw=None, exten=None, prefix=None,
                 role=None, ruk_id=None, name=None):
        self.login = login
        self.passw = passw
        self.exten = exten
        self.prefix = prefix
        self.role = role
        self.ruk_id = ruk_id
        self.name = name

    def check_exist(login, exten):
        if exten:
            # OR c помощью |
            return User.query.filter(
                (User.login == login) | (User.exten == exten)).first()

        else:
            return User.query.filter_by(login=login).first()
            
# card class for Kanban
class Card(db.Model):
    __tablename__ = 'card'
    id = db.Column(db.Integer, primary_key=True, unique=True)
    userid = db.Column(db.Integer, db.ForeignKey('user.userid'))
    status = db.Column(db.Integer) # whether to-do, in progress, or done
    header = db.Column(db.String(80))
    desc = db.Column(db.String(120))

    def __init__(self, userid, status, header, desc):
        self.userid = userid
        self.status = status
        self.header= header
        self.desc = desc