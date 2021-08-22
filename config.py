class Config(object):
    TESTING = False
    TEMPLATES_AUTO_RELOAD = True
    SECRET_KEY = '______YOUR_SECRET__________'
    SEASURF_INCLUDE_OR_EXEMPT_VIEWS = 'include'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = \
        'mysql+mysqlconnector://crmdb:habrhabr@localhost/crmdb'


class ProductionConfig(Config):
    DEBUG = False
    LOGFILE = 'logs/Production.log'


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    LOGFILE = 'logs/Development.log'
