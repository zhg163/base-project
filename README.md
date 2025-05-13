# AI项目

基于FastAPI的AI应用项目。

## 功能特点

- 集成大语言模型服务
- 支持检索增强生成(RAG)
- 文档处理与向量索引
- 异步任务处理

## 快速开始

### 环境准备

1. 克隆项目
```bash
git clone <repository-url>
cd ai_project

# 创建缓存目录
mkdir -p ~/.pyenv/cache

# 通过国内镜像下载源码包（任选一个镜像源）
# 镜像源1：淘宝npm镜像
wget https://npmmirror.com/mirrors/python/3.11.6/Python-3.11.6.tar.xz -P ~/.pyenv/cache/

# 镜像源2：华为云镜像
# wget https://mirrors.huaweicloud.com/python/3.11.6/Python-3.11.6.tar.xz -P ~/.pyenv/cache/

PYTHON_BUILD_MIRROR_URL="https://mirrors.huaweicloud.com/python"   /home/pyenv/bin/pyenv install 3.11.6
# 手动安装
pyenv install 3.11.6

pyenv install 3.11.6
# 切换到 Python 3.11.6
pyenv shell 3.11.6

/home/pyenv/bin/pyenv local 3.11.6

# 创建虚拟环境
python -m venv venv

pyenv virtualenv 3.11.6 .venv

pyenv activate venv

# 激活虚拟环境
# 在 macOS/Linux 上
source venv/bin/activate

# 验证 Python 版本
python --version

# 使用完整路径创建虚拟环境
~/.pyenv/versions/3.11.6/bin/python -m venv venv

# 激活虚拟环境
source venv/bin/activate

pip install -r requirements.txt
# 或者
pip install -e .

deactivate

# 查看已安装的所有包并更新requirements.txt
pip freeze > complete_requirements.txt


nohup uvicorn main:app --reload --host 0.0.0.0 --port 8001





apt update
apt install -y pkg-config libicu-dev

