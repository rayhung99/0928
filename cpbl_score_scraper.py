import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class CPBLRealTimeScraper:
    def __init__(self):
        self.url = "https://www.cpbl.com.tw"
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(options=opts)

    def get_today_games(self, retries=3):
        for _ in range(retries):
            try:
                self.driver.get(self.url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "game_item"))
                )
                return self.parse_games()
            except Exception:
                time.sleep(2)
        print("無法取得比賽資料")
        return []

    def parse_games(self):
        js = """
        function getStatus(el){
            if(el.classList.contains('final')) return '✅ 已結束';
            if(el.classList.contains('live')) return '🔴 進行中';
            if(el.classList.contains('canceled')) return '❌ 取消';
            return '⏰ 未開始';
        }
        const games = [...document.querySelectorAll('.game_item'), ...document.querySelectorAll('.game_canceled')];
        return games.map(g=>{
            const teams = g.querySelectorAll('.team_name');
            const scores = g.querySelectorAll('.score');
            return {
                away_team: teams[0]?.textContent?.trim() || '',
                home_team: teams[1]?.textContent?.trim() || '',
                away_score: scores[0]?.textContent?.trim() || '0',
                home_score: scores[1]?.textContent?.trim() || '0',
                status: getStatus(g),
                inning: g.querySelector('.inning')?.textContent?.trim() || '',
                game_time: g.querySelector('.game_time')?.textContent?.trim() || '',
                element_class: g.className,
                element_id: g.id,
                game_link: g.querySelector('a')?.href || '',
                source: 'javascript'
            };
        });
        """
        games = self.driver.execute_script(js)
        # 去除重複比賽
        seen = set()
        return [g for g in games if g and f"{g['away_team']}-{g['home_team']}" not in seen and not seen.add(f"{g['away_team']}-{g['home_team']}")]

    def save_json(self, games, filename="cpbl_live_scores.json"):
        data = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_games": len(games),
            "games": games,
            "source": "CPBL官網 + JS抓取"
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def cleanup(self):
        if self.driver:
            self.driver.quit()

if __name__ == "__main__":
    scraper = CPBLRealTimeScraper()
    games = scraper.get_today_games()
    scraper.save_json(games)
    scraper.cleanup()
