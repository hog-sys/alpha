# src/analysis/ml_predictor_enhanced.py
"""
增强版机器学习预测器 - 根据PDF建议集成SHAP可解释性
实现LSTM+XGBoost混合模型
"""
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import joblib
from pathlib import Path
import logging

# 机器学习库
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_recall_curve, roc_auc_score
import xgboost as xgb

# 深度学习
import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input, concatenate
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# SHAP可解释性
import shap

logger = logging.getLogger(__name__)

class EnhancedMLPredictor:
    """
    增强版ML预测器 - 实现PDF中建议的LSTM+XGBoost混合架构
    """
    
    def __init__(self, config):
        self.config = config
        self.models = {}
        self.scalers = {}
        self.shap_explainers = {}
        
        # 模型路径
        self.model_path = Path(config.get('ML_MODEL_PATH', 'ml_models'))
        self.model_path.mkdir(exist_ok=True)
        
        # 模型参数
        self.sequence_length = 60  # LSTM的时间序列长度
        self.prediction_horizon = 5  # 预测未来5分钟
        
        # 特征配置
        self.time_series_features = [
            'price', 'volume', 'bid', 'ask', 'spread',
            'rsi', 'macd', 'bollinger_upper', 'bollinger_lower'
        ]
        
        self.cross_sectional_features = [
            'sentiment_score', 'mention_count', 'dev_activity_score',
            'whale_movement_count', 'exchange_inflow', 'exchange_outflow',
            'gas_price', 'market_cap_rank', 'volume_rank'
        ]
        
        self.feature_importance_history = []
    
    async def initialize(self):
        """初始化预测器"""
        logger.info("初始化增强版ML预测器...")
        
        # 加载已有模型
        await self._load_models()
        
        # 初始化SHAP解释器
        self._initialize_shap_explainers()
        
        # 启动定期重训练
        asyncio.create_task(self._periodic_retrain())
        
        logger.info("✅ ML预测器初始化完成")
    
    def _build_lstm_model(self, sequence_shape: Tuple) -> Model:
        """
        构建LSTM模型用于时间序列特征提取
        """
        inputs = Input(shape=sequence_shape)
        
        # LSTM层
        x = LSTM(128, return_sequences=True, dropout=0.2)(inputs)
        x = LSTM(64, return_sequences=True, dropout=0.2)(x)
        x = LSTM(32, dropout=0.2)(x)
        
        # 输出时序特征向量
        time_features = Dense(16, activation='relu', name='time_features')(x)
        
        model = Model(inputs=inputs, outputs=time_features)
        return model
    
    def _build_hybrid_model(
        self, 
        sequence_shape: Tuple,
        cross_sectional_shape: Tuple
    ) -> Model:
        """
        构建LSTM+XGBoost混合模型
        这里我们用神经网络模拟混合架构
        """
        # LSTM输入
        sequence_input = Input(shape=sequence_shape, name='sequence_input')
        
        # LSTM处理
        lstm_x = LSTM(128, return_sequences=True, dropout=0.2)(sequence_input)
        lstm_x = LSTM(64, dropout=0.2)(lstm_x)
        lstm_features = Dense(32, activation='relu')(lstm_x)
        
        # 横截面特征输入
        cross_input = Input(shape=cross_sectional_shape, name='cross_input')
        cross_features = Dense(32, activation='relu')(cross_input)
        cross_features = Dropout(0.3)(cross_features)
        
        # 合并特征
        combined = concatenate([lstm_features, cross_features])
        
        # 深层处理
        x = Dense(64, activation='relu')(combined)
        x = Dropout(0.3)(x)
        x = Dense(32, activation='relu')(x)
        x = Dropout(0.2)(x)
        
        # 输出层
        output = Dense(1, activation='sigmoid', name='opportunity_score')(x)
        
        model = Model(
            inputs=[sequence_input, cross_input],
            outputs=output
        )
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC()]
        )
        
        return model
    
    def _train_xgboost_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> xgb.XGBClassifier:
        """
        训练XGBoost模型
        """
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            objective='binary:logistic',
            use_label_encoder=False,
            eval_metric='auc',
            random_state=42
        )
        
        # 训练时使用早停
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=10,
            verbose=False
        )
        
        return model
    
    async def predict_opportunity_with_explanation(
        self,
        opportunity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        预测机会质量并提供SHAP解释
        """
        try:
            # 提取特征
            features = await self._extract_features(opportunity)
            
            if features is None:
                return {
                    'prediction_score': opportunity.get('confidence', 0.5),
                    'shap_values': {},
                    'feature_importance': {},
                    'explanation': "特征提取失败"
                }
            
            # 使用混合模型预测
            if 'hybrid_model' in self.models:
                # 分离时序和横截面特征
                sequence_features = features['sequence']
                cross_features = features['cross_sectional']
                
                # 标准化
                if 'sequence_scaler' in self.scalers:
                    sequence_features = self.scalers['sequence_scaler'].transform(sequence_features)
                if 'cross_scaler' in self.scalers:
                    cross_features = self.scalers['cross_scaler'].transform(cross_features)
                
                # 预测
                prediction = self.models['hybrid_model'].predict(
                    [sequence_features, cross_features]
                )[0][0]
            else:
                # 回退到简单模型
                prediction = opportunity.get('confidence', 0.5)
            
            # 使用XGBoost生成SHAP值
            shap_values = {}
            feature_importance = {}
            
            if 'xgboost_model' in self.models and 'xgboost_explainer' in self.shap_explainers:
                # 合并所有特征用于XGBoost
                all_features = np.concatenate([
                    features['sequence'].flatten(),
                    features['cross_sectional']
                ])
                
                # 获取SHAP值
                shap_values_array = self.shap_explainers['xgboost_explainer'].shap_values(
                    all_features.reshape(1, -1)
                )[0]
                
                # 映射到特征名称
                feature_names = self._get_all_feature_names()
                shap_values = dict(zip(feature_names, shap_values_array))
                
                # 计算特征重要性（绝对SHAP值）
                feature_importance = {
                    name: abs(value) 
                    for name, value in shap_values.items()
                }
                
                # 排序并获取top特征
                top_features = sorted(
                    feature_importance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            
            # 生成人类可读的解释
            explanation = self._generate_explanation(
                prediction,
                shap_values,
                opportunity
            )
            
            return {
                'prediction_score': float(prediction),
                'original_confidence': opportunity.get('confidence', 0),
                'shap_values': shap_values,
                'feature_importance': dict(top_features) if 'top_features' in locals() else {},
                'explanation': explanation,
                'model_confidence': self._calculate_model_confidence(prediction)
            }
            
        except Exception as e:
            logger.error(f"预测失败: {e}", exc_info=True)
            return {
                'prediction_score': opportunity.get('confidence', 0.5),
                'shap_values': {},
                'feature_importance': {},
                'explanation': f"预测错误: {str(e)}"
            }
    
    def _initialize_shap_explainers(self):
        """初始化SHAP解释器"""
        try:
            if 'xgboost_model' in self.models:
                # 创建背景数据集（用于SHAP）
                # 这里应该使用真实的训练数据子集
                background_data = np.random.randn(100, 100)  # 示例
                
                self.shap_explainers['xgboost_explainer'] = shap.Explainer(
                    self.models['xgboost_model'],
                    background_data
                )
                logger.info("✅ SHAP解释器初始化完成")
        except Exception as e:
            logger.error(f"初始化SHAP失败: {e}")
    
    def _generate_explanation(
        self,
        prediction: float,
        shap_values: Dict[str, float],
        opportunity: Dict
    ) -> str:
        """
        生成人类可读的预测解释
        """
        explanation_parts = []
        
        # 预测强度
        if prediction > 0.8:
            explanation_parts.append("🟢 强烈推荐：模型高度确信这是一个优质机会")
        elif prediction > 0.6:
            explanation_parts.append("🟡 谨慎推荐：模型认为这可能是一个不错的机会")
        else:
            explanation_parts.append("🔴 不推荐：模型认为风险较高")
        
        # 主要驱动因素
        if shap_values:
            sorted_shap = sorted(
                shap_values.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:3]
            
            positive_factors = []
            negative_factors = []
            
            for feature, value in sorted_shap:
                if value > 0:
                    positive_factors.append(self._translate_feature_name(feature))
                else:
                    negative_factors.append(self._translate_feature_name(feature))
            
            if positive_factors:
                explanation_parts.append(f"✅ 积极因素: {', '.join(positive_factors)}")
            
            if negative_factors:
                explanation_parts.append(f"⚠️ 风险因素: {', '.join(negative_factors)}")
        
        # 信号类型特定解释
        signal_type = opportunity.get('signal_type', '')
        if signal_type == 'arbitrage':
            profit = opportunity.get('data', {}).get('profit_pct', 0)
            explanation_parts.append(f"💰 套利利润: {profit:.2f}%")
        elif signal_type == 'sentiment_shift':
            sentiment_delta = opportunity.get('data', {}).get('sentiment_delta', 0)
            explanation_parts.append(f"😊 情绪变化: {sentiment_delta:+.2f}")
        
        return " | ".join(explanation_parts)
    
    def _translate_feature_name(self, feature: str) -> str:
        """将技术特征名转换为易懂的描述"""
        translations = {
            'price': '价格走势',
            'volume': '成交量',
            'sentiment_score': '市场情绪',
            'dev_activity_score': '开发活跃度',
            'whale_movement_count': '巨鲸活动',
            'rsi': 'RSI指标',
            'macd': 'MACD指标',
            'spread': '买卖价差',
            'gas_price': 'Gas费用',
            'mention_count': '社交提及量'
        }
        
        for key, value in translations.items():
            if key in feature.lower():
                return value
        
        return feature
    
    def _calculate_model_confidence(self, prediction: float) -> float:
        """
        计算模型置信度
        极端预测值（接近0或1）表示高置信度
        """
        distance_from_middle = abs(prediction - 0.5)
        confidence = distance_from_middle * 2
        return min(confidence, 1.0)
    
    async def _extract_features(self, opportunity: Dict) -> Optional[Dict[str, np.ndarray]]:
        """
        提取混合模型所需的特征
        """
        try:
            # 这里应该从数据库获取历史数据
            # 为了演示，我们生成示例数据
            
            # 时序特征（LSTM输入）
            sequence_features = np.random.randn(
                1, 
                self.sequence_length,
                len(self.time_series_features)
            )
            
            # 横截面特征（当前时刻的特征）
            cross_features = np.random.randn(
                1,
                len(self.cross_sectional_features)
            )
            
            return {
                'sequence': sequence_features,
                'cross_sectional': cross_features
            }
            
        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            return None
    
    def _get_all_feature_names(self) -> List[str]:
        """获取所有特征名称"""
        # 时序特征展平
        sequence_names = []
        for i in range(self.sequence_length):
            for feature in self.time_series_features:
                sequence_names.append(f"{feature}_t-{i}")
        
        # 加上横截面特征
        return sequence_names + self.cross_sectional_features
    
    async def train_hybrid_model(
        self,
        training_data: pd.DataFrame
    ):
        """
        训练混合模型
        """
        logger.info("开始训练LSTM+XGBoost混合模型...")
        
        try:
            # 准备数据
            X_sequence, X_cross, y = await self._prepare_training_data(training_data)
            
            # 时间序列分割（不能用随机分割）
            tscv = TimeSeriesSplit(n_splits=5)
            
            best_score = 0
            best_model = None
            
            for train_idx, val_idx in tscv.split(X_sequence):
                X_seq_train, X_seq_val = X_sequence[train_idx], X_sequence[val_idx]
                X_cross_train, X_cross_val = X_cross[train_idx], X_cross[val_idx]
                y_train, y_val = y[train_idx], y[val_idx]
                
                # 训练混合模型
                model = self._build_hybrid_model(
                    sequence_shape=(self.sequence_length, len(self.time_series_features)),
                    cross_sectional_shape=(len(self.cross_sectional_features),)
                )
                
                # 早停和学习率调整
                callbacks = [
                    EarlyStopping(
                        monitor='val_loss',
                        patience=10,
                        restore_best_weights=True
                    ),
                    ReduceLROnPlateau(
                        monitor='val_loss',
                        factor=0.5,
                        patience=5,
                        min_lr=0.00001
                    )
                ]
                
                history = model.fit(
                    [X_seq_train, X_cross_train],
                    y_train,
                    validation_data=([X_seq_val, X_cross_val], y_val),
                    epochs=50,
                    batch_size=32,
                    callbacks=callbacks,
                    verbose=0
                )
                
                # 评估
                val_score = model.evaluate(
                    [X_seq_val, X_cross_val],
                    y_val,
                    verbose=0
                )[1]  # accuracy
                
                if val_score > best_score:
                    best_score = val_score
                    best_model = model
            
            # 保存最佳模型
            if best_model:
                best_model.save(self.model_path / 'hybrid_model.h5')
                self.models['hybrid_model'] = best_model
                logger.info(f"✅ 混合模型训练完成，最佳准确率: {best_score:.3f}")
            
            # 同时训练XGBoost用于SHAP解释
            # 合并特征
            X_all = np.concatenate([
                X_sequence.reshape(X_sequence.shape[0], -1),
                X_cross
            ], axis=1)
            
            X_train, X_val, y_train, y_val = train_test_split(
                X_all, y, test_size=0.2, random_state=42
            )
            
            xgb_model = self._train_xgboost_model(X_train, y_train, X_val, y_val)
            
            # 保存XGBoost模型
            joblib.dump(xgb_model, self.model_path / 'xgboost_model.pkl')
            self.models['xgboost_model'] = xgb_model
            
            # 重新初始化SHAP解释器
            self._initialize_shap_explainers()
            
        except Exception as e:
            logger.error(f"训练混合模型失败: {e}", exc_info=True)
    
    async def _prepare_training_data(
        self,
        data: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        准备训练数据
        """
        # 这里应该实现真实的数据准备逻辑
        # 为了演示，返回示例数据
        n_samples = 1000
        
        X_sequence = np.random.randn(
            n_samples,
            self.sequence_length,
            len(self.time_series_features)
        )
        
        X_cross = np.random.randn(
            n_samples,
            len(self.cross_sectional_features)
        )
        
        y = np.random.randint(0, 2, n_samples)
        
        return X_sequence, X_cross, y
    
    async def _load_models(self):
        """加载已保存的模型"""
        try:
            # 加载混合模型
            hybrid_path = self.model_path / 'hybrid_model.h5'
            if hybrid_path.exists():
                self.models['hybrid_model'] = tf.keras.models.load_model(hybrid_path)
                logger.info("✅ 加载混合模型")
            
            # 加载XGBoost模型
            xgb_path = self.model_path / 'xgboost_model.pkl'
            if xgb_path.exists():
                self.models['xgboost_model'] = joblib.load(xgb_path)
                logger.info("✅ 加载XGBoost模型")
            
            # 加载标准化器
            for scaler_type in ['sequence_scaler', 'cross_scaler']:
                scaler_path = self.model_path / f'{scaler_type}.pkl'
                if scaler_path.exists():
                    self.scalers[scaler_type] = joblib.load(scaler_path)
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
    
    async def _periodic_retrain(self):
        """定期重训练模型"""
        while True:
            try:
                # 等待配置的时间间隔
                await asyncio.sleep(86400)  # 每天重训练
                
                logger.info("开始定期模型重训练...")
                
                # 获取最新训练数据
                # training_data = await self._fetch_training_data()
                
                # if training_data is not None and len(training_data) > 1000:
                #     await self.train_hybrid_model(training_data)
                
            except Exception as e:
                logger.error(f"定期重训练失败: {e}")