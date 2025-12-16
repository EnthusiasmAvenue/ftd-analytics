import requests
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scrape_todays_fixtures():
    """Fetch real fixtures from API-Football with proper error handling"""
    today = datetime.now().strftime('%Y-%m-%d')
    day_of_week = datetime.now().strftime('%A')
    
    logger.info(f"📅 Today is {day_of_week}, {today}")
    
    # Get API key from environment variable for security
    api_key = os.getenv('RAPIDAPI_KEY', '474daff9c5msh0a7b5b2f2e8f1a4p1e7f5ejsn8e4c4f5a0a3')
    
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    # Draw-prone leagues: Mix of weekday and weekend leagues
    # Premier League (39), La Liga (140), Serie A (135), Bundesliga (78) - play midweek
    # Championship (40), Scottish (179) - mostly weekends
    # Add more active leagues for broader coverage
    global_draw_leagues = [
        39,   # Premier League (England) - plays midweek
        40,   # Championship (England)
        41,   # League One (England) 
        42,   # League Two (England)
        140,  # La Liga (Spain) - plays midweek
        135,  # Serie A (Italy) - plays midweek
        78,   # Bundesliga (Germany) - plays midweek
        179,  # Scottish Premiership
        144,  # Belgian First Division A
        94,   # Primeira Liga (Portugal)
        88,   # Eredivisie (Netherlands)
        203,  # Turkish Super Lig
        103,  # Eliteserien (Norway)
        87,   # Allsvenskan (Sweden)
        98,   # Superliga (Denmark)
        61,   # Ligue 1 (France) - plays midweek
        71,   # Serie B (Brazil)
        73,   # MLS (USA)
    ]
    
    all_fixtures = []
    
    # Fetch in batches to avoid URL length limits
    for i in range(0, len(global_draw_leagues), 10):
        batch = global_draw_leagues[i:i+10]
        leagues_str = ",".join(map(str, batch))
        
        try:
            url = f"https://v3.football.api-sports.io/fixtures?date={today}&league={leagues_str}"
            logger.info(f"🔍 Fetching batch {i//10 + 1}: {len(batch)} leagues")
            
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check API response structure
                if 'response' not in data:
                    logger.error(f"❌ Invalid API response: {data}")
                    continue
                
                fixtures = data['response']
                logger.info(f"✅ Batch {i//10 + 1}: Found {len(fixtures)} matches")
                
                for fixture in fixtures:
                    try:
                        home = fixture['teams']['home']['name']
                        away = fixture['teams']['away']['name']
                        kickoff_utc = fixture['fixture']['date']
                        kickoff_time = datetime.fromisoformat(kickoff_utc.replace('Z', '+00:00'))
                        kickoff_formatted = kickoff_time.strftime('%H:%M')
                        league = fixture['league']['name']
                        fixture_id = fixture['fixture']['id']
                        
                        # Try to get real odds, fallback to estimate
                        draw_odds = await get_draw_odds(fixture_id, league, headers)
                        
                        # Estimate market liquidity based on league
                        liquidity = estimate_liquidity(league)
                        
                        all_fixtures.append({
                            'fixture_id': fixture_id,
                            'kickoff': kickoff_formatted,
                            'league': league,
                            'home': home,
                            'away': away,
                            'draw_odds': draw_odds,
                            'liquidity': liquidity
                        })
                        
                    except KeyError as e:
                        logger.warning(f"⚠️ Skipping fixture due to missing data: {e}")
                        continue
                        
            elif response.status_code == 429:
                logger.error(f"❌ Rate limit exceeded (429). Wait before retrying.")
                break
            elif response.status_code == 403:
                logger.error(f"❌ API key invalid or expired (403)")
                break
            else:
                logger.error(f"❌ API error {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Request timeout for batch {i//10 + 1}")
            continue
        except Exception as e:
            logger.error(f"❌ Unexpected error in batch {i//10 + 1}: {str(e)}")
            continue
    
    if all_fixtures:
        logger.info(f"🎯 TOTAL: {len(all_fixtures)} matches found for {today}")
        return all_fixtures
    else:
        logger.warning(f"⚠️ NO MATCHES found for {today} ({day_of_week})")
        logger.warning(f"   This is NORMAL if:")
        logger.warning(f"   - Today is Monday-Thursday (Championship/Scottish play weekends)")
        logger.warning(f"   - Mid-season break")
        logger.warning(f"   - International break")
        logger.warning(f"   ✅ Try again on Friday-Sunday for more matches!")
        return []

async def get_draw_odds(fixture_id, league, headers):
    """Attempt to fetch real draw odds from API-Football"""
    try:
        url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'response' in data and len(data['response']) > 0:
                # Look for Match Winner market
                bookmakers = data['response'][0].get('bookmakers', [])
                for bookmaker in bookmakers:
                    for bet in bookmaker.get('bets', []):
                        if bet['name'] == 'Match Winner':
                            for value in bet['values']:
                                if value['value'] == 'Draw':
                                    odds = float(value['odd'])
                                    logger.info(f"📊 Real odds found: {odds}")
                                    return round(odds, 2)
    except Exception as e:
        logger.debug(f"Could not fetch real odds: {e}")
    
    # Fallback: Estimate based on league
    return estimate_draw_odds(league)

def estimate_draw_odds(league):
    """Estimate draw odds based on league characteristics"""
    high_draw_leagues = {
        'Championship': 3.60,
        'League One': 3.50,
        'League Two': 3.45,
        'Scottish Championship': 3.55,
        'Scottish League One': 3.50,
        'Primeira Liga': 3.65,
        'Eredivisie': 3.70,
        'Belgian First Division A': 3.75,
    }
    
    for league_key, odds in high_draw_leagues.items():
        if league_key.lower() in league.lower():
            return odds
    
    # Default odds for unknown leagues
    return 3.80

def estimate_liquidity(league):
    """Estimate betting market liquidity based on league popularity"""
    tier_1_leagues = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1']
    tier_2_leagues = ['Championship', 'Eredivisie', 'Primeira Liga', 'Belgian']
    tier_3_leagues = ['League One', 'Scottish', 'League Two']
    
    league_lower = league.lower()
    
    if any(t1.lower() in league_lower for t1 in tier_1_leagues):
        return 5000000  # $5M+
    elif any(t2.lower() in league_lower for t2 in tier_2_leagues):
        return 1500000  # $1.5M
    elif any(t3.lower() in league_lower for t3 in tier_3_leagues):
        return 500000   # $500K
    else:
        return 300000   # $300K default

async def calculate_ev(match, pattern_boosts=0):
    """Calculate Expected Value for draw bet"""
    base_prob = 0.28 + pattern_boosts  # More conservative base
    
    # League-specific adjustments
    draw_prone_leagues = ['Championship', 'League One', 'League Two', 'Scottish', 'Primeira Liga', 'Eredivisie']
    if any(l in match['league'] for l in draw_prone_leagues):
        base_prob += 0.08
    
    # Odds-based confidence
    if match['draw_odds'] < 3.60:
        base_prob += 0.06
    elif match['draw_odds'] < 3.80:
        base_prob += 0.04
    
    # Liquidity indicator
    if match.get('liquidity', 0) > 1000000:
        base_prob += 0.03
    
    # Cap probability
    model_prob = min(base_prob, 0.45)
    
    # Calculate EV: (probability × odds) - 1
    ev = (model_prob * match['draw_odds']) - 1
    
    # Build reasoning
    reasons = []
    if any(l in match['league'] for l in draw_prone_leagues):
        reasons.append("HIGH DRAW LEAGUE")
    if match['draw_odds'] < 3.60:
        reasons.append("LOW ODDS")
    reasons.append("AI MODEL")
    
    return {
        **match,
        'model_prob': round(model_prob, 3),
        'ev_percent': round(ev * 100, 1),
        'reasons': ', '.join(reasons)
    }
