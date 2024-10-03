import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from init import ChaZuo, KongTiao, YuE, electricity_fee
from toml import load
import os
from streamlit_echarts import st_echarts
from pyecharts.charts import Line, Grid
from pyecharts import options as opts

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")

st.set_page_config(
    page_title=config["visualize"]["title"],
    page_icon="⚡",
)

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

global current_chazuo
global current_kongtiao
global current_yue

update_time = st.empty()


def fetch_data():
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


if col2.button("获取最新数据"):
    fetch_data()


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


# 获取插座和空调数据
chazuo_data, chazuo_tr = get_data(ChaZuo, time_range)
kongtiao_data, kongtiao_tr = get_data(KongTiao, time_range)
yue_data, yue_tr = get_data(YuE, time_range, is_YuE=True)


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
    consumption_data_rate["charge"] = consumption_data_rate["charge"] / tmp_time * interval
    consumption_data_rate = consumption_data_rate.fillna(0)
    consumption_data_rate = consumption_data_rate[consumption_data_rate["charge"] > 0]
    # print(consumption_data_rate)

    # print(consumption_time)
    if consumption_time.total_seconds() > 0:
        consumption_rate = consumption / (consumption_time / timedelta(hours=1))
    else:
        consumption_rate = 0

    return consumption_data_rate, consumption_rate


def visualize_consumption_data(data, header, tr, current):
    consumption_data, consumption_rate = get_consumption(data, tr)

    if consumption_data is not None and not consumption_data.empty:
        header_col, toggle_col = st.columns([3, 1])
        with header_col:
            st.header(header)
            update_time.write(f"最后更新时间：{data['time'].iloc[-1]}")
        with toggle_col:
            on = st.toggle("显示变化量", key=header + "_toggle")
        col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例

        with col1:
            chart_data = {
                "consumption": consumption_data["charge"].tolist().copy(),
                "data": data["charge"].tolist().copy(),
                "consumption_time": consumption_data["time"]
                .dt.strftime("%Y-%m-%d %H:%M:%S")
                .tolist(),
                "data_time": data["time"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            }
            option = {
                "title": {"text": header},
                "xAxis": {"type": "time"},
                "yAxis": {"type": "value", "scale": True},
                "series": [
                    {
                        "data": list(zip(chart_data["data_time"], chart_data["data"])),
                        "type": "line",
                        "name": "电量",
                        "smooth": True,
                        "tooltip": {
                            "show": True,
                        }
                    },
                    {
                        "data": list(zip(chart_data["consumption_time"], chart_data["consumption"])),
                        "type": "line",
                        "name": "耗电量",
                        "smooth": True,
                        "tooltip": {
                            "show": True,
                        }
                    },
                ],
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "cross"},
                },
                "dataZoom": [
                    {"type": "inside", "xAxisIndex": [0], "start": 100-12.5, "end": 100}
                ],
                "legend": {
                    "selected": {"耗电量": False} if not on else {"电量": False},
                    "show": False,
                },
            }
            st_echarts(option, key=header + "_chart")
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

    elif not data.empty:
        st.header(header)
        update_time.write(f"最后更新时间：{data['time'].iloc[-1]}")
        st.write(f"{time_range}内设备没有消耗电量。")

    else:
        st.write("暂无电量数据，尝试获取最新数据...")
        fetch_data()

    #     st.write("暂无电量数据，尝试获取最新数据...")
    #     fetch_data()


# 总剩余
st.header("总剩余")

if not chazuo_data.empty and not kongtiao_data.empty:
    current_chazuo = chazuo_data["charge"].iloc[-1] if not chazuo_data.empty else 0
    current_kongtiao = (
        kongtiao_data["charge"].iloc[-1] if not kongtiao_data.empty else 0
    )
    current_yue = yue_data["balance"].iloc[-1] if not yue_data.empty else 0

    chazuo_col, kongtiao_col, total_col, yue_col = st.columns(4)
    total_remaining = current_chazuo + current_kongtiao

    chazuo_col.metric("插座剩余", f"{current_chazuo:.2f}")
    kongtiao_col.metric("空调剩余", f"{current_kongtiao:.2f}")
    total_col.metric(
        "相当于还有",
        f"¥{total_remaining * electricity_fee:.2f}",
    )
    yue_col.metric("校园卡余额", f"¥{current_yue:.2f}")
else:
    st.write("暂无完整的电量数据")


visualize_consumption_data(chazuo_data, "插座", chazuo_tr, current_chazuo)
visualize_consumption_data(kongtiao_data, "空调", kongtiao_tr, current_kongtiao)

footer = """
<style>
    footer {
        text-align: center;
        padding: 10px;
    }
</style>

<footer>
Powered by <a href="https://streamlit.io/">Streamlit</a>. Open source on <a href="https://github.com/hongjr03/OUC-Electricity-Monitor">GitHub</a>.
</footer>
"""

st.markdown(footer, unsafe_allow_html=True)
