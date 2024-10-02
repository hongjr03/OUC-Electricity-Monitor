from peewee import *
import datetime
import time, os
from toml import dump, load
import requests

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")

try:
    if config["student"]["proxy"] == "false":
        root_url = "http://10.128.13.25"
    else:
        root_url = "https://lsky.lmark.cc"
except Exception as e:
    root_url = "https://lsky.lmark.cc"

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


class YuE(Model):
    balance = DecimalField()
    time = DateTimeField()

    class Meta:
        database = db


# 被 bash 调用，返回 crontab 的配置
def get_crontab():
    # 如果有 crontab
    if "crontab" in config["cron"]:
        # check crontab
        import re

        if re.match(r"^\*\/[1-9]\d* \* \* \* \*$", config["cron"]["crontab"]):
            return config["cron"]["crontab"]
        else:
            config["cron"]["crontab"] = f"*/5 * * * *"
            return f"*/5 * * * *"
    elif "interval" in config["cron"]:
        config["cron"]["interval"] = int(config["cron"]["interval"])
        if config["cron"]["interval"] < 1:
            config["cron"]["crontab"] = f"*/1 * * * *"
            return f"*/1 * * * *"
        elif config["cron"]["interval"] > 59:
            config["cron"]["crontab"] = f"*/59 * * * *"
            return f"*/59 * * * *"
        else:
            config["cron"]["crontab"] = f"*/{config['cron']['interval']} * * * *"
            return f"*/{config['cron']['interval']} * * * *"
    else:
        config["cron"]["crontab"] = f"*/5 * * * *"
        return f"*/5 * * * *"


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
        f"{root_url}/hydxcas/getCadByNo", headers=headers, json=sno_payload
    )

    if response.status_code == 200:
        response_data = response.json()

        value = response_data["value"]
        # print("Value:", value)
        try:
            value_dict = eval(value)
        # NameError
        except NameError as e:
            print(e)
            print("获取数据失败，请检查 config 配置并重新初始化。")
            exit(1)

        card = value_dict["card"]
        try:
            card_dict = eval(card)[0]
            account = card_dict["account"]
        except NameError as e:
            print(e)
            print("获取数据失败，请检查 config 配置并重新初始化。")
            exit(1)

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
            try:
                if categoryEnergyName == "空调末端":
                    KongTiao.create_table()
                    categoryEnergyName = "kongtiao"
                elif categoryEnergyName == "照明与插座":
                    ChaZuo.create_table()
                    categoryEnergyName = "chazuo"
            except Exception as e:
                print(e)
                print("创建数据库表失败，请检查 config 配置并重新初始化。")
                exit(1)
            config["student"]["equipments"][categoryEnergyName] = {}
            config["student"]["equipments"][categoryEnergyName]["equipmentInfoId"] = (
                eqptData[i]["equipmentInfoId"]
            )
            config["student"]["equipments"][categoryEnergyName]["roomName"] = eqptData[
                i
            ]["roomName"]

    dz_payload = {"account": account}
    response = requests.post(
        f"{root_url}/hydxcas/getDzByNo", headers=headers, json=dz_payload
    )
    if response.status_code == 200:
        try:
            YuE.create_table()
            config["student"]["account"] = account

        except Exception as e:
            print(e)
            print("处理账户信息失败，请检查 config 配置并重新初始化。")
            exit(1)
    else:
        print("获取账户信息失败，请检查网络连接或配置。")
        exit(1)

    with open("config.toml", "w", encoding="utf-8") as f:
        if "visualize" not in config or "title" not in config["visualize"]:
            config["visualize"] = {}
            config["visualize"]["title"] = "Electricity!"
        if "notify" not in config:
            config["notify"] = {}
            config["notify"]["chazuo_threshold"] = 10
            config["notify"]["kongtiao_threshold"] = 10
            config["notify"]["yue_threshold"] = 10
        else:
            if "chazuo_threshold" not in config["notify"]:
                config["notify"]["chazuo_threshold"] = 10
            if "kongtiao_threshold" not in config["notify"]:
                config["notify"]["kongtiao_threshold"] = 10
            if "yue_threshold" not in config["notify"]:
                config["notify"]["yue_threshold"] = 10
        get_crontab()
        dump(config, f)

    from get import get_latest_data

    data = get_latest_data()
    if data["status"] == 0:
        exit(1)
    else:
        ChaZuo.create(charge=data["chazuo"], time=data["time"])
        KongTiao.create(charge=data["kongtiao"], time=data["time"])
        YuE.create(balance=data["yue"], time=data["time"])
        print("初始化成功并已更新数据库！")
