#!/bin/bash

# Install Python 3.10
echo "Installing Python 3.10..."
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.10 python3.10-venv
echo "Python 3.10 has been installed."
echo ""
echo ""

# Create a virtual environment
echo "Creating a virtual environment..."
python3.10 -m venv .venv
source .venv/bin/activate
echo "Virtual environment has been created."
echo ""
echo ""

# Install required packages
echo "Installing required packages..."
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "Required packages have been installed."
echo ""
echo ""

# Initialize the database
echo "Initializing the database..."
python init.py
echo "Database has been initialized."
echo ""
echo ""

# Test if get.py works
echo "Testing get.py..."
python get.py
echo "get.py works."
echo ""
echo ""

# 执行 get_cronjob() 函数，获得 crontab 时间表 ("*/5 * * * *")
echo "Setting up crontab..."
CRONTAB=$(python -c "from init import get_crontab; print(get_crontab())")
CRONTAB_COMMAND="cd $(pwd) && .venv/bin/python get.py"

echo "${CRONTAB} ${CRONTAB_COMMAND}"

# 将 crontab 时间表写入文件
(crontab -l 2>/dev/null; echo "${CRONTAB} ${CRONTAB_COMMAND}") | crontab -
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

# 创建 systemd 服务文件
sudo bash -c "cat > ${SERVICE_FILE} <<EOF
[Unit]
Description=Streamlit Service
After=network.target

[Service]
ExecStart=${STREAMLIT_PATH} run ${SCRIPT_PATH}
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
echo "Enjoy your Streamlit app at http://localhost:8501"
echo ""
echo ""
echo "Setup has been completed."
echo "To check the status of the Streamlit service, run 'sudo systemctl status streamlit.service'."
echo "To stop the Streamlit service, run 'sudo systemctl stop streamlit.service'."