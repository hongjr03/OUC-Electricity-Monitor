from peewee import *
import os
from toml import dump, load
import requests

from models import ChaZuo, KongTiao, YuE
from utils import get_crontab

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")

try:
    if "root_url" not in config["student"] or config["student"]["root_url"] == "":
        root_url = "http://10.128.13.25"
    else:
        root_url = config["student"]["root_url"]
        if root_url[-1] == "/":
            root_url = root_url[:-1]
        assert root_url.startswith("http")

except Exception as e:
    print(e)
    print(
        "请重新设置 config.toml 中的 proxy 字段，以 http:// 或 https:// 开头，或者删除该字段并连接校园网。"
    )
    exit(1)


electricity_fee = config["student"]["electricity_fee"]


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
