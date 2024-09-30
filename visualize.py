import streamlit as st
import pandas as pd
import plotly.express as px
from peewee import *
from datetime import datetime, timedelta
from init import ChaZuo, KongTiao, electricity_fee
from toml import load

config = load("config.toml")
if "visualize" not in config or "title" not in config["visualize"]:
    st.error("请先运行 init.py 文件")
    st.stop()
# Streamlit 应用
st.title(config["visualize"]["title"])

# 时间范围选择
time_range = st.selectbox(
    "选择时间范围", ("最近 24 小时", "最近 7 天", "最近 30 天", "全部")
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

    return df


# 获取插座和空调数据
chazuo_data = get_data(ChaZuo, time_range)
kongtiao_data = get_data(KongTiao, time_range)


def get_consumption_rate(data):
    consumption_rate = 0
    consumption = 0
    consumption_time = 0
    for i in range(1, len(data)):
        if data["charge"].iloc[i] < data["charge"].iloc[i - 1]:
            consumption += float(data["charge"].iloc[i - 1]) - float(
                data["charge"].iloc[i]
            )
            consumption_time += (
                data["time"].iloc[i] - data["time"].iloc[i - 1]
            ).total_seconds()
    consumption_rate = consumption / consumption_time * 3600
    return consumption_rate


# 展示插座剩余电量
st.header("插座剩余电量")
st.write(config["student"]["equipments"]["chazuo"]["roomName"])
if not chazuo_data.empty:
    col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例
    with col1:
        fig_chazuo = px.line(chazuo_data, x="time", y="charge")
        st.plotly_chart(fig_chazuo, use_container_width=True)
    with col2:
        current_chazuo = chazuo_data["charge"].iloc[-1]
        st.metric("当前插座剩余电量", f"{current_chazuo:.2f}")
        if len(chazuo_data) > 1:
            chazuo_consumption_rate = get_consumption_rate(chazuo_data)
            st.metric("插座每小时平均消耗", f"{chazuo_consumption_rate:.2f}")
            st.metric(
                "相当于每天交",
                f"¥{chazuo_consumption_rate * 24 * electricity_fee:.2f}",
            )
else:
    st.write("暂无插座电量数据")

# 展示空调剩余电量
st.header("空调剩余电量")
if not kongtiao_data.empty:
    col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例
    with col1:
        fig_kongtiao = px.line(kongtiao_data, x="time", y="charge")
        st.plotly_chart(fig_kongtiao, use_container_width=True)
    with col2:
        current_kongtiao = kongtiao_data["charge"].iloc[-1]
        st.metric("当前空调剩余电量", f"{current_kongtiao:.2f}")
        if len(kongtiao_data) > 1:
            kongtiao_consumption_rate = get_consumption_rate(kongtiao_data)
            st.metric("空调每小时平均消耗", f"{kongtiao_consumption_rate:.2f}")
            # 换算成每天交的电费
            st.metric(
                "相当于每天交",
                f"¥{kongtiao_consumption_rate * 24 * electricity_fee:.2f}",
            )

else:
    st.write("暂无空调电量数据")

# 总剩余电量
st.header("总剩余电量")
if not chazuo_data.empty and not kongtiao_data.empty:
    col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例
    with col1:
        total_remaining = current_chazuo + current_kongtiao
        # 剩余电量比例饼图
        pie_data = pd.DataFrame(
            {"类型": ["插座", "空调"], "剩余电量": [current_chazuo, current_kongtiao]}
        )
        fig_pie = px.pie(pie_data, values="剩余电量", names="类型")
        st.plotly_chart(fig_pie, use_container_width=True)
    with col2:
        st.metric("插座剩余", f"{current_chazuo:.2f}")
        st.metric("空调剩余", f"{current_kongtiao:.2f}")
        st.metric(
            "相当于还有",
            f"¥{total_remaining * electricity_fee:.2f}",
        )
else:
    st.write("暂无完整的电量数据")
