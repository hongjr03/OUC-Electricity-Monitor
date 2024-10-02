import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from init import ChaZuo, KongTiao, electricity_fee
from toml import load
import os
from streamlit_echarts import st_echarts

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")
if "visualize" not in config or "title" not in config["visualize"]:
    st.error("请先运行 init.py 文件")
    st.stop()
# Streamlit 应用
st.title(config["visualize"]["title"])

col1, col2 = st.columns([3, 1], vertical_alignment="bottom")

# 选择时间范围
time_range = col1.selectbox(
    "选择时间范围", ("最近 24 小时", "最近 7 天", "最近 30 天", "全部")
)
# 按钮，点击获取最新数据
if col2.button("获取最新数据"):
    with st.spinner("获取数据..."):
        from get import get_latest_data

        data = get_latest_data()
        if data["status"] == 1:
            current_chazuo = data["chazuo"]
            current_kongtiao = data["kongtiao"]
            st.toast("获取数据成功，已更新到数据库与页面！", icon="🔥")
        else:
            st.toast(
                "获取数据失败，数据为 0，请检查 config 配置并重新初始化。", icon="🚨"
            )


# 根据选择的时间范围获取数据
def get_data(model, time_range):
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

    # 将 'charge' 列转换为 float 类型
    if "charge" in df.columns:
        df["charge"] = df["charge"].astype(float)

    real_time_range = df["time"].max() - df["time"].min()
    return df, real_time_range


# 获取插座和空调数据
chazuo_data, chazuo_tr = get_data(ChaZuo, time_range)
kongtiao_data, kongtiao_tr = get_data(KongTiao, time_range)


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
            {"time": data["time"], "charge": data["charge"].diff().fillna(0).abs()}
        )
    # print(consumption_time)
    if consumption_time.total_seconds() > 0:
        consumption_rate = consumption / (consumption_time / timedelta(hours=1))
    else:
        consumption_rate = 0

    return consumption_data, consumption_rate


def visualize_consumption_data(data, header, tr, current):
    st.header(header)
    consumption_data, consumption_rate = get_consumption(data, tr)
    if not consumption_data.empty:
        col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例
        with col1:
            chart_data = consumption_data["charge"].tolist().copy()
            # .4f
            chart_data = [f"{i:.4f}" for i in chart_data]
            options = {
                "xAxis": {
                    "type": "category",
                    "data": consumption_data["time"]
                    .dt.strftime("%Y-%m-%d %H:%M:%S")
                    .tolist(),
                },
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "data": chart_data,
                        "type": "line",
                        "smooth": True  # 使曲线变平滑
                    }
                ],
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {
                        "type": "cross"
                    }
                }
            }
            st_echarts(options=options)
        with col2:
            if len(consumption_data) > 1:
                st.metric("每小时平均消耗", f"{consumption_rate:.2f}")
                st.metric(
                    "相当于每天交",
                    f"¥{consumption_rate * 24 * electricity_fee:.2f}",
                )
                # current / consumption_rate 转换成 时间
                available_time = current / consumption_rate
                try:
                    available_time = timedelta(hours=available_time)
                # OverflowError: cannot convert float infinity to integer
                except OverflowError:
                    available_time = timedelta(days=0)
                if available_time.days > 0:
                    st.metric(
                        "还可以使用",
                        f"{available_time.days} 天",
                    )
                elif available_time.seconds // 3600 > 0:
                    st.metric(
                        "还可以使用",
                        f"{available_time.seconds // 3600} 小时",
                    )
                elif available_time.seconds // 60 > 0:
                    st.metric(
                        "还可以使用",
                        f"{available_time.seconds // 60} 分钟",
                    )
    else:
        st.write("暂无电量数据")


current_chazuo = chazuo_data["charge"].iloc[-1] if not chazuo_data.empty else 0
current_kongtiao = kongtiao_data["charge"].iloc[-1] if not kongtiao_data.empty else 0


# 总剩余电量
st.header("总剩余电量")
if not chazuo_data.empty and not kongtiao_data.empty:
    chazuo_col, kongtiao_col, total_col = st.columns(3)
    total_remaining = current_chazuo + current_kongtiao

    chazuo_col.metric("插座剩余", f"{current_chazuo:.2f}")
    kongtiao_col.metric("空调剩余", f"{current_kongtiao:.2f}")
    total_col.metric(
        "相当于还有",
        f"¥{total_remaining * electricity_fee:.2f}",
    )
else:
    st.write("暂无完整的电量数据")


visualize_consumption_data(chazuo_data, "插座", chazuo_tr, current_chazuo)
visualize_consumption_data(kongtiao_data, "空调", kongtiao_tr, current_kongtiao)
