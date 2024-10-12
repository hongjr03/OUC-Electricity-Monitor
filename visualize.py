import streamlit as st
from datetime import datetime, timedelta
from toml import load
import os

from models import ChaZuo, KongTiao, YuE
from utils import get_consumption, get_data

script_dir = os.path.dirname(os.path.abspath(__file__))
config = load(script_dir + "/config.toml")

electricity_fee = config["student"]["electricity_fee"]

st.set_page_config(
    page_title=config["visualize"]["title"],
    page_icon=config["visualize"]["icon"],
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

# 获取插座和空调数据
chazuo_data, chazuo_tr = get_data(ChaZuo, time_range)
kongtiao_data, kongtiao_tr = get_data(KongTiao, time_range)
yue_data, yue_tr = get_data(YuE, time_range, is_YuE=True)


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


def visualize_consumption_data(data, header, tr, current):
    consumption_data, consumption_rate = get_consumption(data, tr)

    if consumption_data is not None and not consumption_data.empty:
        header_col, toggle_col = st.columns([3, 1], vertical_alignment="bottom")
        with header_col:
            st.header(header)
            update_time.write(f"最后更新时间：{data['time'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')}")
        with toggle_col:
            on = st.toggle("显示变化量", key=header + "_toggle")
        col1, col2 = st.columns([3, 1])  # 3:1 的宽度比例

        with col1:
            import plotly.graph_objects as go

            fig = go.Figure()

            if on:
                fig.add_trace(
                    go.Scatter(
                        x=consumption_data["time"],
                        y=consumption_data["charge"],
                        mode="lines",
                        name="耗电量",
                        line=dict(shape="spline"),
                    )
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=data["time"],
                        y=data["charge"],
                        mode="lines",
                        name="电量",
                        line=dict(shape="spline"),
                    )
                )

            fig.update_layout(
                xaxis_title="时间",
                yaxis_title="电量" if not on else "耗电量",
                legend_title="图例",
                hovermode="x unified",
            )

            st.plotly_chart(fig, use_container_width=True)
        with col2:
            if len(consumption_data) > 1:
                st.metric("每小时平均消耗", f"{consumption_rate:.2f}")
                st.metric(
                    "相当于每天交",
                    f"¥{consumption_rate * 24 * electricity_fee:.2f}",
                )
                available_time = current / consumption_rate
                try:
                    available_time = timedelta(hours=available_time)
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
        update_time.write(f"最后更新时间：{data['time'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')}")
        st.write(f"{time_range}内设备没有消耗电量。")

    else:
        st.write("暂无电量数据，尝试获取最新数据...")
        fetch_data()

    #     st.write("暂无电量数据，尝试获取最新数据...")
    #     fetch_data()

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
