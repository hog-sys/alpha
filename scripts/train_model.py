import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import os
import time

# ==============================================================================
# 配置区域
# ==============================================================================

# 读取和保存文件的路径
DATA_FILE = "backtest_opportunities.csv"
MODEL_SAVE_PATH = "ml_models"
MODEL_NAME = "opportunity_classifier.pkl"
SCALER_NAME = "opportunity_scaler.pkl"

# 模型训练参数
TEST_SIZE = 0.2  # 20%的数据用于测试
RANDOM_STATE = 42 # 保证每次划分结果一致

# ==============================================================================
# 特征工程
# ==============================================================================

def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """从原始数据中创建新特征"""
    print("开始进行特征工程...")
    
    # 将时间戳转换为更有用的特征
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek # 星期一=0, 星期日=6
    df['month'] = df['timestamp'].dt.month
    
    # 可以添加更多特征，例如价格差的绝对值等
    df['price_spread'] = df['sell_price'] - df['buy_price']
    
    print("✅ 特征工程完成！")
    return df

# ==============================================================================
# 模型训练核心逻辑
# ==============================================================================

def train_model(df: pd.DataFrame):
    """训练、评估并保存模型"""
    
    # 1. 定义特征 (X) 和目标 (y)
    # 我们选择这些特征来预测一个机会是否会成功
    features = ['buy_price', 'sell_price', 'profit_pct', 'hour', 'day_of_week', 'month', 'price_spread']
    target = 'is_successful'

    X = df[features]
    y = df[target]

    # 2. 划分训练集和测试集
    print(f"将数据划分为训练集和测试集 (测试集比例: {TEST_SIZE})...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y)
    print(f"训练集大小: {len(X_train)}, 测试集大小: {len(X_test)}")

    # 3. 数据标准化
    print("正在对特征数据进行标准化...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 4. 训练模型
    print("开始训练随机森林分类器模型...")
    model = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1) # n_jobs=-1 表示使用所有CPU核心
    model.fit(X_train_scaled, y_train)
    print("✅ 模型训练完成！")

    # 5. 评估模型
    print("\n--- 模型评估报告 ---")
    y_pred = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"模型在测试集上的准确率: {accuracy:.2%}")
    
    print("\n分类报告:")
    print(classification_report(y_test, y_pred))
    
    print("\n混淆矩阵:")
    print(confusion_matrix(y_test, y_pred))
    
    # 6. 保存模型和标准化器
    if not os.path.exists(MODEL_SAVE_PATH):
        os.makedirs(MODEL_SAVE_PATH)
        
    model_path = os.path.join(MODEL_SAVE_PATH, MODEL_NAME)
    scaler_path = os.path.join(MODEL_SAVE_PATH, SCALER_NAME)
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    print(f"\n✅ 模型成功保存到: {model_path}")
    print(f"✅ 标准化器成功保存到: {scaler_path}")

# ==============================================================================
# 主程序
# ==============================================================================

if __name__ == "__main__":
    start_time = time.time()

    if not os.path.exists(DATA_FILE):
        print(f"错误: 找不到数据文件 '{DATA_FILE}'。请先运行回测脚本。")
    else:
        # 1. 加载数据
        print(f"正在从 {DATA_FILE} 加载数据...")
        data_df = pd.read_csv(DATA_FILE)
        
        # 2. 特征工程
        data_df = feature_engineering(data_df)
        
        # 3. 训练模型
        train_model(data_df)

    end_time = time.time()
    print(f"\n总耗时: {end_time - start_time:.2f} 秒")
