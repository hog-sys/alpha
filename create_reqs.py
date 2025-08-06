<<<<<<< HEAD
# create_reqs.py
# 运行此脚本以生成一个格式正确的 requirements.txt 文件。

requirements_content = """# Web and Server
fastapi
uvicorn
gunicorn

# Data and Async
aio-pika
asyncpg
sqlalchemy
numpy
pandas

# Telegram Bot
python-telegram-bot

# Blockchain and Crypto
web3
ccxt

# Machine Learning
scikit-learn
joblib

# System
psutil

# Windows specific (optional, for local dev)
pywin32; sys_platform == 'win32'
"""

try:
    # 'w'模式会覆盖已有的文件，确保我们从一个干净的文件开始
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        f.write(requirements_content)
    print("✅ 'requirements.txt' 文件已成功生成！")
    print("   现在请运行: python -m pip install -r requirements.txt")
except Exception as e:
    print(f"❌ 生成文件时出错: {e}")

=======
# create_reqs.py
# 运行此脚本以生成一个格式正确的 requirements.txt 文件。

requirements_content = """# Web and Server
fastapi
uvicorn
gunicorn

# Data and Async
aio-pika
asyncpg
sqlalchemy
numpy
pandas

# Telegram Bot
python-telegram-bot

# Blockchain and Crypto
web3
ccxt

# Machine Learning
scikit-learn
joblib

# System
psutil

# Windows specific (optional, for local dev)
pywin32; sys_platform == 'win32'
"""

try:
    # 'w'模式会覆盖已有的文件，确保我们从一个干净的文件开始
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        f.write(requirements_content)
    print("✅ 'requirements.txt' 文件已成功生成！")
    print("   现在请运行: python -m pip install -r requirements.txt")
except Exception as e:
    print(f"❌ 生成文件时出错: {e}")

>>>>>>> e5cf058720e42a15be9be28747f9f02b5d15a885
