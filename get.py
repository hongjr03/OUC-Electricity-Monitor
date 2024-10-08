import requests, os
from peewee import *
import datetime
from init import ChaZuo, KongTiao, YuE
from toml import load
import pandas as pd

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


def get_df(equipmentInfoId):
    url = f"{root_url}/feemanager/findSurplusElectricByMeterSearchPower.action"
    flag = False
    counter = 0
    while not flag:
        response = requests.request(
            "POST", url, data={"equipmentInfoId": equipmentInfoId}
        ).json()
        counter += 1
        if response.get("equipmentList"):
            flag = True
        if counter > 10:
            return None
    # print(response)
    equipmentList = response["equipmentList"]
    return {
        # 充值电量
        "surplus": float(equipmentList["roomSurplusBuyElecNum"]),
        # 赠送电量
        "give": float(equipmentList["roomSurplusGiveElecNum"]),
        # 总电量
        "total": float(equipmentList["roomSurplusBuyElecNum"])
        + float(equipmentList["roomSurplusGiveElecNum"]),
        # 按当前电压
        "voltage": equipmentList["line1Voltage"],
        # 当前电流
        "electricity": equipmentList["line1Electricity"],
    }


def get_yue(account):
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,es-ES;q=0.5,es;q=0.4",
        "content-type": "application/json;charset=UTF-8",
        "systemsign": "se-pc",
        "token": "9f7c6e76979c4cb9dd3828f8cc44a5ef",
        "x-requested-with": "XMLHttpRequest",
    }
    dz_payload = {"account": account}
    response = requests.post(
        f"{root_url}/hydxcas/getDzByNo", headers=headers, json=dz_payload
    )
    if response.status_code == 200:
        response_data = response.json()
        value = response_data["value"]
        value_dict = eval(value)[0]
        balance = value_dict.get("balance")
        balance = int(balance)
        return {"balance": f"{balance/100:.2f}"}


def get_latest_db_data(model, is_YuE=False):
    # 查询数据库，按时间降序排列，获取第一条记录
    query = model.select().order_by(model.time.desc()).limit(1)
    df = pd.DataFrame(list(query.dicts()))

    if not is_YuE:
        # 将 'charge' 列转换为 float 类型
        if "charge" in df.columns:
            df["charge"] = df["charge"].astype(float)

        return df["charge"].values[0] if not df.empty else 0.0
    else:
        if "balance" in df.columns:
            df["balance"] = df["balance"].astype(float)

        return df["balance"].values[0] if not df.empty else 0.0


def get_latest_data():
    try:
        print("获取数据...")
        chazuo_response = get_df(
            config["student"]["equipments"]["chazuo"]["equipmentInfoId"]
        )
        print("插座：", chazuo_response["total"])
        kongtiao_response = get_df(
            config["student"]["equipments"]["kongtiao"]["equipmentInfoId"]
        )
        print("空调：", kongtiao_response["total"])
        yue_response = get_yue(config["student"]["account"])
        print("余额：", yue_response["balance"])
        # YuE.create(balance=yue_response["balance"], time=datetime.datetime.now())
    except Exception as e:
        print(e)
        print("获取数据失败，请检查 config 配置并重新初始化。")

        return {
            "status": 0,
            "chazuo": 0,
            "kongtiao": 0,
            "yue": 0,
            "time": datetime.datetime.now(),
        }
        # 状态码，插座电量，空调电量

    return {
        "status": 1,
        "chazuo": chazuo_response["total"],
        "kongtiao": kongtiao_response["total"],
        "yue": yue_response["balance"],
        "time": datetime.datetime.now(),
    }


def notify(
    chazuo_info, kongtiao_info, yue_info, db_chazuo_info, db_kongtiao_info, db_yue_info
):
    try:
        chazuo_threshold = config["notify"]["chazuo_threshold"]
        kongtiao_threshold = config["notify"]["kongtiao_threshold"]
        yue_threshold = config["notify"]["yue_threshold"]
    except KeyError:
        print("请检查 config.toml 文件中的 notify 字段是否正确配置。")
        return

    try:
        from BarkNotificator import BarkNotificator

        bark = BarkNotificator(device_token=config["notify"]["bark"]["device_token"])
    except ImportError:
        print("未安装 BarkNotificator，请执行 `pip install BarkNotificator` 安装。")
        return

    if chazuo_info < chazuo_threshold:
        bark.send(
            title="插座电量不足",
            content=f"剩余 {chazuo_info:.2f} 度，请及时充电费！",
        )
    if kongtiao_info < kongtiao_threshold:
        bark.send(
            title="空调电量不足",
            content=f"剩余 {kongtiao_info:.2f} 度，请及时充电费！",
        )
    if yue_info < yue_threshold:
        bark.send(
            title="校园卡余额不足",
            content=f"剩余 {yue_info:.2f} 元，请及时充值！",
        )

    if chazuo_info - db_chazuo_info > 0:
        bark.send(title="插座", content=f"充入 {chazuo_info - db_chazuo_info:.2f} 度。")
    if kongtiao_info - db_kongtiao_info > 0:
        bark.send(
            title="空调",
            content=f"充入 {kongtiao_info - db_kongtiao_info:.2f} 度。",
        )
    if yue_info - db_yue_info > 0:
        bark.send(title="校园卡", content=f"充入 {yue_info - db_yue_info:.2f} 元。")


if __name__ == "__main__":

    # 获取距离现在最近的插座和空调数据
    db_chazuo_info = get_latest_db_data(ChaZuo)
    db_kongtiao_info = get_latest_db_data(KongTiao)
    db_yue_info = get_latest_db_data(YuE, is_YuE=True)

    data = get_latest_data()
    if data["status"] == 0:
        exit(1)
    else:
        ChaZuo.create(charge=data["chazuo"], time=data["time"])
        KongTiao.create(charge=data["kongtiao"], time=data["time"])
        YuE.create(balance=data["yue"], time=data["time"])

        chazuo_info = data["chazuo"]
        kongtiao_info = data["kongtiao"]
    yue_info = data["yue"]

    try:
        if config["notify"]["bark"]["enabled"]:
            notify(
                chazuo_info,
                kongtiao_info,
                yue_info,
                db_chazuo_info,
                db_kongtiao_info,
                db_yue_info,
            )
    # 如果没有配置 bark，则不发送通知
    except KeyError:
        pass

    # 返回值
