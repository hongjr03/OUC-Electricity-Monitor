#!/bin/bash

# Install Python 3.10 if python3.10 is not found
if ! command -v python3.10 &> /dev/null; then
    echo "Python 3.10 is not found. Installing Python 3.10..."
    {
        sudo apt update
        sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt update
        sudo apt install -y python3.10 python3.10-venv
    } &> /dev/null
    echo "Python 3.10 has been installed."
    echo ""
    echo ""
fi

# Create a virtual environment
echo "Creating a virtual environment..."
python3.10 -m venv .venv
source .venv/bin/activate
echo "Virtual environment has been created."
echo ""
echo ""

# Install required packages
echo "Installing required packages..."
cat requirements.txt
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple &> /dev/null
echo "Required packages have been installed."
echo ""
echo ""

# Initialize the database
echo "Initializing the database..."
python init.py
if [ $? -ne 0 ]; then
    echo "Database initialization failed. Please recheck the configuration. Exiting..."
    exit 1
fi
echo "Database has been initialized."
echo ""
echo ""

# Test if get.py works
echo "Testing get.py..."
python get.py
# 如果 get.py 运行失败，exit(1)
if [ $? -ne 0 ]; then
    echo "get.py failed. Please recheck the configuration. Exiting..."
    exit 1
fi
echo "get.py works."
echo ""
echo ""

# 执行 get_cronjob() 函数，获得 crontab 时间表 ("*/5 * * * *")
echo "Setting up crontab..."
CRONTAB=$(python -c "from utils import get_crontab; print(get_crontab())")
CRONTAB_COMMAND="cd $(pwd) && .venv/bin/python get.py"
echo "${CRONTAB} ${CRONTAB_COMMAND}"
# 检查 crontab 是否已有该时间表，如果没有则添加
(crontab -l 2>/dev/null; echo "${CRONTAB} ${CRONTAB_COMMAND}") | sort - | uniq - | crontab -
echo "Crontab has been set up."
echo ""
echo ""

# 安装 Streamlit 服务
echo "Setting up Streamlit service..."
SERVICE_NAME="streamlit"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
STREAMLIT_PATH=$(which streamlit)
SCRIPT_PATH="$(pwd)/visualize.py"
WORKING_DIR="$(pwd)"
USER=$(whoami)

PORT=$(python -c "from utils import get_visualize_port; print(get_visualize_port())")

# 创建 systemd 服务文件
sudo bash -c "cat > ${SERVICE_FILE} <<EOF
[Unit]
Description=Streamlit Service
After=network.target

[Service]
ExecStart=${STREAMLIT_PATH} run ${SCRIPT_PATH} --server.port ${PORT}
WorkingDirectory=${WORKING_DIR}
Restart=always
User=${USER}
Environment='PATH=$(dirname ${STREAMLIT_PATH})'

[Install]
WantedBy=multi-user.target
EOF"

# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动并启用服务
sudo systemctl start ${SERVICE_NAME}.service
sudo systemctl enable ${SERVICE_NAME}.service

echo "Streamlit service has been set up and started."
echo ""
echo ""
echo "All done!"
echo "你可以通过以下命令查看 Streamlit 服务的状态："
echo "sudo systemctl status streamlit.service | 查看服务状态"

echo "你可以通过以下命令重启 Streamlit 服务："
echo "sudo systemctl restart streamlit.service | 重启服务"

echo "你可以通过以下命令卸载 Streamlit 服务："
echo "sudo systemctl stop streamlit.service | 停止服务"
echo "sudo systemctl disable streamlit.service | 禁用服务"