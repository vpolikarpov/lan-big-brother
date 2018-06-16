from peewee import *

db = SqliteDatabase('lan.db')


class BaseModel(Model):
    class Meta:
        database = db


class Person(BaseModel):
    name = CharField()


class Device(BaseModel):
    mac_addr = TextField(unique=True, primary_key=False)
    name = TextField(null=True)
    owner = ForeignKeyField(Person, null=True)

    def __str__(self):
        return '%s [%s]' % (self.name, self.mac_addr)


class ScanResult(BaseModel):
    time = DateTimeField()
    device = ForeignKeyField(Device, null=True)
    mac_addr = TextField()
    ip_addr = TextField()


def create_tables():
    return db.create_tables([Person, Device, ScanResult])
