import time
from datetime import datetime
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class CPBLRealTimeScraper:
    def __init__(self):
        self.base_url = "https://www.cpbl.com.tw"
        self.driver = None
        
        # 隊名對照表
        self.team_mapping = {
            "CTBC Brothers": "中信兄弟",
            "Uni-President 7-Eleven Lions": "統一7-ELEVEN獅",
            "Rakuten Monkeys": "樂天桃猿",
            "Fubon Guardians": "富邦悍將",
            "Wei Chuan Dragons": "味全龍",
            "TSG Hawks": "台鋼雄鷹",
            # 簡化版
            "Brothers": "中信兄弟",
            "Lions": "統一7-ELEVEN獅",
            "Monkeys": "樂天桃猿",
            "Guardians": "富邦悍將",
            "Dragons": "味全龍",
            "Hawks": "台鋼雄鷹",
            # 中文版
            "中信兄弟": "中信兄弟",
            "統一7-ELEVEN獅": "統一7-ELEVEN獅",
            "統一獅": "統一7-ELEVEN獅",
            "樂天桃猿": "樂天桃猿",
            "富邦悍將": "富邦悍將",
            "味全龍": "味全龍",
            "台鋼雄鷹": "台鋼雄鷹"
        }
        
        self.setup_driver()
    
    def setup_driver(self):
        """初始化 Chrome WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--headless')  

            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ WebDriver 初始化成功")
        except Exception as e:
            print(f"❌ WebDriver 初始化失敗: {e}")
    
    def get_today_games(self):
        """固定使用 JavaScript 搜尋"""
        if not self.driver:
            return []
        
        try:
            print("🌐 載入 CPBL 官網...")
            self.driver.get(self.base_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(5)  # 等頁面載入

            games = self.javascript_search()
            return self.validate_games(games)
        except Exception as e:
            print(f"❌ 獲取比賽資料失敗: {e}")
            return []
    
    def javascript_search(self):
        """用 JavaScript 搜尋比分元素"""
        js_script = """
        var games = [];
        var allElements = document.querySelectorAll('*');
        
        for (var i = 0; i < allElements.length; i++) {
            var elem = allElements[i];
            var text = elem.innerText || elem.textContent;
            if (!text) continue;
            
            var scoreMatch = text.match(/(\\d{1,2})\\s*[:：]\\s*(\\d{1,2})/);
            if (scoreMatch) {
                games.push({
                    text: text,
                    score1: scoreMatch[1],
                    score2: scoreMatch[2],
                    className: elem.className,
                    id: elem.id,
                    html: elem.outerHTML.substring(0, 200)  // 限制長度
                });
            }
        }
        return games;
        """
        
        results = self.driver.execute_script(js_script)
        print(f"🎯 JavaScript 找到 {len(results)} 個元素")
        
        games = []
        for result in results:
            game = self.parse_js_result(result)
            if game:
                games.append(game)
        return games
    
    def parse_js_result(self, result):
        """解析 JS 搜尋結果"""
        text = result.get("text", "")
        score1 = result.get("score1", "")
        score2 = result.get("score2", "")

        teams = self.extract_teams_from_text(text)
        if len(teams) >= 2:
            return {
                "away_team": teams[0],
                "home_team": teams[1],
                "away_score": score1,
                "home_score": score2,
                "status": self.determine_status(text),
                "game_time": self.extract_time(text),
                "inning": self.extract_inning(text),
                "element_class": result.get("className", ""),
                "element_id": result.get("id", ""),
                "element_html": result.get("html", ""),
                "source": "javascript_search"
            }
        return None
    
    def extract_teams_from_text(self, text):
        teams = []
        for team_key in sorted(self.team_mapping.keys(), key=len, reverse=True):
            if team_key in text and self.team_mapping[team_key] not in teams:
                teams.append(self.team_mapping[team_key])
                if len(teams) >= 2:
                    break
        return teams
    
    def determine_status(self, text):
        text_lower = text.lower()
        if any(k in text_lower for k in ["live", "進行中", "直播"]):
            return "🔴 進行中"
        elif any(k in text_lower for k in ["final", "結束", "終了", "比賽結束"]):
            return "✅ 已結束"
        elif any(k in text_lower for k in ["未開始", "upcoming"]):
            return "⏰ 未開始"
        return ""
    
    def extract_time(self, text):
        for pattern in [r"(\d{1,2}:\d{2})", r"(\d{2}/\d{2})", r"(\d{4}-\d{2}-\d{2})"]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def extract_inning(self, text):
        match = re.search(r"(\d+)局([上下半]?)", text)
        if match:
            return f"{match.group(1)}局{match.group(2) or ''}"
        return ""
    
    def validate_games(self, games):
        valid = []
        seen = set()
        for g in games:
            if not g: continue
            key = f"{g['away_team']}-{g['home_team']}-{g['away_score']}-{g['home_score']}"
            if key not in seen:
                seen.add(key)
                valid.append(g)
        return valid
    
    def save_to_json(self, games, filename="cpbl_live_scores.json"):
        data = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_games": len(games),
            "games": games,
            "source": "CPBL官網 + JavaScript 抓取"
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存 {filename}")
    
    def cleanup(self):
        if self.driver:
            self.driver.quit()
            print("✅ WebDriver 已關閉")

def main():
    scraper = CPBLRealTimeScraper()
    games = scraper.get_today_games()
    scraper.save_to_json(games)
    scraper.cleanup()

if __name__ == "__main__":
    main()
