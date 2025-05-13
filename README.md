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







### **1. 检查网络连通性**
#### 命令：
```bash
ping -c 4 github.com
```
- **若成功**：显示类似 `64 bytes from github.com (IP地址)`，说明网络连通。
- **若失败**：提示 `Unknown host` 或超时，可能是 DNS 或网络问题。

---

### **2. 检查 DNS 解析**
#### 命令：
```bash
nslookup github.com  # 或使用 dig github.com
```
- **正常情况**：返回 GitHub 的 IP 地址（如 `140.82.121.3`）。
- **异常情况**：无响应或报错，说明 DNS 解析失败。

#### 解决方案：
- **更换 DNS 服务器**（如 Google 的 `8.8.8.8`）：
  ```bash
  echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
  ```
- 或在网络设置中手动配置 DNS。

---

### **3. 检查 Hosts 文件**
#### 命令：
```bash
sudo cat /etc/hosts  # Linux/macOS
```
- 检查是否有异常条目（如将 `github.com` 指向错误 IP）。
- **修复**：用 `sudo vim /etc/hosts` 删除错误行。

---

### **4. 检查代理设置**
#### 查看 Git 是否配置了代理：
```bash
git config --global --get http.proxy
```
- **如果有代理**：尝试关闭代理：
  ```bash
  git config --global --unset http.proxy
  ```
- **若使用全局代理**（如 VPN/Clash），确保代理正常运行。

---

### **5. 检查防火墙/网络限制**
- **临时关闭防火墙**（Linux）：
  ```bash
  sudo ufw disable  # Ubuntu
  ```
- **公司/校园网**：可能限制访问 GitHub，尝试切换网络（如手机热点）。

---

### **6. 检查 GitHub 服务状态**
- 访问 [GitHub Status](https://www.githubstatus.com/) 确认服务正常。
- 尝试浏览器打开 `https://github.com`，若失败则可能是网络问题。

---

### **7. 检查 SSL 证书（可选）**
#### 命令：
```bash
curl -vI https://github.com
```
- 若报错 `SSL certificate problem`，尝试更新 CA 证书：
  ```bash
  sudo apt-get update && sudo apt-get install ca-certificates  # Debian/Ubuntu
  ```

---

### **8. 最终验证**
修复后，再次测试：
```bash
git pull
```
或直接测试连接：
```bash
curl -v https://github.com
```

---

### **总结命令**
```bash
# 1. 检查网络
ping -c 4 github.com

# 2. 检查 DNS
nslookup github.com

# 3. 检查 Hosts
cat /etc/hosts

# 4. 检查代理
git config --global --get http.proxy

# 5. 检查防火墙/网络限制
curl -v https://github.com
```

根据结果逐步排查，通常可解决问题！