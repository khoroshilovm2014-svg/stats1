# blitz_stats_ultimate.py
import requests
import json
import time
from datetime import datetime
import io
import sys
import signal
import sqlite3
import os
from typing import Dict, List, Optional
import urllib3
import warnings

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

BOT_TOKEN = "8575145131:AAERhzW7TTjf3NT1aFEGfkjuDGN_ftMuAvw"
WG_API_KEY = "3c2a90c4b97e6e4660b62117dc8bfe2e"
ADMIN_IDS = [7635015201]
CHANNEL_USERNAME = "@freeaccountanksblitz"

class BlitzBotUltimate:
    def __init__(self):
        self.bot_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
        self.wg_url = "https://api.wotblitz.eu/wotb"
        self.offset = 0
        self.user_data = {}
        self.running = True
        
        # Инициализация базы данных
        self.init_database()
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def init_database(self):
        """Инициализация базы данных SQLite"""
        db_file = 'bot_data.db'
        
        # Если база повреждена - удаляем и создаем новую
        if os.path.exists(db_file):
            try:
                test_conn = sqlite3.connect(db_file)
                test_cursor = test_conn.cursor()
                test_cursor.execute('SELECT 1')
                test_cursor.close()
                test_conn.close()
            except sqlite3.Error:
                try:
                    os.remove(db_file)
                except:
                    pass
        
        # Создаем новое соединение с базой данных
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Таблица пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def signal_handler(self, signum, frame):
        print("\n🛑 Получен сигнал остановки...")
        self.running = False
        time.sleep(1)
        print("👋 Бот остановлен")
        sys.exit(0)
    
    def make_request(self, url, params):
        """Безопасный запрос к API"""
        try:
            response = requests.get(url, params=params, timeout=10, verify=False)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def search_player(self, nickname):
        """Поиск игрока по никнейму"""
        try:
            data = self.make_request(
                f"{self.wg_url}/account/list/",
                {
                    'application_id': WG_API_KEY,
                    'search': nickname,
                    'limit': 5
                }
            )
            
            if data and data.get('status') == 'ok' and data.get('data'):
                for player in data['data']:
                    if player.get('nickname', '').lower() == nickname.lower():
                        return player['account_id']
                # Если точного совпадения нет, берем первого
                if data['data']:
                    return data['data'][0]['account_id']
            
            return None
        except:
            return None
    
    def get_player_stats(self, account_id):
        """Получение статистики игрока"""
        try:
            data = self.make_request(
                f"{self.wg_url}/account/info/",
                {
                    'application_id': WG_API_KEY,
                    'account_id': account_id,
                    'fields': 'nickname,created_at,last_battle_time,statistics.all'
                }
            )
            
            if data and data.get('status') == 'ok' and 'data' in data:
                player_data = data['data'].get(str(account_id))
                if not player_data:
                    return None
                
                stats = player_data.get('statistics', {}).get('all', {})
                
                battles = stats.get('battles', 0)
                wins = stats.get('wins', 0)
                damage = stats.get('damage_dealt', 0)
                survived = stats.get('survived_battles', 0)
                hits = stats.get('hits', 0)
                shots = stats.get('shots', 0)
                frags = stats.get('frags', 0)
                max_xp = stats.get('max_xp', 0)
                
                # Расчеты
                winrate = (wins / battles * 100) if battles > 0 else 0
                avg_damage = (damage / battles) if battles > 0 else 0
                survival = (survived / battles * 100) if battles > 0 else 0
                accuracy = (hits / shots * 100) if shots > 0 else 0
                avg_frags = (frags / battles) if battles > 0 else 0
                
                return {
                    'nickname': player_data.get('nickname', 'Неизвестно'),
                    'created_at': player_data.get('created_at', 0),
                    'last_battle': player_data.get('last_battle_time', 0),
                    'battles': battles,
                    'wins': wins,
                    'winrate': winrate,
                    'damage': avg_damage,
                    'survival': survival,
                    'accuracy': accuracy,
                    'frags': avg_frags,
                    'max_xp': max_xp
                }
        except:
            return None
        return None
    
    def get_player_tanks(self, account_id):
        """Получение списка танков игрока"""
        try:
            data = self.make_request(
                f"{self.wg_url}/tanks/stats/",
                {
                    'application_id': WG_API_KEY,
                    'account_id': account_id,
                    'fields': 'tank_id,all.battles,all.wins,all.damage_dealt'
                }
            )
            
            if data and data.get('status') == 'ok' and 'data' in data:
                tanks_data = data['data'].get(str(account_id), [])
                
                tanks = []
                for tank in tanks_data:
                    if isinstance(tank, dict):
                        tank_info = {
                            'tank_id': tank.get('tank_id'),
                            'battles': tank.get('all', {}).get('battles', 0),
                            'wins': tank.get('all', {}).get('wins', 0),
                            'damage': tank.get('all', {}).get('damage_dealt', 0)
                        }
                        tanks.append(tank_info)
                
                return tanks
            
            return []
            
        except:
            return []
    
    def get_tank_info(self, tank_ids):
        """Получение информации о танках"""
        if not tank_ids:
            return {}
        
        try:
            tank_ids_str = ','.join(map(str, tank_ids[:100]))
            
            data = self.make_request(
                f"{self.wg_url}/encyclopedia/vehicles/",
                {
                    'application_id': WG_API_KEY,
                    'tank_id': tank_ids_str,
                    'fields': 'name,tier,type,nation,is_premium'
                }
            )
            
            if data and data.get('status') == 'ok' and 'data' in data:
                return data['data']
            return {}
            
        except:
            return {}
    
    def get_top_tanks(self, tanks, tank_info, limit=10):
        """Получение топ танков по боям"""
        tank_stats = []
        
        for tank in tanks:
            tank_id = tank['tank_id']
            info = tank_info.get(str(tank_id))
            
            if info and tank['battles'] > 0:
                winrate = (tank['wins'] / tank['battles'] * 100) if tank['battles'] > 0 else 0
                avg_damage = tank['damage'] / tank['battles'] if tank['battles'] > 0 else 0
                
                tank_stats.append({
                    'name': info.get('name', f'Танк {tank_id}'),
                    'tier': info.get('tier', 0),
                    'battles': tank['battles'],
                    'wins': tank['wins'],
                    'winrate': winrate,
                    'damage': avg_damage,
                    'total_damage': tank['damage']
                })
        
        # Сортируем по количеству боёв
        tank_stats.sort(key=lambda x: x['battles'], reverse=True)
        return tank_stats[:limit]
    
    def format_main_stats(self, stats):
        """Форматирование основной статистики"""
        created = datetime.fromtimestamp(stats['created_at']).strftime('%d.%m.%Y %H:%M')
        last = datetime.fromtimestamp(stats['last_battle']).strftime('%d.%m.%Y %H:%M')
        
        message = f"👤 *{stats['nickname']}*\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n"
        message += f"📅 Создан: `{created}`\n"
        message += f"🕒 Последний бой: `{last}`\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n"
        message += f"⚔️ Боёв: `{stats['battles']:,}`\n".replace(',', ' ')
        message += f"🏆 Побед: `{stats['wins']:,}` (`{stats['winrate']:.2f}%`)\n".replace(',', ' ')
        message += f"💥 Ср. урон: `{int(stats['damage'])}`\n"
        message += f"🛡 Выживаемость: `{stats['survival']:.2f}%`\n"
        message += f"🎯 Точность: `{stats['accuracy']:.2f}%`\n"
        message += f"🎖 Фрагов за бой: `{stats['frags']:.2f}`\n"
        message += f"🌟 Макс. опыт: `{int(stats['max_xp'])}`\n"
        
        return message
    
    def format_top_tanks(self, nickname, top_tanks):
        """Форматирование топа танков"""
        if not top_tanks:
            return "📊 *Топ танков:*\n\nНет данных о танках"
        
        message = f"🏆 *Топ танков игрока {nickname}:*\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n\n"
        
        for i, tank in enumerate(top_tanks, 1):
            message += f"{i}. *{tank['name']}*\n"
            message += f"   ⚔️ Боёв: `{tank['battles']}`\n"
            message += f"   🏆 Побед: `{tank['wins']}` (`{tank['winrate']:.1f}%`)\n"
            message += f"   💥 Ср. урон: `{int(tank['damage'])}`\n"
            if i < len(top_tanks):
                message += "   ─────────────\n"
        
        return message
    
    def format_all_tanks(self, nickname, tanks, tank_info):
        """Форматирование всех танков"""
        if not tanks:
            return "🚙 *Весь ангар:*\n\nТанки не найдены"
        
        message = f"🚙 *Весь ангар игрока {nickname}:*\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n\n"
        
        # Группируем танки по уровню
        tanks_by_tier = {}
        
        for tank in tanks:
            tank_id = tank['tank_id']
            info = tank_info.get(str(tank_id))
            
            if info:
                tier = info.get('tier', 0)
                name = info.get('name', f'Танк {tank_id}')
                is_premium = info.get('is_premium', False)
                
                if tier not in tanks_by_tier:
                    tanks_by_tier[tier] = []
                
                prefix = "💰 " if is_premium else "• "
                tanks_by_tier[tier].append(f"{prefix}{name}")
        
        # Сортируем по уровню (от высокого к низкому)
        for tier in sorted(tanks_by_tier.keys(), reverse=True):
            message += f"*[Уровень {tier}]*\n"
            
            # Сортируем танки по названию
            for tank_name in sorted(tanks_by_tier[tier]):
                message += f"{tank_name}\n"
            
            message += "\n"
        
        message += f"📊 Всего танков: {len(tanks)}"
        
        return message
    
    def create_main_keyboard(self):
        """Создание основной клавиатуры с кнопками"""
        return {
            "inline_keyboard": [
                [
                    {"text": "📊 Общее", "callback_data": "main_stats"},
                    {"text": "🏆 Топ Танков", "callback_data": "top_tanks"}
                ],
                [
                    {"text": "📁 Стат. в файл", "callback_data": "stats_file"},
                    {"text": "🚙 Весь ангар", "callback_data": "all_tanks"}
                ]
            ]
        }
    
    def generate_stats_file(self, nickname, stats, tanks, tank_info):
        """Генерация файла со статистикой"""
        created = datetime.fromtimestamp(stats['created_at']).strftime('%d.%m.%Y %H:%M')
        last = datetime.fromtimestamp(stats['last_battle']).strftime('%d.%m.%Y %H:%M')
        
        content = f"👤 ПОЛНАЯ СТАТИСТИКА ИГРОКА: {nickname}\n"
        content += "=" * 60 + "\n\n"
        
        content += f"📅 Дата создания аккаунта: {created}\n"
        content += f"🕒 Последний бой: {last}\n\n"
        
        content += "📊 ОСНОВНАЯ СТАТИСТИКА:\n"
        content += "-" * 40 + "\n"
        content += f"Всего боёв: {stats['battles']:,}\n".replace(',', ' ')
        content += f"Побед: {stats['wins']:,} ({stats['winrate']:.2f}%)\n".replace(',', ' ')
        content += f"Средний урон за бой: {int(stats['damage'])}\n"
        content += f"Выживаемость: {stats['survival']:.2f}%\n"
        content += f"Точность стрельбы: {stats['accuracy']:.2f}%\n"
        content += f"Фрагов за бой: {stats['frags']:.2f}\n"
        content += f"Максимальный опыт за бой: {stats['max_xp']}\n\n"
        
        if tanks:
            # Получаем топ танков
            top_tanks = self.get_top_tanks(tanks, tank_info, 20)
            
            content += "🏆 ТОП 20 ТАНКОВ ПО КОЛИЧЕСТВУ БОЁВ:\n"
            content += "=" * 60 + "\n\n"
            
            for i, tank in enumerate(top_tanks, 1):
                content += f"{i:2d}. {tank['name']}\n"
                content += f"    Боёв: {tank['battles']}\n"
                content += f"    Побед: {tank['wins']} ({tank['winrate']:.1f}%)\n"
                content += f"    Ср. урон: {int(tank['damage'])}\n"
                content += f"    Всего урона: {tank['total_damage']:,}\n".replace(',', ' ')
                if i < len(top_tanks):
                    content += "    " + "-" * 30 + "\n"
            
            content += f"\nВсего танков в ангаре: {len(tanks)}\n"
        
        content += "\n" + "=" * 60 + "\n"
        content += f"Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        content += "Бот: @freeaccountanksblitz"
        
        return content
    
    def generate_all_tanks_file(self, nickname, tanks, tank_info):
        """Генерация файла со всеми танками"""
        content = f"🚙 ПОЛНЫЙ СПИСОК ТАНКОВ ИГРОКА: {nickname}\n"
        content += "=" * 60 + "\n\n"
        
        if not tanks:
            content += "Танки не найдены\n"
            return content
        
        # Сортируем танки по уровню и названию
        sorted_tanks = []
        for tank in tanks:
            tank_id = tank['tank_id']
            info = tank_info.get(str(tank_id))
            
            if info:
                sorted_tanks.append({
                    'id': tank_id,
                    'tier': info.get('tier', 0),
                    'name': info.get('name', f'Танк {tank_id}'),
                    'type': info.get('type', 'unknown'),
                    'nation': info.get('nation', 'unknown'),
                    'is_premium': info.get('is_premium', False),
                    'battles': tank.get('battles', 0),
                    'wins': tank.get('wins', 0),
                    'damage': tank.get('damage', 0)
                })
        
        sorted_tanks.sort(key=lambda x: (x['tier'], x['name']), reverse=True)
        
        # Выводим танки
        current_tier = None
        for tank in sorted_tanks:
            if tank['tier'] != current_tier:
                current_tier = tank['tier']
                content += f"\n[Уровень {tank['tier']}]\n"
                content += "-" * 50 + "\n"
            
            premium_mark = "💰 " if tank['is_premium'] else "  "
            winrate = (tank['wins'] / tank['battles'] * 100) if tank['battles'] > 0 else 0
            avg_damage = tank['damage'] / tank['battles'] if tank['battles'] > 0 else 0
            
            content += f"{premium_mark}{tank['name']}\n"
            content += f"    Тип: {tank['type']}, Нация: {tank['nation']}\n"
            if tank['battles'] > 0:
                content += f"    Боёв: {tank['battles']}, Побед: {tank['wins']} ({winrate:.1f}%)\n"
                content += f"    Ср. урон: {int(avg_damage)}, Всего урона: {tank['damage']:,}\n".replace(',', ' ')
            content += f"    ID танка: {tank['id']}\n"
        
        content += f"\n" + "=" * 60 + "\n"
        content += f"Всего танков: {len(tanks)}\n"
        
        premium_count = sum(1 for tank in sorted_tanks if tank['is_premium'])
        if premium_count > 0:
            content += f"Премиум танков: {premium_count}\n"
        
        content += f"\nСгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        content += "Бот: @freeaccountanksblitz"
        
        return content
    
    def send_message(self, chat_id, text, keyboard=None, parse_mode='Markdown'):
        try:
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            if keyboard:
                payload['reply_markup'] = json.dumps(keyboard)
            
            requests.post(f"{self.bot_url}/sendMessage", json=payload, timeout=10)
        except:
            pass
    
    def send_document(self, chat_id, content, filename, caption=""):
        try:
            files = {'document': (filename, io.BytesIO(content.encode('utf-8')), 'text/plain')}
            data = {'chat_id': chat_id, 'caption': caption}
            requests.post(f"{self.bot_url}/sendDocument", files=files, data=data, timeout=30)
        except:
            pass
    
    def process_message(self, message):
        """Обработка входящих сообщений"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        text = message.get('text', '').strip()
        
        # Добавляем пользователя в базу
        try:
            username = message['from'].get('username')
            first_name = message['from'].get('first_name')
            last_name = message['from'].get('last_name')
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            self.conn.commit()
        except:
            pass
        
        if text == '/start':
            welcome = (
                "🎮 *WoT BLITZ STATS BOT*\n\n"
                "Привет, танкист! 👋\n\n"
                "Я покажу тебе статистику и ангар любого игрока WoT Blitz.\n\n"
                "*Как пользоваться:*\n"
                "Просто отправь мне никнейм игрока\n\n"
                "*Пример:* `PRO_100_IGROK`\n\n"
                "Поддержи канал: @freeaccountanksblitz"
            )
            self.send_message(chat_id, welcome)
            return
        
        if not text or len(text) < 3:
            self.send_message(chat_id, "❌ Никнейм должен содержать минимум 3 символа")
            return
        
        self.send_message(chat_id, f"🔍 Ищу игрока `{text}`...")
        
        account_id = self.search_player(text)
        if not account_id:
            self.send_message(chat_id, f"❌ Игрок `{text}` не найден.")
            return
        
        stats = self.get_player_stats(account_id)
        if not stats:
            self.send_message(chat_id, f"❌ Не удалось получить статистику для `{text}`")
            return
        
        # Получаем танки игрока
        tanks = self.get_player_tanks(account_id)
        tank_info = {}
        if tanks:
            tank_ids = [tank['tank_id'] for tank in tanks]
            tank_info = self.get_tank_info(tank_ids)
        
        # Сохраняем данные
        self.user_data[f"{chat_id}_data"] = {
            'nickname': text,
            'account_id': account_id,
            'stats': stats,
            'tanks': tanks,
            'tank_info': tank_info
        }
        
        # Отправляем основную статистику
        main_message = self.format_main_stats(stats)
        self.send_message(chat_id, main_message)
        
        # Отправляем клавиатуру с кнопками
        keyboard = self.create_main_keyboard()
        self.send_message(chat_id, "📊 Выберите действие:", keyboard)
    
    def handle_callback(self, callback_query):
        """Обработка callback-запросов"""
        chat_id = callback_query['message']['chat']['id']
        user_id = callback_query['from']['id']
        callback_id = callback_query['id']
        data = callback_query['data']
        
        try:
            requests.post(
                f"{self.bot_url}/answerCallbackQuery",
                json={'callback_query_id': callback_id}
            )
        except:
            pass
        
        user_data = self.user_data.get(f"{chat_id}_data")
        if not user_data:
            self.send_message(chat_id, "❌ Данные не найдены. Отправьте никнейм снова.")
            return
        
        if data == 'main_stats':
            main_message = self.format_main_stats(user_data['stats'])
            self.send_message(chat_id, main_message)
        
        elif data == 'top_tanks':
            top_tanks = self.get_top_tanks(user_data['tanks'], user_data['tank_info'], 10)
            top_message = self.format_top_tanks(user_data['nickname'], top_tanks)
            self.send_message(chat_id, top_message)
        
        elif data == 'stats_file':
            self.send_message(chat_id, "⏳ Готовлю файл со статистикой...")
            stats_content = self.generate_stats_file(
                user_data['nickname'],
                user_data['stats'],
                user_data['tanks'],
                user_data['tank_info']
            )
            self.send_document(
                chat_id,
                stats_content,
                f"{user_data['nickname']}_stats.txt",
                f"📊 Полная статистика игрока {user_data['nickname']}"
            )
        
        elif data == 'all_tanks':
            all_tanks_message = self.format_all_tanks(
                user_data['nickname'],
                user_data['tanks'],
                user_data['tank_info']
            )
            self.send_message(chat_id, all_tanks_message)
    
    def get_updates(self):
        try:
            response = requests.get(
                f"{self.bot_url}/getUpdates",
                params={'offset': self.offset, 'timeout': 30},
                timeout=35
            )
            return response.json()
        except:
            return {'ok': False}
    
    def run(self):
        print("=" * 60)
        print("🤖 WoT BLITZ STATS BOT")
        print("=" * 60)
        print("📊 Показывает статистику и ангар игрока")
        print("🏆 Топ танков по боям")
        print("📁 Скачивание статистики в файл")
        print("🚙 Просмотр всего ангара")
        print("🛑 Остановка: Ctrl+C")
        print("=" * 60)
        print("\nБот запущен...\n")
        
        while self.running:
            try:
                updates = self.get_updates()
                
                if updates.get('ok'):
                    for update in updates.get('result', []):
                        self.offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            self.process_message(update['message'])
                        elif 'callback_query' in update:
                            self.handle_callback(update['callback_query'])
                
                time.sleep(0.3)
                
            except KeyboardInterrupt:
                print("\n🛑 Остановка бота...")
                self.running = False
                break
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                time.sleep(1)
        
        # Закрываем соединение с базой данных
        if hasattr(self, 'conn'):
            self.conn.close()
        print("\n👋 Бот остановлен")
        sys.exit(0)

if __name__ == '__main__':
    bot = BlitzBotUltimate()
    bot.run()