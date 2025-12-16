import aiosqlite
from datetime import datetime, timedelta

class FTDDatabase:
    def __init__(self, db_path="ftd.db"):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    kickoff TEXT,
                    league TEXT,
                    home TEXT,
                    away TEXT,
                    draw_odds REAL,
                    model_prob REAL,
                    ev_percent REAL,
                    reasons TEXT,
                    liquidity REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    stake_amount REAL DEFAULT 0
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS draw_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_date TEXT,
                    pattern_type TEXT UNIQUE,
                    frequency INTEGER,
                    draw_rate REAL,
                    example_matches TEXT,
                    model_boost REAL DEFAULT 0
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS backtest_hits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_date TEXT,
                    league TEXT,
                    reasons TEXT,
                    hit_count INTEGER,
                    avg_ev REAL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS backtest_misses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_date TEXT,
                    league TEXT,
                    reasons TEXT,
                    miss_count INTEGER,
                    avg_ev REAL
                )
            ''')
            await db.commit()
    
    async def save_predictions(self, predictions):
        async with aiosqlite.connect(self.db_path) as db:
            for pred in predictions:
                await db.execute('''
                    INSERT OR REPLACE INTO predictions 
                    (date, kickoff, league, home, away, draw_odds, model_prob, ev_percent, reasons, liquidity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pred['date'], pred['kickoff'], pred['league'], pred['home'], 
                      pred['away'], pred['draw_odds'], pred['model_prob'], pred['ev_percent'], 
                      pred['reasons'], pred.get('liquidity', 0)))
            await db.commit()
    
    async def get_todays_predictions(self):
        today = datetime.now().strftime('%Y-%m-%d')
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT id, kickoff, league, home, away, draw_odds, model_prob, ev_percent, reasons, liquidity
                FROM predictions WHERE date = ? AND status = 'pending'
                ORDER BY ev_percent DESC LIMIT 15
            ''', (today,))
            return await cursor.fetchall()
    
    async def update_prediction_result(self, pred_id: int, result: str, stake=0):
        async with aiosqlite.connect(self.db_path) as db:
            status = 'HIT' if result == 'draw' else 'MISS'
            await db.execute('''
                UPDATE predictions SET status = ?, result = ?, stake_amount = ? WHERE id = ?
            ''', (status, result, stake, pred_id))
            await db.commit()
    
    async def get_performance_stats(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'HIT' THEN 1 ELSE 0 END) as hits,
                    AVG(ev_percent) as avg_ev
                FROM predictions 
                WHERE date >= date('now', '-30 days')
            ''')
            stats = await cursor.fetchone()
            
            total = stats[0] if stats and stats[0] is not None else 0
            hits = stats[1] if stats and stats[1] is not None else 0
            avg_ev = stats[2] if stats and stats[2] is not None else 0
            
            hit_rate = (hits / total * 100) if total > 0 else 0
            return {
                'total': int(total),
                'hits': int(hits),
                'hit_rate': round(hit_rate, 1),
                'avg_ev': round(avg_ev, 1) if avg_ev else 0,
                'total_pnl': 0
            }
    
    async def save_draw_patterns(self, patterns):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM draw_patterns")
            today = datetime.now().strftime('%Y-%m-%d')
            for pattern in patterns:
                await db.execute('''
                    INSERT OR REPLACE INTO draw_patterns 
                    (analysis_date, pattern_type, frequency, draw_rate, example_matches, model_boost)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (today, pattern['type'], pattern['count'], pattern['rate'], 
                      pattern['examples'], pattern.get('boost', 0)))
            await db.commit()
    
    async def run_backtest_analysis(self):
        async with aiosqlite.connect(self.db_path) as db:
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor = await db.execute('''
                SELECT league, reasons, AVG(ev_percent), COUNT(*) 
                FROM predictions 
                WHERE status = 'HIT' AND date >= date('now', '-30 days')
                GROUP BY league, reasons
                ORDER BY COUNT(*) DESC LIMIT 5
            ''')
            hits = await cursor.fetchall()
            await db.execute("DELETE FROM backtest_hits")
            for hit in hits:
                league, reasons, avg_ev, count = hit
                await db.execute('''
                    INSERT INTO backtest_hits (analysis_date, league, reasons, hit_count, avg_ev)
                    VALUES (?, ?, ?, ?, ?)
                ''', (today, str(league), str(reasons), int(count), float(avg_ev or 0)))
            
            cursor = await db.execute('''
                SELECT league, reasons, AVG(ev_percent), COUNT(*) 
                FROM predictions 
                WHERE status = 'MISS' AND date >= date('now', '-30 days')
                GROUP BY league, reasons
                ORDER BY COUNT(*) DESC LIMIT 5
            ''')
            misses = await cursor.fetchall()
            await db.execute("DELETE FROM backtest_misses")
            for miss in misses:
                league, reasons, avg_ev, count = miss
                await db.execute('''
                    INSERT INTO backtest_misses (analysis_date, league, reasons, miss_count, avg_ev)
                    VALUES (?, ?, ?, ?, ?)
                ''', (today, str(league), str(reasons), int(count), float(avg_ev or 0)))
            
            await db.commit()
    
    async def kelly_stake(self, bankroll, odds, prob):
        kelly_fraction = (prob * odds - 1) / (odds - 1)
        return max(0, min(bankroll * kelly_fraction * 0.25, bankroll * 0.05))