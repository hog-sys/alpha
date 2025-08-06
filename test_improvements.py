#!/usr/bin/env python3
"""
测试改进后的Crypto Alpha Scout功能
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_config_system():
    """测试配置系统"""
    print("🧪 测试配置系统...")
    
    try:
        from config.settings import settings
        print("✅ 配置系统加载成功")
        
        # 测试配置验证
        try:
            settings.validate()
            print("✅ 配置验证通过")
        except ValueError as e:
            print(f"⚠️  配置验证失败（预期）: {e}")
        
        return True
    except Exception as e:
        print(f"❌ 配置系统测试失败: {e}")
        return False

def test_ml_predictor():
    """测试机器学习预测器"""
    print("\n🧪 测试机器学习预测器...")
    
    try:
        from src.analysis.ml_predictor import MLPredictor
        from config.settings import settings
        
        # 创建预测器实例
        predictor = MLPredictor(settings)
        print("✅ ML预测器创建成功")
        
        # 测试特征提取
        test_opportunity = {
            'price_change_24h': 5.2,
            'volume_change_24h': 12.5,
            'market_cap': 1000000000,
            'volume_24h': 50000000,
            'confidence': 0.7,
            'rsi': 65,
            'macd': 0.02,
            'bollinger_position': 0.6,
            'support_distance': 0.05,
            'resistance_distance': 0.08,
            'social_sentiment': 0.3,
            'news_sentiment': 0.4,
            'whale_activity': 0.2,
            'timestamp': '2024-01-01T12:00:00'
        }
        
        features = predictor._extract_opportunity_features(test_opportunity)
        if features:
            print(f"✅ 特征提取成功，特征数量: {len(features)}")
        else:
            print("❌ 特征提取失败")
            return False
        
        return True
    except Exception as e:
        print(f"❌ ML预测器测试失败: {e}")
        return False

def test_data_collector():
    """测试数据收集器"""
    print("\n🧪 测试数据收集器...")
    
    try:
        from src.analysis.data_collector import DataCollector
        from config.settings import settings
        
        # 创建数据收集器实例
        collector = DataCollector(settings)
        print("✅ 数据收集器创建成功")
        
        # 测试技术指标计算
        import numpy as np
        test_prices = np.array([100, 101, 99, 102, 98, 103, 97, 104, 96, 105])
        
        rsi = collector._calculate_rsi(test_prices)
        print(f"✅ RSI计算成功: {rsi:.2f}")
        
        macd, signal = collector._calculate_macd(test_prices)
        print(f"✅ MACD计算成功: {macd:.4f}, {signal:.4f}")
        
        bb_upper, bb_middle, bb_lower = collector._calculate_bollinger_bands(test_prices)
        print(f"✅ 布林带计算成功: {bb_upper:.2f}, {bb_middle:.2f}, {bb_lower:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ 数据收集器测试失败: {e}")
        return False

def test_main_import():
    """测试主程序导入"""
    print("\n🧪 测试主程序导入...")
    
    try:
        # 测试主要模块导入
        from src.core import ScoutManager, PerformanceOptimizer
        from src.telegram import TelegramBot
        from src.web import DashboardServer
        from src.analysis import MLPredictor
        
        print("✅ 所有核心模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 主程序导入测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试Crypto Alpha Scout改进...\n")
    
    tests = [
        test_config_system,
        test_ml_predictor,
        test_data_collector,
        test_main_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！改进成功！")
    else:
        print("⚠️  部分测试失败，请检查相关模块")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 