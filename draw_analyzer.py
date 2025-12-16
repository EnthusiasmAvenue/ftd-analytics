import requests
import os
from datetime import datetime, timedelta
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DrawAnalyzer:
    """
    Analyzes past matches that ended in draws to identify patterns
    and improve future predictions through self-learning
    """
    
    def __init__(self):
        self.api_key = os.getenv('RAPIDAPI_KEY', '474daff9c5msh0a7b5b2f2e8f1a4p1e7f5ejsn8e4c4f5a0a3')
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
    
    async def analyze_recent_draws(self, days_back=7, leagues=None):
        """
        Fetch and analyze matches that ended in draws over the past N days
        
        Args:
            days_back: How many days to look back (default 7)
            leagues: List of league IDs to analyze (default: high-draw leagues)
        
        Returns:
            List of draw patterns discovered
        """
        if leagues is None:
            # Focus on high-draw leagues
            leagues = [40, 41, 42, 179, 94, 88, 144, 203]
        
        logger.info(f"🔍 Analyzing draws from past {days_back} days...")
        
        all_draws = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Fetch fixtures for each day
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            for league_id in leagues:
                try:
                    url = f"https://v3.football.api-sports.io/fixtures?date={date_str}&league={league_id}"
                    response = requests.get(url, headers=self.headers, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        fixtures = data.get('response', [])
                        
                        for fixture in fixtures:
                            # Check if match ended in a draw
                            if fixture['fixture']['status']['short'] == 'FT':
                                home_goals = fixture['goals']['home']
                                away_goals = fixture['goals']['away']
                                
                                if home_goals == away_goals and home_goals is not None:
                                    draw_match = self._extract_draw_data(fixture)
                                    all_draws.append(draw_match)
                    
                except Exception as e:
                    logger.debug(f"Error fetching {date_str} for league {league_id}: {e}")
                    continue
            
            current_date += timedelta(days=1)
        
        logger.info(f"✅ Found {len(all_draws)} draws in past {days_back} days")
        
        # Analyze patterns
        patterns = self._identify_patterns(all_draws)
        
        return patterns
    
    def _extract_draw_data(self, fixture):
        """Extract relevant data from a drawn match"""
        try:
            return {
                'date': fixture['fixture']['date'][:10],
                'league': fixture['league']['name'],
                'league_id': fixture['league']['id'],
                'home': fixture['teams']['home']['name'],
                'away': fixture['teams']['away']['name'],
                'score': f"{fixture['goals']['home']}-{fixture['goals']['away']}",
                'home_odds': fixture.get('odds', {}).get('home', None),
                'draw_odds': fixture.get('odds', {}).get('draw', None),
                'away_odds': fixture.get('odds', {}).get('away', None),
            }
        except Exception as e:
            logger.warning(f"Error extracting draw data: {e}")
            return None
    
    def _identify_patterns(self, draws):
        """
        Analyze draw matches to identify patterns
        
        Patterns include:
        - Which leagues have highest draw rates
        - What score lines are most common
        - Time patterns (day of week, time of day)
        - Team characteristics
        """
        if not draws:
            return []
        
        # Group by league
        leagues = defaultdict(list)
        scores = defaultdict(int)
        
        for draw in draws:
            if draw:
                leagues[draw['league']].append(draw)
                scores[draw['score']] += 1
        
        # Build pattern insights
        patterns = []
        
        # League-specific patterns
        for league, matches in leagues.items():
            if len(matches) >= 2:  # At least 2 draws to consider a pattern
                draw_count = len(matches)
                common_score = max(scores.items(), key=lambda x: x[1])[0] if scores else "1-1"
                
                # Calculate boost based on frequency
                # More draws = higher confidence = bigger boost
                boost = min(0.15, draw_count * 0.02)  # Cap at 15%
                
                patterns.append({
                    'type': f"{league.lower().replace(' ', '_')}_draws",
                    'count': draw_count,
                    'rate': None,  # Will be calculated in combination with total matches
                    'examples': f"{league} ({draw_count} draws in past week)",
                    'boost': boost,
                    'common_score': common_score,
                    'details': {
                        'league': league,
                        'recent_draws': draw_count,
                        'sample_matches': [f"{m['home']} {m['score']} {m['away']}" for m in matches[:3]]
                    }
                })
        
        # Score pattern analysis
        if scores:
            most_common_score = max(scores.items(), key=lambda x: x[1])
            patterns.append({
                'type': 'common_scoreline',
                'count': most_common_score[1],
                'rate': most_common_score[1] / len(draws),
                'examples': f"{most_common_score[0]} score ({most_common_score[1]} times)",
                'boost': 0.03,
                'common_score': most_common_score[0],
                'details': {
                    'scoreline': most_common_score[0],
                    'frequency': most_common_score[1],
                    'all_scores': dict(scores)
                }
            })
        
        logger.info(f"📊 Identified {len(patterns)} draw patterns")
        return patterns
    
    async def learn_from_marked_results(self, db):
        """
        Analyze predictions that were marked as draws (✅) to learn patterns
        Adjust future predictions based on what actually worked
        """
        logger.info("🧠 Learning from marked results...")
        
        async with db.get_connection() as conn:
            # Get successful predictions (marked as draws)
            cursor = await conn.execute('''
                SELECT league, reasons, draw_odds, model_prob, ev_percent, COUNT(*) as hits
                FROM predictions
                WHERE status = 'HIT' AND date >= date('now', '-30 days')
                GROUP BY league, reasons
                HAVING COUNT(*) >= 2
                ORDER BY COUNT(*) DESC
            ''')
            successful_patterns = await cursor.fetchall()
            
            # Get failed predictions  
            cursor = await conn.execute('''
                SELECT league, reasons, draw_odds, model_prob, ev_percent, COUNT(*) as misses
                FROM predictions
                WHERE status = 'MISS' AND date >= date('now', '-30 days')
                GROUP BY league, reasons
                HAVING COUNT(*) >= 2
                ORDER BY COUNT(*) DESC
            ''')
            failed_patterns = await cursor.fetchall()
        
        learned_patterns = []
        
        # Boost successful patterns
        for pattern in successful_patterns:
            league, reasons, avg_odds, avg_prob, avg_ev, hits = pattern
            
            # Higher hit count = more confidence = bigger boost
            confidence_boost = min(0.20, hits * 0.03)  # Cap at 20%
            
            learned_patterns.append({
                'type': f"learned_{league.lower().replace(' ', '_')}",
                'count': hits,
                'rate': None,
                'examples': f"{league}: {reasons} ({hits} successful predictions)",
                'boost': confidence_boost,
                'details': {
                    'league': league,
                    'reasons': reasons,
                    'hit_count': hits,
                    'avg_ev': avg_ev,
                    'source': 'learned_from_results'
                }
            })
        
        # Reduce weight for failed patterns
        for pattern in failed_patterns:
            league, reasons, avg_odds, avg_prob, avg_ev, misses = pattern
            
            # Negative boost (penalty) for patterns that consistently fail
            penalty = -min(0.10, misses * 0.02)  # Cap at -10%
            
            learned_patterns.append({
                'type': f"avoid_{league.lower().replace(' ', '_')}",
                'count': misses,
                'rate': None,
                'examples': f"{league}: {reasons} (AVOID - {misses} misses)",
                'boost': penalty,
                'details': {
                    'league': league,
                    'reasons': reasons,
                    'miss_count': misses,
                    'avg_ev': avg_ev,
                    'source': 'learned_from_failures'
                }
            })
        
        logger.info(f"✅ Learned {len(learned_patterns)} patterns from historical results")
        logger.info(f"   📈 {len(successful_patterns)} successful patterns (boost)")
        logger.info(f"   📉 {len(failed_patterns)} failed patterns (penalty)")
        
        return learned_patterns
    
    async def combine_patterns(self, historical_draws, learned_patterns, static_patterns):
        """
        Combine all pattern sources into unified insights:
        1. Recent draws from API (what's happening now)
        2. Learned patterns from marked results (what worked for us)
        3. Static patterns from research (general knowledge)
        
        Returns weighted average of all sources
        """
        all_patterns = []
        
        # Add historical draws (highest weight - most recent data)
        for pattern in historical_draws:
            pattern['weight'] = 3.0  # Highest priority
            pattern['source'] = 'recent_draws'
            all_patterns.append(pattern)
        
        # Add learned patterns (medium weight - our specific experience)
        for pattern in learned_patterns:
            pattern['weight'] = 2.0  # Medium priority
            all_patterns.append(pattern)
        
        # Add static patterns (lowest weight - general knowledge)
        for pattern in static_patterns:
            pattern['weight'] = 1.0  # Lowest priority
            pattern['source'] = 'static_research'
            all_patterns.append(pattern)
        
        # Calculate weighted boost
        total_weight = sum(p['weight'] for p in all_patterns)
        weighted_boost = sum(p['boost'] * p['weight'] for p in all_patterns) / total_weight if total_weight > 0 else 0
        
        logger.info(f"🎯 Combined boost from all sources: +{weighted_boost:.1%}")
        logger.info(f"   - Recent draws: {len(historical_draws)} patterns")
        logger.info(f"   - Learned results: {len(learned_patterns)} patterns")
        logger.info(f"   - Static research: {len(static_patterns)} patterns")
        
        return {
            'patterns': all_patterns,
            'total_boost': weighted_boost,
            'sources': {
                'recent_draws': len(historical_draws),
                'learned': len(learned_patterns),
                'static': len(static_patterns)
            }
        }


# Helper function for integration with main app
async def get_intelligent_patterns(db):
    """
    Main entry point: Gets patterns from all sources and combines them
    This replaces the old research_recent_draws() function
    """
    analyzer = DrawAnalyzer()
    
    # 1. Analyze recent actual draws from API
    recent_draws = await analyzer.analyze_recent_draws(days_back=7)
    
    # 2. Learn from our own marked results
    learned = await analyzer.learn_from_marked_results(db)
    
    # 3. Static patterns (baseline knowledge)
    static = [
        {'type': 'lower_league_edge', 'count': 18, 'rate': 0.29, 'examples': 'Championship/League One', 'boost': 0.12},
        {'type': 'scottish_stalemate', 'count': 11, 'rate': 0.27, 'examples': 'Scottish lower divisions', 'boost': 0.09},
        {'type': 'portugal_parity', 'count': 9, 'rate': 0.265, 'examples': 'Primeira Liga mid-table', 'boost': 0.07},
    ]
    
    # 4. Combine all sources with intelligent weighting
    combined = await analyzer.combine_patterns(recent_draws, learned, static)
    
    return combined['patterns'], combined['total_boost']
