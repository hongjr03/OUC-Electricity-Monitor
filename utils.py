import os
from toml import load
import pandas as pd
from datetime import datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")


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


def get_visualize_host():
    return config["visualize"]["host"] if "host" in config["visualize"] else "localhost"


def get_visualize_port():
    return config["visualize"]["port"] if "port" in config["visualize"] else 8501


# 根据选择的时间范围获取数据
def get_data(model, time_range, is_YuE=False):
    if time_range == "最近 24 小时":
        start_time = datetime.now() - timedelta(hours=24)
    elif time_range == "最近 7 天":
        start_time = datetime.now() - timedelta(days=7)
    elif time_range == "最近 30 天":
        start_time = datetime.now() - timedelta(days=30)
    else:
        start_time = datetime.min

    query = model.select().where(model.time >= start_time).order_by(model.time)
    df = pd.DataFrame(list(query.dicts()))

    if not is_YuE:
        # 将 'charge' 列转换为 float 类型
        if "charge" in df.columns:
            df["charge"] = df["charge"].astype(float)
    else:
        if "balance" in df.columns:
            df["balance"] = df["balance"].astype(float)

    real_time_range = df["time"].max() - df["time"].min()
    return df, real_time_range


def get_consumption(data, tr):
    # print(tr)
    consumption_data = None
    consumption_time = tr

    # 计算相邻两个数据点的差值
    consumption = 0
    for i in range(1, len(data)):
        # print(data["charge"].iloc[i], data["charge"].iloc[i - 1])
        if data["charge"].iloc[i] < data["charge"].iloc[i - 1]:
            consumption += data["charge"].iloc[i - 1] - data["charge"].iloc[i]
        else:
            consumption_time -= data["time"].iloc[i - 1] - data["time"].iloc[i]
    consumption_data = pd.DataFrame(
        {
            "time": data["time"],
            "charge": data["charge"].diff().fillna(0).abs(),
        }
    )
    # 整理 consumption_data，根据 2 倍的 interval 合并该时间段的电费
    interval = config["cron"]["interval"] * 2
    consumption_data = consumption_data.groupby(
        pd.Grouper(key="time", freq=f"{interval}Min")
    )
    consumption_data = consumption_data.sum().reset_index()
    # 只存非 0 的数据
    consumption_data = consumption_data[consumption_data["charge"] > 0]
    # 使用 charge / 时间差 计算消耗率
    consumption_data_rate = consumption_data.copy()
    tmp_time = consumption_data_rate["time"].diff().dt.total_seconds() / 60
    consumption_data_rate["charge"] = (
        consumption_data_rate["charge"] / tmp_time * interval
    )
    consumption_data_rate = consumption_data_rate.fillna(0)
    consumption_data_rate = consumption_data_rate[consumption_data_rate["charge"] > 0]

    if consumption_time.total_seconds() > 0:
        consumption_rate = consumption / (consumption_time / timedelta(hours=1))
    else:
        consumption_rate = 0

    return consumption_data_rate, consumption_rate
