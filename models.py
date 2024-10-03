from peewee import *
import datetime
import time, os
from toml import dump, load

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")


db = None
if config["database"]["type"].lower() == "sqlite":
    # if the file exists, change to its absolute path
    if os.path.exists(config["database"]["SQLite"]["file_path"]):
        config["database"]["SQLite"]["file_path"] = os.path.abspath(
            config["database"]["SQLite"]["file_path"]
        )
    db = SqliteDatabase(config["database"]["SQLite"]["file_path"])
elif config["database"]["type"].lower() == "mysql":
    db = MySQLDatabase(
        config["database"]["MySQL"]["database_name"],
        user=config["database"]["MySQL"]["user"],
        password=config["database"]["MySQL"]["password"],
        host=config["database"]["MySQL"]["host"],
        port=config["database"]["MySQL"]["port"],
    )


class ChaZuo(Model):
    charge = DecimalField()
    time = DateTimeField()

    class Meta:
        database = db


class KongTiao(Model):
    charge = DecimalField()
    time = DateTimeField()

    class Meta:
        database = db


class YuE(Model):
    balance = DecimalField()
    time = DateTimeField()

    class Meta:
        database = db
