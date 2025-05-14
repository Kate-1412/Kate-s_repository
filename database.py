import sqlite3
from datetime import datetime
from typing import List, Dict


class Database:
    def __init__(self, db_name: str = 'finance.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        """Создает таблицы в базе данных"""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    lang TEXT DEFAULT 'ru',
                    currency TEXT DEFAULT 'RUB',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL NOT NULL,
                    category TEXT,
                    is_income BOOLEAN NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    user_id INTEGER,
                    category TEXT,
                    limit_amount REAL,
                    PRIMARY KEY (user_id, category)
                )
            """)

    def add_user(self, user_id: int, first_name: str, username: str):
        """Добавляет пользователя в базу"""
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
                (user_id, first_name, username)
            )

    def add_transaction(self, user_id: int, amount: float, category: str, is_income: bool, currency: str = 'RUB'):
        """Добавляет транзакцию"""
        with self.conn:
            self.conn.execute(
                """INSERT INTO transactions 
                (user_id, amount, category, is_income, currency) 
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, category, is_income, currency)
            )

    def get_transactions(self, user_id: int, period: str = 'all') -> List[Dict]:
        """Возвращает транзакции за период"""
        now = datetime.now()
        query = "SELECT * FROM transactions WHERE user_id = ?"
        params = [user_id]

        if period == 'current_month':
            query += " AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"
        elif period == 'last_month':
            query += " AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-1 month')"
        elif period == 'last_30_days':
            query += " AND date >= datetime('now', '-30 days')"
        elif period == 'last_12_months':
            query += " AND date >= datetime('now', '-1 year')"

        cursor = self.conn.execute(query, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_stats(self, user_id: int, period: str = 'all') -> Dict:
        """Статистика по категориям"""
        transactions = self.get_transactions(user_id, period)
        stats = {
            'total_income': 0,
            'total_expense': 0,
            'categories_income': {},
            'categories_expense': {}
        }

        for t in transactions:
            if t['is_income']:
                stats['total_income'] += t['amount']
                stats['categories_income'][t['category']] = stats['categories_income'].get(t['category'], 0) + t[
                    'amount']
            else:
                stats['total_expense'] += t['amount']
                stats['categories_expense'][t['category']] = stats['categories_expense'].get(t['category'], 0) + t[
                    'amount']

        return stats

    def export_to_csv(self, user_id: int) -> str:
        """Экспорт транзакций в CSV"""
        import csv
        from io import StringIO

        transactions = self.get_transactions(user_id)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Дата', 'Сумма', 'Категория', 'Тип', 'Валюта'])

        for t in transactions:
            writer.writerow([
                t['date'],
                t['amount'],
                t['category'],
                'Доход' if t['is_income'] else 'Расход',
                t['currency']
            ])

        return output.getvalue()


db = Database()
