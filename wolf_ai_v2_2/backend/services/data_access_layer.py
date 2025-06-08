import aiosqlite
import logging
import os
from typing import Optional, Dict, Any, List

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataAccessLayer:
    def __init__(self, reports_db_path: str, prompts_db_path: str):
        """
        初始化資料存取層。
        :param reports_db_path: 報告資料庫檔案的路徑。
        :param prompts_db_path: 提示詞資料庫檔案的路徑。
        """
        self.reports_db_path = reports_db_path
        self.prompts_db_path = prompts_db_path
        logger.info(f"DataAccessLayer initialized with reports_db: '{reports_db_path}', prompts_db: '{prompts_db_path}'")

    async def _execute_query(self, db_path: str, query: str, params: tuple = (), fetch_one=False, fetch_all=False, commit=False):
        """
        通用的異步查詢執行方法。
        """
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        async with aiosqlite.connect(db_path) as db:
            # For DDL statements that don't return rows (like CREATE TABLE)
            # or for INSERT/UPDATE/DELETE, execute directly.
            if query.strip().upper().startswith(("CREATE", "INSERT", "UPDATE", "DELETE")) or commit:
                await db.execute(query, params)
                if commit:
                    await db.commit()
                # For INSERT, SQLite's lastrowid is typically retrieved from the cursor
                # after an execute call, but aiosqlite's execute itself doesn't return a cursor directly for non-select.
                # A common way for INSERT is to get it from the connection after commit or cursor.
                # For simplicity here, if it's an INSERT, we might need a different handling if lastrowid is strictly needed from this generic method.
                # For now, let's assume commit=True implies it might be an INSERT/UPDATE/DELETE
                # and if a lastrowid is needed, it's better to handle it in the specific method.
                # Let's return cursor.lastrowid if commit is true, assuming it's an insert/update
                if commit: # Attempt to get lastrowid, works for INSERT
                    cursor = await db.execute("SELECT last_insert_rowid()")
                    last_id = await cursor.fetchone()
                    return last_id[0] if last_id else None
            else: # For SELECT statements
                async with db.execute(query, params) as cursor:
                    if fetch_one:
                        result = await cursor.fetchone()
                        return result
                    if fetch_all:
                        result = await cursor.fetchall()
                        return result

    async def initialize_databases(self):
        """
        初始化兩個資料庫，如果它們還不存在或表不存在，則創建表。
        """
        await self._create_reports_table()
        await self._create_prompts_table()
        logger.info("資料庫初始化完成 (如果需要)。")

    async def _create_reports_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            content TEXT,
            source_path TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            metadata TEXT
        );
        """
        # DDL statements don't typically return lastrowid, so commit=True is enough.
        await self._execute_query(self.reports_db_path, query, commit=True)
        logger.info(f"'reports' 表已在 '{self.reports_db_path}' 中確認/創建。")

    async def _create_prompts_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            template_text TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self._execute_query(self.prompts_db_path, query, commit=True)
        logger.info(f"'prompt_templates' 表已在 '{self.prompts_db_path}' 中確認/創建。")

    async def insert_report_data(self, original_filename: str, content: Optional[str], source_path: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[int]:
        import json
        metadata_str = json.dumps(metadata) if metadata else None
        query = "INSERT INTO reports (original_filename, content, source_path, metadata, status) VALUES (?, ?, ?, ?, 'pending')"
        try:
            last_row_id = await self._execute_query(self.reports_db_path, query, (original_filename, content, source_path, metadata_str), commit=True)
            logger.info(f"新報告 '{original_filename}' 已插入到 reports 資料庫，ID: {last_row_id}")
            return last_row_id
        except Exception as e:
            logger.error(f"插入報告 '{original_filename}' 失敗: {e}")
            return None

    async def get_report_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT id, original_filename, content, source_path, processed_at, status, metadata FROM reports WHERE id = ?"
        row = await self._execute_query(self.reports_db_path, query, (report_id,), fetch_one=True)
        if row:
            # Convert aiosqlite.Row to dict
            # row.keys() gives column names, and row itself can be indexed like a tuple or dict
            return {k: row[k] for k in row.keys()}
        return None

    async def get_all_reports(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = "SELECT id, original_filename, source_path, processed_at, status FROM reports ORDER BY processed_at DESC LIMIT ? OFFSET ?"
        rows = await self._execute_query(self.reports_db_path, query, (limit, offset), fetch_all=True)
        if rows:
            return [{k: row[k] for k in row.keys()} for row in rows]
        return []

    async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
        fields_to_update = {"status": status}
        if processed_content is not None:
            fields_to_update["content"] = processed_content

        query_parts = [f"{field} = ?" for field in fields_to_update.keys()]
        query_params = list(fields_to_update.values())
        query_params.append(report_id)

        query = f"UPDATE reports SET {', '.join(query_parts)}, processed_at = CURRENT_TIMESTAMP WHERE id = ?"

        try:
            await self._execute_query(self.reports_db_path, query, tuple(query_params), commit=True)
            logger.info(f"報告 ID {report_id} 的狀態已更新為 '{status}'。")
            return True
        except Exception as e:
            logger.error(f"更新報告 ID {report_id} 狀態失敗: {e}")
            return False

    async def insert_prompt_template(self, name: str, template_text: str, category: Optional[str] = None) -> Optional[int]:
        query = "INSERT INTO prompt_templates (name, template_text, category) VALUES (?, ?, ?)"
        try:
            last_row_id = await self._execute_query(self.prompts_db_path, query, (name, template_text, category), commit=True)
            logger.info(f"新提示詞範本 '{name}' 已插入到 prompts 資料庫，ID: {last_row_id}")
            return last_row_id
        except Exception as e:
            logger.error(f"插入提示詞範本 '{name}' 失敗: {e}")
            return None

    async def get_prompt_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        query = "SELECT id, name, template_text, category, created_at, updated_at FROM prompt_templates WHERE name = ?"
        row = await self._execute_query(self.prompts_db_path, query, (name,), fetch_one=True)
        if row:
            return {k: row[k] for k in row.keys()}
        return None

    async def get_all_prompt_templates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = "SELECT id, name, category, updated_at FROM prompt_templates ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        rows = await self._execute_query(self.prompts_db_path, query, (limit, offset), fetch_all=True)
        if rows:
            return [{k: row[k] for k in row.keys()} for row in rows]
        return []

if __name__ == '__main__':
    import asyncio

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
    data_dir = os.path.join(project_root, 'data')

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    test_reports_db = os.path.join(data_dir, 'test_reports.sqlite')
    test_prompts_db = os.path.join(data_dir, 'test_prompts.sqlite')

    if os.path.exists(test_reports_db):
        os.remove(test_reports_db)
    if os.path.exists(test_prompts_db):
        os.remove(test_prompts_db)

    async def main():
        # Make sure aiosqlite connection uses row_factory for dict-like rows if needed by default
        # For this code, conversion is done manually after fetching.
        # import aiosqlite
        # aiosqlite.Row.keys() and indexing row[key] works out of the box.

        dal = DataAccessLayer(reports_db_path=test_reports_db, prompts_db_path=test_prompts_db)

        logger.info("---- 測試 DataAccessLayer ----")
        await dal.initialize_databases()

        logger.info("\n---- 測試報告功能 ----")
        report_id1 = await dal.insert_report_data("週報_2025_W23.docx", "這是第一份週報的內容。", "/wolf_in/週報_2025_W23.docx", {"author": "張三"})
        report_id2 = await dal.insert_report_data("月度總結.pdf", None, "/wolf_in/月度總結.pdf", {"department": "技術部"})

        if report_id1:
            retrieved_report1 = await dal.get_report_by_id(report_id1)
            logger.info(f"獲取的報告 ID {report_id1}: {retrieved_report1}")

        if report_id2:
            await dal.update_report_status(report_id2, "processed", "這是處理後的月度總結內容。")
            retrieved_report2 = await dal.get_report_by_id(report_id2)
            logger.info(f"更新並獲取的報告 ID {report_id2}: {retrieved_report2}")

        all_reports = await dal.get_all_reports()
        logger.info(f"所有報告 (部分欄位): {all_reports}")

        logger.info("\n---- 測試提示詞範本功能 ----")
        prompt_id1 = await dal.insert_prompt_template("週報總結助理", "請幫我總結這份週報的主要內容、已完成任務和遇到的問題。", "週報分析")
        prompt_id2 = await dal.insert_prompt_template("提取關鍵資訊", "從以下文字中提取關鍵的日期、人物和事件：\n{text_input}", "通用提取")

        if prompt_id1:
            retrieved_prompt1 = await dal.get_prompt_template_by_name("週報總結助理")
            logger.info(f"獲取的提示詞範本 '週報總結助理': {retrieved_prompt1}")

        all_prompts = await dal.get_all_prompt_templates()
        logger.info(f"所有提示詞範本 (部分欄位): {all_prompts}")

        logger.info(f"測試資料庫檔案位於: {data_dir}")

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
