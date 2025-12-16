from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import uvicorn
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from db import FTDDatabase
from scraper import scrape_todays_fixtures, research_recent_draws, calculate_ev
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use persistent storage path or fallback
db_path = os.getenv("DATABASE_PATH", "ftd.db")
db = FTDDatabase(db_path=db_path)

# Track if analysis is running
analysis_running = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("✅ Database initialized")
    
    # Run initial analysis on startup
    asyncio.create_task(run_initial_analysis())
    
    # Start background task unless explicitly disabled
    if not os.getenv("DISABLE_BACKGROUND"):
        logger.info("🚀 Starting background analysis task")
        asyncio.create_task(run_daily_analysis())
    else:
        logger.info("⏸️ Background analysis disabled")
    
    yield
    
    logger.info("👋 Shutting down")

app = FastAPI(lifespan=lifespan)

async def run_initial_analysis():
    """Run analysis immediately on startup"""
    global analysis_running
    if analysis_running:
        return
    
    analysis_running = True
    try:
        await perform_analysis()
    finally:
        analysis_running = False

async def run_daily_analysis():
    """Background task that runs analysis every 4 hours"""
    await asyncio.sleep(60)  # Wait 1 min after startup
    
    while True:
        try:
            await perform_analysis()
            logger.info("⏰ Next analysis in 4 hours")
            await asyncio.sleep(14400)  # 4 hours
        except Exception as e:
            logger.error(f"❌ Analysis loop error: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour on error

async def perform_analysis():
    """Core analysis logic"""
    today = datetime.now().strftime('%Y-%m-%d')
    day_of_week = datetime.now().strftime('%A')
    logger.info(f"🔥 Starting analysis for {today} ({day_of_week})")
    
    try:
        # Step 1: Research draw patterns
        logger.info("📊 Researching draw patterns...")
        draw_patterns = await research_recent_draws()
        await db.save_draw_patterns(draw_patterns)
        total_boost = sum(p.get('boost', 0) for p in draw_patterns) / max(1, len(draw_patterns))
        logger.info(f"✅ Pattern boost: +{total_boost:.1%}")
        
        # Step 2: Scrape today's fixtures
        logger.info("🔍 Scraping today's fixtures...")
        fixtures = await scrape_todays_fixtures()
        
        if not fixtures:
            logger.warning(f"⚠️ No fixtures found for {today}")
            
            # If it's Monday-Thursday, suggest checking on weekend
            if day_of_week in ['Monday', 'Tuesday', 'Wednesday', 'Thursday']:
                logger.info(f"💡 TIP: Most target leagues (Championship, Scottish) play on weekends")
                logger.info(f"    Try again Friday-Sunday for more matches!")
            
            return
        
        logger.info(f"✅ Found {len(fixtures)} fixtures")
        
        # Step 3: Calculate EV for each match
        logger.info("🧮 Calculating EV for matches...")
        predictions = []
        for fixture in fixtures:
            try:
                pred = await calculate_ev(fixture, total_boost)
                if pred['ev_percent'] > 5:  # Only save positive EV
                    pred['date'] = today
                    predictions.append(pred)
            except Exception as e:
                logger.error(f"❌ Error calculating EV for {fixture.get('home', '?')} vs {fixture.get('away', '?')}: {e}")
                continue
        
        # Step 4: Save predictions
        if predictions:
            await db.save_predictions(predictions)
            logger.info(f"✅ Saved {len(predictions)} predictions (EV > 5%)")
        else:
            logger.warning(f"⚠️ No positive EV predictions today")
        
        # Step 5: Run backtest
        logger.info("📈 Running backtest analysis...")
        await db.run_backtest_analysis()
        
        logger.info(f"✅ Analysis complete: {len(predictions)} picks | +{total_boost:.1%} boost")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {str(e)}", exc_info=True)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    # Prevent caching
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    try:
        predictions = await db.get_todays_predictions()
        stats = await db.get_performance_stats()
        today_date = datetime.now().strftime('%Y-%m-%d')
        day_name = datetime.now().strftime('%A')
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>FTD Analytics - 15 Daily Draw Picks</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta name="theme-color" content="#0f0f23">
            <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
            <meta http-equiv="Pragma" content="no-cache">
            <meta http-equiv="Expires" content="0">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                * {{ touch-action: manipulation; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #0f0f23; color: white; }}
                .header {{ text-align: center; margin-bottom: 40px; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
                .stat-card {{ background: #1a1a2e; padding: 20px; border-radius: 12px; text-align: center; }}
                .stat-big {{ font-size: 2.5em; font-weight: bold; color: #4ade80; }}
                table {{ width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 12px; overflow: hidden; margin-bottom: 20px; }}
                th, td {{ padding: 16px; text-align: left; border-bottom: 1px solid #333; }}
                th {{ background: #16213e; font-weight: 600; }}
                .ev-positive {{ color: #4ade80; font-weight: bold; }}
                .ev-negative {{ color: #ef4444; }}
                .ev-medium {{ color: #fbbf24; }}
                .refresh {{ position: fixed; top: 20px; right: 20px; background: #3b82f6; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; z-index: 1000; font-size: 16px; }}
                .refresh:hover {{ background: #2563eb; }}
                .chart-container {{ background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 20px; height: 300px; }}
                .action-btn {{ background: #10b981; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin: 0 4px; font-size: 13px; }}
                .action-btn:hover {{ background: #059669; }}
                .action-btn.miss {{ background: #ef4444; }}
                .action-btn.miss:hover {{ background: #dc2626; }}
                .no-matches {{ color: #f59e0b; text-align: center; padding: 60px; font-size: 1.2em; background: #1a1a2e; border-radius: 12px; }}
                .loading {{ text-align: center; padding: 40px; color: #60a5fa; font-size: 1.1em; }}
                .manual-trigger {{ text-align: center; margin: 20px 0; }}
                .trigger-btn {{ background: #8b5cf6; color: white; border: none; padding: 14px 28px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 600; }}
                .trigger-btn:hover {{ background: #7c3aed; }}
                @media (max-width: 768px) {{ 
                    body {{ padding: 10px; }} 
                    th, td {{ padding: 12px 8px; font-size: 14px; }}
                    .stat-big {{ font-size: 2em; }}
                    .refresh {{ padding: 10px 16px; font-size: 14px; }}
                }}
            </style>
        </head>
        <body>
            <button class="refresh" onclick="location.reload()">🔄 Refresh</button>
            <div class="header">
                <h1>🎯 FTD Analytics</h1>
                <p>AI Draw Detection | Hit Rate: {stats['hit_rate']}% | TODAY: {today_date}</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div>Total Bets</div>
                    <div class="stat-big">{stats['total']}</div>
                </div>
                <div class="stat-card">
                    <div>Hit Rate</div>
                    <div class="stat-big">{stats['hit_rate']}%</div>
                </div>
                <div class="stat-card">
                    <div>Avg EV</div>
                    <div class="stat-big">+{stats['avg_ev']}%</div>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="performanceChart"></canvas>
            </div>
            
            <div class="manual-trigger">
                <button class="trigger-btn" onclick="triggerAnalysis()">⚡ Run Analysis Now</button>
            </div>
            
            <h2>🎯 TODAY'S TOP 15 DRAW PICKS</h2>
            <table>
                <tr><th>ID</th><th>Time</th><th>League</th><th>Match</th><th>Odds</th><th>Kelly</th><th>EV%</th><th>Actions</th></tr>
        """
        
        if predictions:
            for pred in predictions:
                pred_id, kickoff, league, home, away, odds, prob, ev, reasons, liquidity = pred
                kelly_stake = await db.kelly_stake(1000, odds, prob)
                
                # Color code EV
                if ev > 10:
                    ev_class = "ev-positive"
                elif ev > 5:
                    ev_class = "ev-medium"
                else:
                    ev_class = "ev-negative"
                
                html += f"""
                <tr>
                    <td>{pred_id}</td>
                    <td>{kickoff}</td>
                    <td>{league}</td>
                    <td><strong>{home}</strong> vs <strong>{away}</strong></td>
                    <td>${odds:.2f}</td>
                    <td>${kelly_stake:.1f}</td>
                    <td class="{ev_class}">+{ev}%</td>
                    <td>
                        <button class="action-btn" onclick="markResult({pred_id},'draw')">✅ Win</button>
                        <button class="action-btn miss" onclick="markResult({pred_id},'loss')">❌ Loss</button>
                    </td>
                </tr>
                """
        else:
            html += f"""
                <tr><td colspan='8' class="no-matches">
                    🔍 NO HIGH EV DRAWS TODAY ({today_date})<br>
                    <small>This is normal for {datetime.now().strftime('%A')}s</small><br>
                    <small style="color: #60a5fa;">Championship & Scottish leagues play mostly on weekends</small><br>
                    <small style="color: #6b7280;">Next fixtures: Friday-Sunday | Try "Run Analysis Now" on match days</small>
                </td></tr>
            """
        
        html += f"""
                </table>
                
                <script>
                    if ('serviceWorker' in navigator) {{
                        navigator.serviceWorker.register('/sw.js').catch(e => console.log('SW registration failed'));
                    }}
                    
                    const hits = {stats['hits']};
                    const total = {stats['total']};
                    const misses = Math.max(0, total - hits);
                    
                    // Only render chart if there's data
                    const chartCanvas = document.getElementById('performanceChart');
                    if (chartCanvas && (hits > 0 || misses > 0)) {{
                        new Chart(chartCanvas.getContext('2d'), {{
                            type: 'doughnut', 
                            data: {{
                                labels: ['Hits', 'Misses'], 
                                datasets: [{{
                                    data: [hits, misses],
                                    backgroundColor: ['#4ade80', '#ef4444'],
                                    borderWidth: 0
                                }}]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {{
                                    legend: {{
                                        labels: {{
                                            color: 'white',
                                            font: {{ size: 14 }}
                                        }}
                                    }},
                                    tooltip: {{
                                        callbacks: {{
                                            label: function(context) {{
                                                const label = context.label || '';
                                                const value = context.parsed || 0;
                                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                                return label + ': ' + value + ' (' + percentage + '%)';
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }});
                    }} else {{
                        // Show placeholder message when no data
                        chartCanvas.parentElement.innerHTML = `
                            <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #6b7280;">
                                <div style="text-align: center;">
                                    <div style="font-size: 3em; margin-bottom: 10px;">📊</div>
                                    <div>No performance data yet</div>
                                    <div style="font-size: 0.9em; margin-top: 5px;">Mark predictions as wins/losses to see stats</div>
                                </div>
                            </div>
                        `;
                    }}
                    
                    async function markResult(id, r) {{
                        try {{
                            await fetch(`/result/${{id}}`, {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                body: `result=${{r}}`
                            }});
                            location.reload();
                        }} catch(e) {{
                            alert('Failed to update result');
                        }}
                    }}
                    
                    async function triggerAnalysis() {{
                        const btn = event.target;
                        btn.disabled = true;
                        btn.textContent = '⏳ Running...';
                        
                        try {{
                            const response = await fetch('/trigger-analysis', {{ method: 'POST' }});
                            if (response.ok) {{
                                alert('Analysis started! Refresh in 30 seconds to see results.');
                                setTimeout(() => location.reload(), 30000);
                            }} else {{
                                alert('Analysis failed. Check logs.');
                            }}
                        }} catch(e) {{
                            alert('Error triggering analysis');
                        }} finally {{
                            btn.disabled = false;
                            btn.textContent = '⚡ Run Analysis Now';
                        }}
                    }}
                    
                    // Auto-refresh every 5 minutes (instead of 2)
                    setTimeout(() => location.reload(), 300000);
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=html)
        
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}", exc_info=True)
        return HTMLResponse(content=f"""
            <html>
                <body style="background: #0f0f23; color: white; font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>❌ Error Loading Dashboard</h1>
                    <p>{str(e)}</p>
                    <button onclick="location.reload()" style="padding: 12px 24px; font-size: 16px; cursor: pointer;">
                        🔄 Retry
                    </button>
                </body>
            </html>
        """, status_code=500)

@app.post("/trigger-analysis")
async def trigger_analysis():
    """Manually trigger analysis"""
    global analysis_running
    
    if analysis_running:
        return JSONResponse({"status": "already_running"}, status_code=409)
    
    asyncio.create_task(run_initial_analysis())
    return JSONResponse({"status": "started"})

@app.get("/manifest.json")
async def manifest():
    return {
        "name": "FTD Analytics",
        "short_name": "FTD",
        "description": "AI Football Draw Predictions",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f0f23",
        "theme_color": "#4ade80",
        "icons": [{
            "src": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48dGV4dCB5PSIuOWVtIiBmb250LXNpemU9IjkwIj7wn6q8PC90ZXh0Pjwvc3ZnPg==",
            "sizes": "192x192",
            "type": "image/png"
        }]
    }

@app.get("/sw.js")
async def service_worker():
    return HTMLResponse(content="""
    self.addEventListener('install', e => {
      e.waitUntil(
        caches.open('ftd-v1').then(cache => 
          cache.addAll(['/'])
        )
      );
    });
    self.addEventListener('fetch', e => {
      e.respondWith(caches.match(e.request).then(response => response || fetch(e.request)));
    });
    """, media_type="application/javascript")

@app.post("/result/{pred_id}")
async def mark_result(pred_id: int, result: str = Form(...)):
    try:
        await db.update_prediction_result(pred_id, result)
        await db.run_backtest_analysis()
        return {"status": "updated"}
    except Exception as e:
        logger.error(f"❌ Error updating result: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)