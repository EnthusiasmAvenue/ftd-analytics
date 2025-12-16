# FTD Analytics - Football Draw Prediction System

AI-powered system that analyzes 20+ football leagues to find the top 15 draw betting opportunities each day.

## 🚀 Quick Start

### 1. Get API Key
1. Go to [RapidAPI API-Football](https://rapidapi.com/api-sports/api/api-football)
2. Subscribe (free tier includes 100 requests/day)
3. Copy your API key

### 2. Local Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export RAPIDAPI_KEY="your_key_here"

# Run the app
python app.py
```

Visit `http://localhost:8000` to see your dashboard.

### 3. Deploy to Render
1. Create new Web Service on [Render](https://render.com)
2. Connect your GitHub repo
3. Add environment variable:
   - Key: `RAPIDAPI_KEY`
   - Value: Your API key
4. Deploy!

## 🎯 How It Works

### Data Flow
1. **Scrape Fixtures**: Fetches today's matches from 20+ leagues via API-Football
2. **Calculate Probabilities**: Uses AI model + historical patterns to estimate draw probability
3. **Compute EV**: Calculates Expected Value: `(probability × odds) - 1`
4. **Rank Picks**: Shows top 15 matches with highest EV
5. **Kelly Staking**: Recommends optimal bet size using Kelly Criterion

### Targeted Leagues (High Draw Rate)
- 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship, League One, League Two
- 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish leagues
- 🇵🇹 Primeira Liga
- 🇳🇱 Eredivisie
- 🇧🇪 Belgian First Division
- 🇹🇷 Turkish Super Lig
- 🇸🇪 Allsvenskan
- 🇳🇴 Eliteserien
- 🇩🇰 Danish Superliga
- And 10+ more...

## 📊 Dashboard Features

### Stats Display
- **Total Bets**: All predictions tracked
- **Hit Rate**: % of successful draw predictions
- **Avg EV**: Average expected value of picks

### Prediction Table
Each match shows:
- **Kickoff Time**: When the match starts
- **League**: Competition name
- **Match**: Home vs Away teams
- **Odds**: Current draw odds
- **Kelly**: Recommended stake size (based on $1000 bankroll)
- **EV%**: Expected value percentage
- **Actions**: Mark results as wins ✅ or losses ❌

### Manual Controls
- **🔄 Refresh**: Reload dashboard
- **⚡ Run Analysis Now**: Manually trigger data refresh
- **Result Tracking**: Click ✅ or ❌ to record outcomes

## 🔧 Configuration

### Environment Variables
```bash
RAPIDAPI_KEY=your_key          # Required: API-Football key
DATABASE_PATH=ftd.db           # Optional: SQLite database location
DISABLE_BACKGROUND=false       # Optional: Disable auto-refresh
PORT=8000                      # Optional: Server port
```

### API Limits
- Free tier: 100 requests/day
- Each analysis uses ~20-30 requests (depending on leagues)
- Background task runs every 4 hours = ~120 requests/day
- Consider upgrading if hitting limits

## 📈 Performance Tracking

### Backtest Analysis
The system automatically:
- Tracks all predictions and their outcomes
- Identifies which patterns lead to hits vs misses
- Calculates hit rate over rolling 30-day window
- Stores performance in SQLite database

### Kelly Criterion Staking
Conservative position sizing:
- Uses 25% of full Kelly (fractional Kelly)
- Caps stakes at 5% of bankroll
- Formula: `(prob × odds - 1) / (odds - 1) × bankroll × 0.25`

## 🐛 Troubleshooting

### "NO HIGH EV DRAWS TODAY"
**Possible causes:**
1. No matches scheduled in target leagues
2. All matches have EV < 5% (filtered out)
3. API key issue

**Solution:** Click "Run Analysis Now" to refresh

### API Key Errors
```
❌ API error 403: Forbidden
```
**Solution:** Check your RapidAPI key and subscription status

### Database Issues
```
❌ Database locked
```
**Solution:** 
- On Render: Database in `/tmp/` gets wiped on restart (expected)
- Locally: Delete `ftd.db` and restart app

### No Data After Deployment
**Solution:**
1. Check Render logs for errors
2. Verify `RAPIDAPI_KEY` environment variable is set
3. Wait 60 seconds for initial analysis to complete
4. Click "Run Analysis Now" button

## 📝 File Structure

```
ftd-analytics/
├── app.py              # FastAPI web server & dashboard
├── scraper.py          # Fixture scraping & EV calculation
├── db.py              # SQLite database operations
├── live_odds.py       # Live odds comparison (optional)
├── requirements.txt   # Python dependencies
├── Procfile          # Render deployment config
└── .env              # Environment variables (create this)
```

## 🔒 Security Notes

- Never commit `.env` file to Git
- Never hardcode API keys in source code
- Use environment variables for all secrets
- The exposed API key in old code has been removed

## 📊 Expected Performance

Based on historical data:
- **Draw rate in target leagues**: 26-31%
- **Target hit rate**: 28-35% (above market baseline of ~27%)
- **Positive EV threshold**: Only show picks with EV > 5%
- **Kelly stake size**: Typically 2-5% of bankroll per pick

## 🚨 Disclaimer

This is an educational project for analyzing football draw probabilities. 

- No guarantee of profits
- Past performance ≠ future results
- Only bet what you can afford to lose
- Gambling can be addictive - play responsibly

## 💡 Future Enhancements

Potential improvements:
- [ ] Real-time odds scraping from multiple bookmakers
- [ ] Machine learning model trained on historical results
- [ ] Team form analysis (recent results, head-to-head)
- [ ] Expected Goals (xG) data integration
- [ ] Referee statistics (draw-prone refs)
- [ ] Weather data for outdoor matches
- [ ] Line movement tracking (odds changes)
- [ ] Multi-user support with individual bankrolls
- [ ] Telegram/Discord alerts for high EV picks

## 📚 Resources

- [API-Football Documentation](https://www.api-football.com/documentation-v3)
- [Kelly Criterion Explained](https://en.wikipedia.org/wiki/Kelly_criterion)
- [Expected Value in Betting](https://www.pinnacle.com/en/betting-articles/Betting-Strategy/expected-value-in-betting/NBBWMXVCT9HWEFQK)

## 📧 Support

Issues? Open a GitHub issue or check the logs:
```bash
# View Render logs
render logs -f

# View local logs
python app.py
```

---

Built with ❤️ using FastAPI, SQLite, and API-Football
