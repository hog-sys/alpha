# src/scouts/social_sentiment_scout.py
"""
社交情绪侦察兵 - 根据PDF建议实现
监控Twitter、Reddit等平台的市场情绪
"""
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import re
from collections import defaultdict
import logging

# 情绪分析库
from textblob import TextBlob
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

from .base_scout import BaseScout, OpportunitySignal

logger = logging.getLogger(__name__)

class SocialSentimentScout(BaseScout):
    """
    社交情绪扫描器 - 实现PDF中建议的情绪分析功能
    """
    
    async def _initialize(self):
        """初始化社交情绪Scout"""
        # 下载NLTK数据
        try:
            nltk.download('vader_lexicon', quiet=True)
            self.sia = SentimentIntensityAnalyzer()
        except:
            logger.warning("VADER情绪分析器初始化失败")
            self.sia = None
        
        # 配置参数
        self.monitored_tokens = self.config.get('monitored_tokens', [
            'BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'LINK', 'UNI', 'AAVE'
        ])
        
        self.platforms = self.config.get('platforms', ['twitter', 'reddit'])
        self.min_mentions_threshold = self.config.get('min_mentions', 10)
        self.sentiment_change_threshold = self.config.get('sentiment_threshold', 0.3)
        
        # 历史数据缓存
        self.sentiment_history = defaultdict(lambda: defaultdict(list))
        self.mention_history = defaultdict(lambda: defaultdict(list))
        
        # 关键词和权重
        self.bullish_keywords = {
            'moon': 2.0, 'bullish': 1.5, 'pump': 1.5, 'breakout': 1.8,
            'buy': 1.2, 'long': 1.3, 'rocket': 2.0, 'gem': 1.5,
            'undervalued': 1.7, 'accumulate': 1.5, 'hodl': 1.3
        }
        
        self.bearish_keywords = {
            'dump': -2.0, 'bearish': -1.5, 'sell': -1.2, 'short': -1.3,
            'crash': -2.0, 'scam': -2.5, 'rug': -2.5, 'overvalued': -1.7,
            'bubble': -1.8, 'correction': -1.5
        }
        
        # 影响力权重（粉丝数范围）
        self.influence_weights = {
            'micro': (100, 1000, 1.0),      # 100-1k followers
            'small': (1000, 10000, 1.5),    # 1k-10k
            'medium': (10000, 100000, 2.0), # 10k-100k
            'large': (100000, 1000000, 3.0), # 100k-1M
            'mega': (1000000, float('inf'), 5.0)  # 1M+
        }
    
    async def scan(self) -> List[OpportunitySignal]:
        """执行社交情绪扫描"""
        opportunities = []
        
        tasks = []
        for token in self.monitored_tokens:
            tasks.append(self._analyze_token_sentiment(token))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                opportunities.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"社交情绪扫描错误: {result}")
        
        return opportunities
    
    async def _analyze_token_sentiment(self, token: str) -> List[OpportunitySignal]:
        """分析单个代币的社交情绪"""
        opportunities = []
        
        # 收集各平台数据
        platform_data = {}
        
        if 'twitter' in self.platforms:
            twitter_data = await self._fetch_twitter_data(token)
            if twitter_data:
                platform_data['twitter'] = twitter_data
        
        if 'reddit' in self.platforms:
            reddit_data = await self._fetch_reddit_data(token)
            if reddit_data:
                platform_data['reddit'] = reddit_data
        
        # 聚合分析
        if platform_data:
            analysis = self._aggregate_sentiment_analysis(token, platform_data)
            
            # 检测情绪突变
            if analysis['sentiment_change'] and abs(analysis['sentiment_delta']) > self.sentiment_change_threshold:
                opportunity = self.create_opportunity(
                    signal_type='sentiment_shift',
                    symbol=f"{token}/USDT",
                    confidence=min(abs(analysis['sentiment_delta']) * 2, 0.95),
                    data={
                        'token': token,
                        'current_sentiment': analysis['current_sentiment'],
                        'sentiment_delta': analysis['sentiment_delta'],
                        'mention_count': analysis['total_mentions'],
                        'mention_delta_pct': analysis['mention_change_pct'],
                        'platforms': list(platform_data.keys()),
                        'influencer_mentions': analysis['influencer_mentions'],
                        'trending_score': analysis['trending_score'],
                        'bullish_ratio': analysis['bullish_ratio'],
                        'key_narratives': analysis['key_narratives']
                    },
                    expires_in_minutes=30
                )
                opportunities.append(opportunity)
                
                logger.info(f"😊 情绪转变: {token} - "
                           f"变化: {analysis['sentiment_delta']:+.2f}, "
                           f"提及: {analysis['total_mentions']}")
            
            # 检测提及量激增
            if analysis['mention_spike'] and analysis['mention_change_pct'] > 200:
                opportunity = self.create_opportunity(
                    signal_type='social_volume_spike',
                    symbol=f"{token}/USDT",
                    confidence=min(analysis['mention_change_pct'] / 500, 0.9),
                    data={
                        'token': token,
                        'mention_count': analysis['total_mentions'],
                        'mention_change_pct': analysis['mention_change_pct'],
                        'sentiment': analysis['current_sentiment'],
                        'platforms': list(platform_data.keys()),
                        'viral_posts': analysis.get('viral_posts', [])
                    },
                    expires_in_minutes=60
                )
                opportunities.append(opportunity)
                
                logger.info(f"📢 社交量激增: {token} - "
                           f"增长: {analysis['mention_change_pct']:.0f}%")
        
        return opportunities
    
    async def _fetch_twitter_data(self, token: str) -> Optional[Dict]:
        """获取Twitter数据（使用开源工具）"""
        try:
            # 这里应该使用ntscraper或其他开源工具
            # 为了演示，我们模拟数据结构
            
            posts = []
            
            # 模拟API调用
            # 实际实现时使用：
            # from ntscraper import Nitter
            # scraper = Nitter()
            # posts = await scraper.get_tweets(f"${token} OR #{token}crypto")
            
            # 分析情绪
            sentiments = []
            total_followers = 0
            influencer_posts = []
            
            for post in posts:
                # 分析单条推文
                sentiment = self._analyze_text_sentiment(post.get('text', ''))
                sentiments.append(sentiment)
                
                followers = post.get('user', {}).get('followers_count', 0)
                total_followers += followers
                
                # 识别影响力用户
                if followers > 10000:
                    influencer_posts.append({
                        'user': post['user']['screen_name'],
                        'followers': followers,
                        'text': post['text'][:200],
                        'sentiment': sentiment
                    })
            
            if sentiments:
                return {
                    'posts_count': len(posts),
                    'avg_sentiment': np.mean(sentiments),
                    'sentiment_std': np.std(sentiments),
                    'total_reach': total_followers,
                    'influencer_posts': influencer_posts[:5],  # Top 5
                    'positive_ratio': sum(1 for s in sentiments if s > 0.1) / len(sentiments),
                    'negative_ratio': sum(1 for s in sentiments if s < -0.1) / len(sentiments)
                }
            
        except Exception as e:
            logger.error(f"获取Twitter数据失败 {token}: {e}")
        
        return None
    
    async def _fetch_reddit_data(self, token: str) -> Optional[Dict]:
        """获取Reddit数据"""
        try:
            # 使用PRAW库
            # import praw
            # reddit = praw.Reddit(client_id='...', client_secret='...', user_agent='...')
            
            subreddits = ['cryptocurrency', 'CryptoMoonShots', 'altcoin', token.lower()]
            
            posts_data = []
            comments_data = []
            
            # 模拟数据获取
            # 实际实现：
            # for subreddit_name in subreddits:
            #     subreddit = reddit.subreddit(subreddit_name)
            #     for post in subreddit.search(token, time_filter='day', limit=50):
            #         posts_data.append({...})
            
            # 分析情绪
            post_sentiments = [self._analyze_text_sentiment(p.get('title', '') + ' ' + p.get('selftext', '')) 
                              for p in posts_data]
            comment_sentiments = [self._analyze_text_sentiment(c.get('body', '')) 
                                 for c in comments_data]
            
            all_sentiments = post_sentiments + comment_sentiments
            
            if all_sentiments:
                return {
                    'posts_count': len(posts_data),
                    'comments_count': len(comments_data),
                    'avg_sentiment': np.mean(all_sentiments),
                    'sentiment_std': np.std(all_sentiments),
                    'upvote_ratio': np.mean([p.get('upvote_ratio', 0.5) for p in posts_data]),
                    'total_score': sum(p.get('score', 0) for p in posts_data),
                    'hot_posts': sorted(posts_data, key=lambda x: x.get('score', 0), reverse=True)[:3]
                }
            
        except Exception as e:
            logger.error(f"获取Reddit数据失败 {token}: {e}")
        
        return None
    
    def _analyze_text_sentiment(self, text: str) -> float:
        """分析文本情绪"""
        if not text:
            return 0.0
        
        # 清理文本
        text = re.sub(r'http\S+', '', text)  # 移除URLs
        text = re.sub(r'@\w+', '', text)     # 移除提及
        text = re.sub(r'#(\w+)', r'\1', text) # 移除#但保留标签文本
        
        # 基础情绪分析
        sentiment_scores = []
        
        # 1. TextBlob分析
        try:
            blob = TextBlob(text)
            sentiment_scores.append(blob.sentiment.polarity)
        except:
            pass
        
        # 2. VADER分析
        if self.sia:
            scores = self.sia.polarity_scores(text)
            sentiment_scores.append(scores['compound'])
        
        # 3. 关键词分析
        keyword_score = 0
        text_lower = text.lower()
        
        for word, weight in self.bullish_keywords.items():
            if word in text_lower:
                keyword_score += weight
        
        for word, weight in self.bearish_keywords.items():
            if word in text_lower:
                keyword_score += weight
        
        # 归一化关键词分数
        if keyword_score != 0:
            keyword_score = np.tanh(keyword_score / 5)  # 限制在[-1, 1]
            sentiment_scores.append(keyword_score)
        
        # 综合得分
        if sentiment_scores:
            return np.mean(sentiment_scores)
        
        return 0.0
    
    def _aggregate_sentiment_analysis(self, token: str, platform_data: Dict) -> Dict:
        """聚合多平台情绪分析"""
        current_time = datetime.now()
        
        # 计算综合指标
        total_mentions = sum(
            data.get('posts_count', 0) + data.get('comments_count', 0)
            for data in platform_data.values()
        )
        
        # 加权平均情绪（根据平台权重）
        platform_weights = {'twitter': 1.5, 'reddit': 1.0, 'telegram': 0.8}
        
        weighted_sentiment = 0
        total_weight = 0
        
        for platform, data in platform_data.items():
            weight = platform_weights.get(platform, 1.0)
            sentiment = data.get('avg_sentiment', 0)
            weighted_sentiment += sentiment * weight
            total_weight += weight
        
        current_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0
        
        # 获取历史数据
        history = self.sentiment_history[token]['aggregate']
        history.append({
            'time': current_time,
            'sentiment': current_sentiment,
            'mentions': total_mentions
        })
        
        # 保留最近24小时数据
        cutoff = current_time - timedelta(hours=24)
        history = [h for h in history if h['time'] > cutoff]
        self.sentiment_history[token]['aggregate'] = history
        
        # 计算变化
        sentiment_change = False
        sentiment_delta = 0
        mention_spike = False
        mention_change_pct = 0
        
        if len(history) >= 10:
            # 比较最近1小时vs前3小时
            recent = [h for h in history if h['time'] > current_time - timedelta(hours=1)]
            previous = [h for h in history if current_time - timedelta(hours=4) < h['time'] <= current_time - timedelta(hours=1)]
            
            if recent and previous:
                recent_sentiment = np.mean([h['sentiment'] for h in recent])
                previous_sentiment = np.mean([h['sentiment'] for h in previous])
                sentiment_delta = recent_sentiment - previous_sentiment
                sentiment_change = abs(sentiment_delta) > self.sentiment_change_threshold
                
                recent_mentions = sum(h['mentions'] for h in recent)
                previous_mentions = sum(h['mentions'] for h in previous) / 3  # 平均每小时
                
                if previous_mentions > 0:
                    mention_change_pct = ((recent_mentions - previous_mentions) / previous_mentions) * 100
                    mention_spike = mention_change_pct > 100
        
        # 计算其他指标
        influencer_mentions = sum(
            len(data.get('influencer_posts', []))
            for data in platform_data.values()
        )
        
        # 趋势评分（基于提及增长和情绪）
        trending_score = min(
            (mention_change_pct / 100) * 0.5 + 
            abs(sentiment_delta) * 2 + 
            (influencer_mentions / 10),
            10.0
        )
        
        # 多空比例
        bullish_count = sum(
            data.get('posts_count', 0) * data.get('positive_ratio', 0.5)
            for data in platform_data.values()
        )
        bearish_count = sum(
            data.get('posts_count', 0) * data.get('negative_ratio', 0.5)
            for data in platform_data.values()
        )
        
        bullish_ratio = bullish_count / (bullish_count + bearish_count) if (bullish_count + bearish_count) > 0 else 0.5
        
        # 提取关键叙事
        key_narratives = []
        for data in platform_data.values():
            if 'hot_posts' in data:
                for post in data['hot_posts'][:2]:
                    key_narratives.append(post.get('title', '')[:100])
            if 'viral_posts' in data:
                for post in data['viral_posts'][:2]:
                    key_narratives.append(post.get('text', '')[:100])
        
        return {
            'current_sentiment': current_sentiment,
            'sentiment_delta': sentiment_delta,
            'sentiment_change': sentiment_change,
            'total_mentions': total_mentions,
            'mention_change_pct': mention_change_pct,
            'mention_spike': mention_spike,
            'influencer_mentions': influencer_mentions,
            'trending_score': trending_score,
            'bullish_ratio': bullish_ratio,
            'key_narratives': key_narratives[:5]
        }


class DeveloperActivityScout(BaseScout):
    """
    开发者活动侦察兵 - 监控GitHub活动
    """
    
    async def _initialize(self):
        """初始化开发者活动Scout"""
        self.github_token = self.config.get('github_token')
        self.monitored_repos = self.config.get('monitored_repos', {})
        
        # 活动历史
        self.activity_history = defaultdict(list)
        
        # GitHub API基础URL
        self.github_api = "https://api.github.com"
        
        # 请求头
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.github_token:
            self.headers['Authorization'] = f'token {self.github_token}'
    
    async def scan(self) -> List[OpportunitySignal]:
        """扫描开发者活动"""
        opportunities = []
        
        for token, repo_url in self.monitored_repos.items():
            if 'github.com' in repo_url:
                repo_path = repo_url.split('github.com/')[-1].strip('/')
                activity = await self._analyze_repo_activity(token, repo_path)
                
                if activity:
                    opportunities.extend(activity)
        
        return opportunities
    
    async def _analyze_repo_activity(self, token: str, repo_path: str) -> List[OpportunitySignal]:
        """分析仓库活动"""
        opportunities = []
        
        try:
            # 获取仓库统计
            repo_stats = await self._fetch_repo_stats(repo_path)
            commit_activity = await self._fetch_commit_activity(repo_path)
            pr_activity = await self._fetch_pr_activity(repo_path)
            
            if repo_stats:
                # 计算活动评分
                activity_score = self._calculate_activity_score(
                    repo_stats, commit_activity, pr_activity
                )
                
                # 检测活动异常
                if activity_score > 7:  # 高活跃度
                    opportunity = self.create_opportunity(
                        signal_type='high_dev_activity',
                        symbol=f"{token}/USDT",
                        confidence=min(activity_score / 10, 0.9),
                        data={
                            'token': token,
                            'repo': repo_path,
                            'activity_score': activity_score,
                            'commits_30d': commit_activity.get('commits_30d', 0),
                            'active_contributors': commit_activity.get('contributors', 0),
                            'open_prs': pr_activity.get('open_count', 0),
                            'stars': repo_stats.get('stargazers_count', 0),
                            'forks': repo_stats.get('forks_count', 0)
                        }
                    )
                    opportunities.append(opportunity)
                    
                    logger.info(f"👨‍💻 高开发活动: {token} - 评分: {activity_score:.1f}")
        
        except Exception as e:
            logger.error(f"分析仓库活动失败 {repo_path}: {e}")
        
        return opportunities
    
    async def _fetch_repo_stats(self, repo_path: str) -> Optional[Dict]:
        """获取仓库基础统计"""
        try:
            url = f"{self.github_api}/repos/{repo_path}"
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"获取仓库统计失败: {e}")
        return None
    
    async def _fetch_commit_activity(self, repo_path: str) -> Dict:
        """获取提交活动"""
        try:
            url = f"{self.github_api}/repos/{repo_path}/stats/commit_activity"
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # 计算30天提交数
                    commits_30d = sum(week['total'] for week in data[-4:])
                    return {'commits_30d': commits_30d}
        except Exception as e:
            logger.error(f"获取提交活动失败: {e}")
        return {}
    
    async def _fetch_pr_activity(self, repo_path: str) -> Dict:
        """获取PR活动"""
        try:
            url = f"{self.github_api}/repos/{repo_path}/pulls"
            params = {'state': 'open', 'per_page': 100}
            async with self.session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    prs = await response.json()
                    return {'open_count': len(prs)}
        except Exception as e:
            logger.error(f"获取PR活动失败: {e}")
        return {}
    
    def _calculate_activity_score(self, repo_stats: Dict, commit_activity: Dict, pr_activity: Dict) -> float:
        """计算活动评分"""
        score = 0
        
        # 基于提交频率
        commits = commit_activity.get('commits_30d', 0)
        if commits > 100:
            score += 3
        elif commits > 50:
            score += 2
        elif commits > 20:
            score += 1
        
        # 基于星标数
        stars = repo_stats.get('stargazers_count', 0)
        if stars > 5000:
            score += 2
        elif stars > 1000:
            score += 1
        
        # 基于Fork数
        forks = repo_stats.get('forks_count', 0)
        if forks > 500:
            score += 2
        elif forks > 100:
            score += 1
        
        # 基于PR活动
        open_prs = pr_activity.get('open_count', 0)
        if open_prs > 20:
            score += 2
        elif open_prs > 10:
            score += 1
        
        return score