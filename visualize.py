import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from init import ChaZuo, KongTiao, electricity_fee
from toml import load
import os
import altair as alt

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
    with st.spinner('获取数据...'):
        from get import get_latest_data

        data = get_latest_data()
        if data["status"] == 1:
            current_chazuo = data["chazuo"]
            current_kongtiao = data["kongtiao"]
            st.toast("获取数据成功，已更新到数据库与页面！", icon="🔥")
        else:
            st.toast("获取数据失败，数据为 0，请检查 config 配置并重新初始化。", icon="🚨")


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


def get_consumption_rate(data, tr):

    consumption = 0
    consumption_time = tr.total_seconds() / 3600

    for i in range(1, len(data)):
        if data["charge"].iloc[i] < data["charge"].iloc[i - 1]:
            consumption += float(data["charge"].iloc[i - 1]) - float(
                data["charge"].iloc[i]
            )

    if consumption_time > 0:
        consumption_rate = consumption / consumption_time
    else:
        consumption_rate = 0

    return consumption_rate


def get_consumption(data, header, tr):
    st.header(header)
    if not data.empty:
        col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例
        with col1:
            y_min = data["charge"].min()
            y_max = data["charge"].max()
            chart = alt.Chart(data).mark_line().encode(
                x='time:T',
                y=alt.Y('charge:Q', scale=alt.Scale(domain=[y_min, y_max]))
            ).properties(
                width='container',
                height=300
            )
            st.altair_chart(chart, use_container_width=True)
        with col2:
            current = data["charge"].iloc[-1]
            st.metric("当前剩余电量", f"{current:.2f}")
            if len(data) > 1:
                consumption_rate = get_consumption_rate(data, tr)
                st.metric("每小时平均消耗", f"{consumption_rate:.2f}")
                st.metric(
                    "相当于每天交",
                    f"¥{consumption_rate * 24 * electricity_fee:.2f}",
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


get_consumption(chazuo_data, "插座", chazuo_tr)
get_consumption(kongtiao_data, "空调", kongtiao_tr)