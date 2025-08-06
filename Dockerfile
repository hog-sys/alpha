<<<<<<< HEAD
# Dockerfile for the Crypto Alpha Scout application

# 1. 使用官方的Python镜像作为基础
FROM python:3.12-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖文件并安装
#    这样做可以利用Docker的层缓存，只有在requirements.txt改变时才重新安装
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# 4. 复制项目的所有源代码到工作目录
COPY . .

# 5. 定义容器启动时要执行的命令
CMD ["python", "start.py"]
=======
# Dockerfile for the Crypto Alpha Scout application

# 1. 使用官方的Python镜像作为基础
FROM python:3.12-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖文件并安装
#    这样做可以利用Docker的层缓存，只有在requirements.txt改变时才重新安装
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# 4. 复制项目的所有源代码到工作目录
COPY . .

# 5. 定义容器启动时要执行的命令
CMD ["python", "start.py"]
>>>>>>> e5cf058720e42a15be9be28747f9f02b5d15a885
