from peewee import *
import datetime
import time
from toml import dump, load
import requests

config = load("config.toml")

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
    # db.connect()
    # db.create_tables([ChaZuo, KongTiao])

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
            # 查看是否 categoryEnergyName 有多个空调末端
            # category = [
            #     {
            #         "categoryEnergyName": eqptData[i]["categoryEnergyName"],
            #         "roomName": eqptData[i]["roomName"],
            #         "index": i,
            #     } for i in range(eqptNum)
            # ]
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

            # 询问保留哪一个
            # 允许用户上下移动键盘选择

            import keyboard
            import time

            print("请选择一个空调末端：")
            for i in range(len(category)):
                print(f"{i + 1}: {category[i]['roomName']}")

            index = 0
            while True:
                if keyboard.is_pressed("up"):
                    index = (index - 1) % len(category)
                    time.sleep(0.2)
                elif keyboard.is_pressed("down"):
                    index = (index + 1) % len(category)
                    time.sleep(0.2)
                elif keyboard.is_pressed("enter"):
                    break
                print(f"\r当前选择：{index + 1}: {category[index]['roomName']}", end="")

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

        with open("config.toml", "w", encoding="utf-8") as f:
            # 如果没有 student.electricity_fee = 0.54，添加这一行
            if "electricity_fee" not in config["student"]:
                config["student"]["electricity_fee"] = 0.54
            dump(config, f)
