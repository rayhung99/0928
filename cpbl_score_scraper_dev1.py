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
        
        # 英文隊名對照表
        self.team_mapping = {
            "CTBC Brothers": "中信兄弟",
            "Uni-President 7-Eleven Lions": "統一7-ELEVEN獅",
            "Rakuten Monkeys": "樂天桃猿", 
            "Fubon Guardians": "富邦悍將",
            "Wei Chuan Dragons": "味全龍",
            "TSG Hawks": "台鋼雄鷹",
            # 簡化版本
            "Brothers": "中信兄弟",
            "Lions": "統一7-ELEVEN獅", 
            "Monkeys": "樂天桃猿",
            "Guardians": "富邦悍將",
            "Dragons": "味全龍",
            "Hawks": "台鋼雄鷹",
            # 中文版本
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
        """初始化Chrome WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--headless')  # 無頭模式

            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ WebDriver初始化成功")
            return True
        except Exception as e:
            print(f"❌ WebDriver初始化失敗: {e}")
            return False
    
    def get_today_games(self):
        """固定使用 JavaScript 搜尋比賽資料"""
        if not self.driver:
            print("❌ WebDriver未初始化")
            return []
        
        try:
            print("🌐 正在載入CPBL官網...")
            self.driver.get(self.base_url)
            
            # 等待頁面載入完成
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            print("⏳ 等待頁面內容載入...")
            time.sleep(5)

            # 直接使用 JavaScript 搜尋
            games = self.javascript_search()
            games = self.validate_games(games)

            # 每場比賽加上來源
            for game in games:
                game["source"] = "javascript_search"

            return games
        except Exception as e:
            print(f"❌ 獲取比賽資料失敗: {e}")
            return []
    
    def javascript_search(self):
        """使用JavaScript直接搜尋比賽資料"""
        games = []
        try:
            js_script = """
            var games = [];
            var allElements = document.querySelectorAll('*');
            
            for (var i = 0; i < allElements.length; i++) {
                var elem = allElements[i];
                var text = elem.innerText || elem.textContent;
                if (!text) continue;
                
                var scoreMatch = text.match(/(\\d{1,2})\\s*[:：]\\s*(\\d{1,2})/);
                if (scoreMatch) {
                    var hasGameStatus = /比賽結束|進行中|未開始|結束|live/i.test(text);
                    var rect = elem.getBoundingClientRect();
                    var hasReasonableSize = rect.width > 100 && rect.height > 50;
                    
                    if (hasGameStatus || hasReasonableSize) {
                        games.push({
                            text: text,
                            score1: scoreMatch[1],
                            score2: scoreMatch[2],
                            className: elem.className,
                            id: elem.id
                        });
                    }
                }
            }
            return games;
            """
            
            js_results = self.driver.execute_script(js_script)
            print(f"🎯 JavaScript找到 {len(js_results)} 個潛在比賽元素")
            
            for result in js_results:
                game_data = self.parse_js_result(result)
                if game_data:
                    games.append(game_data)
            return games
        except Exception as e:
            print(f"❌ JavaScript搜尋錯誤: {e}")
            return []
    
    def parse_js_result(self, result):
        """解析JavaScript搜尋結果"""
        try:
            text = result.get('text', '')
            score1 = result.get('score1', '')
            score2 = result.get('score2', '')

            teams = self.extract_teams_from_text(text)
            if len(teams) >= 2:
                return {
                    'away_team': teams[0],
                    'home_team': teams[1], 
                    'away_score': score1,
                    'home_score': score2,
                    'status': self.determine_status(text),
                    'game_time': self.extract_time(text),
                    'inning': self.extract_inning(text),
                    'source': 'javascript_search'
                }
            return None
        except Exception:
            return None
    
    def extract_teams_from_text(self, text):
        """從文字中提取隊伍名稱"""
        teams = []
        sorted_teams = sorted(self.team_mapping.keys(), key=len, reverse=True)
        for team_key in sorted_teams:
            if team_key in text and self.team_mapping[team_key] not in teams:
                teams.append(self.team_mapping[team_key])
                if len(teams) >= 2:
                    break
        return teams
    
    def determine_status(self, text):
        """判斷比賽狀態"""
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ['live', '進行中', '直播']):
            return '🔴 進行中'
        elif any(keyword in text_lower for keyword in ['final', '結束', '終了', '比賽結束']):
            return '✅ 已結束'
        elif any(keyword in text_lower for keyword in ['未開始', 'upcoming']):
            return '⏰ 未開始'
        else:
            return '✅ 已結束'
    
    def extract_time(self, text):
        """提取時間資訊"""
        time_patterns = [r'(\d{1,2}:\d{2})', r'(\d{2}/\d{2})', r'(\d{4}-\d{2}-\d{2})']
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ''
    
    def extract_inning(self, text):
        """提取局數資訊"""
        inning_match = re.search(r'(\d+)局([上下半]?)', text)
        if inning_match:
            return f"{inning_match.group(1)}局{inning_match.group(2) or ''}"
        return ''
    
    def validate_games(self, games):
        """驗證比賽資料"""
        valid_games = []
        seen_games = set()
        for game in games:
            if not self.is_valid_game(game):
                continue
            game_id = f"{game['away_team']}-{game['home_team']}-{game['away_score']}-{game['home_score']}"
            if game_id not in seen_games:
                seen_games.add(game_id)
                valid_games.append(game)
        print(f"✅ 驗證完成，保留 {len(valid_games)} 場有效比賽")
        return valid_games
    
    def is_valid_game(self, game):
        """檢查比賽資料是否有效"""
        if not game or not isinstance(game, dict):
            return False
        required_fields = ['away_team', 'home_team', 'away_score', 'home_score']
        for field in required_fields:
            if field not in game or not game[field]:
                return False
        valid_teams = set(self.team_mapping.values())
        if game['away_team'] not in valid_teams or game['home_team'] not in valid_teams:
            return False
        if game['away_team'] == game['home_team']:
            return False
        return True
    
    def display_games(self, games):
        """顯示比賽結果"""
        if not games:
            print("\n" + "="*60)
            print("🏟️ 中華職棒即時比分")
            print("="*60)
            print("📅 今日無比賽或無法獲取比分")
            return
        
        print("\n" + "="*70)
        print("🏟️ 中華職棒即時比分")
        print("="*70)
        print(f"📅 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 比賽場數: {len(games)}")
        print("="*70)
        
        for i, game in enumerate(games, 1):
            print(f"\n🏟️ 第{i}場")
            print(f"   客隊: {game['away_team']:15} {game['away_score']:>3}")
            print(f"   主隊: {game['home_team']:15} {game['home_score']:>3}")
            print(f"   狀態: {game['status']}")
            if game.get('inning'):
                print(f"   局數: {game['inning']}")
            if game.get('game_time'):
                print(f"   時間: {game['game_time']}")
            print(f"   來源: {game['source']}")
            print("-" * 50)
        print("="*70)
    
    def save_to_json(self, games, filename='cpbl_live_scores.json'):
        """保存到JSON檔案"""
        try:
            data = {
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_games': len(games),
                'games': games,
                'source': 'CPBL官網即時爬取'
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 資料已保存至 {filename}")
        except Exception as e:
            print(f"❌ 保存失敗: {e}")
    
    def cleanup(self):
        """清理資源"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ WebDriver已關閉")
            except:
                pass

def main():
    print("🏟️ 中華職棒即時比分爬蟲 v5.0")
    print("="*50)
    print("🎯 固定使用 JavaScript 搜尋")
    
    scraper = CPBLRealTimeScraper()
    if not scraper.driver:
        print("❌ 初始化失敗，程式結束")
        return
    
    games = scraper.get_today_games()
    scraper.display_games(games)
    if games:
        scraper.save_to_json(games)
    scraper.cleanup()

if __name__ == "__main__":
    main()
