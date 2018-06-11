from peewee import *

db = SqliteDatabase('people.db')


class Person(Model):
    name = CharField()

    class Meta:
        database = db


class Device(Model):
    mac_addr = TextField(null=True, primary_key=True)
    name = TextField(null=True)
    owner = ForeignKeyField(Person, backref='devices')

    class Meta:
        database = db


class ScanResult(Model):
    time = DateTimeField()
    mac_addr = TextField()
    ip_addr = TextField()
