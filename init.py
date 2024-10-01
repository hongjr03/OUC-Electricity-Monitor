from peewee import *
import datetime
import time, os
from toml import dump, load
import requests

script_dir = os.path.dirname(os.path.abspath(__file__))

config = load(script_dir + "/config.toml")

db = None
if config["database"]["type"].lower() == "sqlite":
    db = SqliteDatabase(config["database"]["SQLite"]["file_path"])
elif config["database"]["type"].lower() == "mysql":
    db = MySQLDatabase(
        config["database"]["MySQL"]["database_name"],
        user=config["database"]["MySQL"]["username"],
        password=config["database"]["MySQL"]["password"],
        host=config["database"]["MySQL"]["host"],
        port=config["database"]["MySQL"]["port"],
    )

electricity_fee = config["student"]["electricity_fee"]


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


if __name__ == "__main__":
    id = config["student"]["id"]

    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,es-ES;q=0.5,es;q=0.4",
        "content-type": "application/json;charset=UTF-8",
        "systemsign": "se-pc",
        "token": "9f7c6e76979c4cb9dd3828f8cc44a5ef",
        "x-requested-with": "XMLHttpRequest",
    }

    sno_payload = {"sno": id}

    response = requests.post(
        "http://10.128.13.25/hydxcas/getCadByNo", headers=headers, json=sno_payload
    )

    if response.status_code == 200:
        response_data = response.json()

        value = response_data["value"]

        # print("Value:", value)
        value_dict = eval(value)
        eqptData = value_dict["eqptData"]
        eqptNum = len(eqptData)

        if eqptNum > 2:
            category = []

            for i in range(eqptNum):
                if eqptData[i]["categoryEnergyName"] == "空调末端":
                    category.append(
                        {
                            "categoryEnergyName": eqptData[i]["categoryEnergyName"],
                            "roomName": eqptData[i]["roomName"],
                            "index": i,
                        }
                    )

            print("请选择一个空调末端：")
            for i in range(len(category)):
                print(f"[{i + 1}]: {category[i]['roomName']}")

            index = int(input("请输入方框内的编号：")) - 1
            
            # 保留 "照明与插座" 和选择的空调末端
            eqptData = [
                eqptData[i]
                for i in range(eqptNum)
                if i == index or eqptData[i]["categoryEnergyName"] == "照明与插座"
            ]
            eqptNum = len(eqptData)
            # print(eqptData)

        # 在 config.toml 中添加 eqptNum 和各个设备的 equipmentInfoId
        config["student"]["equipments"] = {}
        for i in range(eqptNum):
            categoryEnergyName = eqptData[i]["categoryEnergyName"]
            if categoryEnergyName == "空调末端":
                KongTiao.create_table()
                categoryEnergyName = "kongtiao"
            elif categoryEnergyName == "照明与插座":
                ChaZuo.create_table()
                categoryEnergyName = "chazuo"
            config["student"]["equipments"][categoryEnergyName] = {}
            config["student"]["equipments"][categoryEnergyName]["equipmentInfoId"] = (
                eqptData[i]["equipmentInfoId"]
            )
            config["student"]["equipments"][categoryEnergyName]["roomName"] = eqptData[
                i
            ]["roomName"]

        with open("config.toml", "w", encoding="utf-8") as f:
            if "visualize" not in config or "title" not in config["visualize"]:
                config["visualize"] = {}
                config["visualize"]["title"] = "Electricity!"
            dump(config, f)
