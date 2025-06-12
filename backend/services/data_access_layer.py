import asyncio
import aiosqlite
import logging
import os
import json
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class DataAccessLayer:
    """
    資料存取層 (DataAccessLayer) 類別。
    負責應用程式核心資料實體（如報告、提示詞）的非同步 CRUD 操作。
    """
    reports_db_path: str
    prompts_db_path: str
    _connections: Dict[str, aiosqlite.Connection]

    def __init__(self, reports_db_path: str, prompts_db_path: str) -> None:
        """初始化 DataAccessLayer。"""
        self.reports_db_path = reports_db_path
        self.prompts_db_path = prompts_db_path
        self._connections = {}
        self._memory_db_locks: Dict[str, asyncio.Lock] = {}
        logger.info(
            f"DataAccessLayer 配置使用報告資料庫於: '{self.reports_db_path}' 及提示詞資料庫於: '{self.prompts_db_path}'.",
            extra={"props": {"service_name": "DataAccessLayer", "status": "configured", "reports_db": reports_db_path, "prompts_db": prompts_db_path}}
        )
        # **【關鍵修正】** 在初始化時，預先建立檔案型資料庫的目錄
        for path in [self.reports_db_path, self.prompts_db_path]:
            if path != ":memory:":
                db_dir = os.path.dirname(path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"已確認或建立資料庫目錄: {db_dir}")

    async def _get_connection(self, db_path: str) -> aiosqlite.Connection:
        """取得並配置一個資料庫連接。"""
        if db_path == ":memory:":
            if db_path not in self._connections:
                conn = await aiosqlite.connect(db_path)
                conn.row_factory = aiosqlite.Row
                self._connections[db_path] = conn
                self._memory_db_locks[db_path] = asyncio.Lock()
            return self._connections[db_path]
        else:
            conn = await aiosqlite.connect(db_path)
            conn.row_factory = aiosqlite.Row
            return conn

    async def close_connections(self) -> None:
        """關閉所有由 DAL 管理的持久化 :memory: 資料庫連接。"""
        for conn in self._connections.values():
            if conn:
                await conn.close()
        self._connections.clear()
        logger.info("所有持久化記憶體資料庫連接已關閉。")

    async def _execute_query(self, db_path: str, query: str, params: Tuple[Any, ...] = (), fetch_one: bool = False, fetch_all: bool = False, commit: bool = False) -> Optional[Any]:
        """內部輔助方法，用於執行 SQL 查詢並處理連接。"""
        is_memory_db = (db_path == ":memory:")
        conn_context = None

        try:
            if is_memory_db:
                lock = self._memory_db_locks.get(db_path)
                if not lock:
                    raise RuntimeError(f"嚴重錯誤：找不到用於記憶體資料庫 '{db_path}' 的鎖。")

                async with lock:
                    conn = await self._get_connection(db_path)
                    cursor = await conn.execute(query, params)
                    if commit:
                        await conn.commit()
                        return cursor.lastrowid if query.strip().upper().startswith("INSERT") else cursor.rowcount

                    if fetch_one:
                        return await cursor.fetchone()
                    if fetch_all:
                        return await cursor.fetchall()
                    return None
            else: # File-based DB
                async with aiosqlite.connect(db_path) as conn:
                    conn.row_factory = aiosqlite.Row
                    cursor = await conn.execute(query, params)
                    if commit:
                        await conn.commit()
                        return cursor.lastrowid if query.strip().upper().startswith("INSERT") else cursor.rowcount

                    if fetch_one:
                        return await cursor.fetchone()
                    if fetch_all:
                        return await cursor.fetchall()
                    return None
        except Exception as e_query:
            logger.error(
                f"執行資料庫查詢失敗。DB: '{db_path}', Query: '{query[:100]}...'",
                exc_info=True,
                extra={"props": {"db_path": db_path, "query_snippet": query[:100], "params": str(params), "error": str(e_query)}}
            )
            raise

    async def initialize_databases(self) -> None:
        """初始化所有配置的資料庫和必要的資料表。"""
        await self._create_reports_table()
        await self._create_prompts_table()
        logger.info("資料庫初始化完成。")

    async def _create_reports_table(self) -> None:
        """在報告資料庫中創建 `reports` 資料表。"""
        query = """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            content TEXT,
            source_path TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            metadata TEXT,
            analysis_json TEXT
        );
        """
        await self._execute_query(self.reports_db_path, query, commit=True)
        logger.info(f"'reports' 表已在 '{self.reports_db_path}' 中確認/創建。")

    async def _create_prompts_table(self) -> None:
        """在提示詞資料庫中創建 `prompt_templates` 資料表。"""
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

    # ... (其餘的 CRUD 方法，如 insert_report_data, get_report_by_id 等維持不變) ...
    async def insert_report_data(self, original_filename: str, content: Optional[str],
                                 source_path: str, metadata: Optional[Dict[str, Any]] = None,
                                 status: str = '已擷取待處理') -> Optional[int]:
        metadata_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
        query = "INSERT INTO reports (original_filename, content, source_path, metadata, status) VALUES (?, ?, ?, ?, ?)"
        try:
            last_row_id = await self._execute_query(self.reports_db_path, query,
                                                (original_filename, content, source_path, metadata_str, status),
                                                commit=True)
            logger.info(f"新報告 '{original_filename}' 已插入到 reports 資料庫，ID: {last_row_id}。")
            return last_row_id
        except Exception as e:
            logger.error(f"插入報告 '{original_filename}' 失敗: {e}")
            return None

    async def get_report_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM reports WHERE id = ?"
        try:
            row = await self._execute_query(self.reports_db_path, query, (report_id,), fetch_one=True)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"查詢報告 ID {report_id} 失敗: {e}")
            return None

    async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
        fields_to_update = {"status": status}
        if processed_content is not None:
            fields_to_update["content"] = processed_content

        set_clause = ", ".join([f"{key} = ?" for key in fields_to_update.keys()])
        params = list(fields_to_update.values()) + [report_id]
        query = f"UPDATE reports SET {set_clause}, processed_at = CURRENT_TIMESTAMP WHERE id = ?"

        try:
            rows_affected = await self._execute_query(self.reports_db_path, query, tuple(params), commit=True)
            return rows_affected > 0
        except Exception as e:
            logger.error(f"更新報告 ID {report_id} 狀態失敗: {e}")
            return False

    async def update_report_analysis(self, report_id: int, analysis_data: str, status: str) -> bool:
        query = "UPDATE reports SET analysis_json = ?, status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        try:
            rows_affected = await self._execute_query(self.reports_db_path, query, (analysis_data, status, report_id), commit=True)
            return rows_affected > 0
        except Exception as e:
            logger.error(f"儲存報告 ID {report_id} 的 AI 分析結果失敗: {e}")
            return False

    async def update_report_metadata(self, report_id: int, metadata_update: Dict[str, Any]) -> bool:
        current_report = await self.get_report_by_id(report_id)
        if not current_report:
            return False
        try:
            current_metadata = json.loads(current_report.get("metadata") or '{}')
            current_metadata.update(metadata_update)
            new_metadata_str = json.dumps(current_metadata, ensure_ascii=False)
            query = "UPDATE reports SET metadata = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
            rows_affected = await self._execute_query(self.reports_db_path, query, (new_metadata_str, report_id), commit=True)
            return rows_affected > 0
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"更新報告 ID {report_id} 的 metadata 時發生錯誤: {e}")
            return False

    async def check_report_exists_by_source_path(self, source_path: str) -> bool:
        query = "SELECT 1 FROM reports WHERE source_path = ? LIMIT 1"
        try:
            result = await self._execute_query(self.reports_db_path, query, (source_path,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"檢查報告是否存在 (source_path: {source_path}) 時失敗: {e}")
            return False

    async def insert_prompt_template(self, name: str, template_text: str, category: Optional[str] = None) -> Optional[int]:
        """將新的提示詞範本插入到 `prompt_templates` 資料庫。

        此方法儲存一個新的提示詞範本，包括其唯一名稱、範本內容和可選的類別。
        `name` 欄位在資料庫中有唯一性約束。如果嘗試插入同名範本，操作將失敗。
        成功插入後返回新範本的 ID。若發生錯誤 (例如違反唯一性約束)，則記錄錯誤並返回 None。

        Args:
            name (str): 提示詞範本的唯一識別名稱。
            template_text (str): 提示詞範本的實際內容文字。
            category (Optional[str], optional): 提示詞範本的分類。預設為 None。

        Returns:
            Optional[int]: 若插入成功，則返回新提示詞範本的整數 ID；若發生錯誤，則返回 None。
        """
        query = "INSERT INTO prompt_templates (name, template_text, category) VALUES (?, ?, ?)"
        log_props = {"prompt_name": name, "category": category, "operation": "insert_prompt_template"}
        try:
            last_row_id = await self._execute_query(self.prompts_db_path, query, (name, template_text, category), commit=True)
            logger.info(
                f"新提示詞範本 '{name}' 已插入到 prompts 資料庫，ID: {last_row_id}",
                extra={"props": {**log_props, "prompt_id": last_row_id, "db_operation_status": "success"}}
            )
            return last_row_id
        except Exception as e:
            logger.error(
                f"插入提示詞範本 '{name}' 失敗: {e}", exc_info=False,
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return None

    async def get_prompt_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根據名稱從提示詞範本資料庫中檢索單個提示詞範本。

        執行 SQL 查詢以獲取具有給定唯一名稱的提示詞範本。
        如果找到，結果 `aiosqlite.Row` 物件會被轉換為字典並返回。
        如果未找到或發生資料庫錯誤，則記錄錯誤並返回 None。

        Args:
            name (str): 要檢索的提示詞範本的唯一名稱。

        Returns:
            Optional[Dict[str, Any]]: 如果找到範本，則返回包含其所有欄位資料的字典；
                                     若未找到或發生錯誤，則返回 None。
        """
        query = "SELECT id, name, template_text, category, created_at, updated_at FROM prompt_templates WHERE name = ?"
        log_props = {"prompt_name": name, "operation": "get_prompt_template_by_name"}
        try:
            row = await self._execute_query(self.prompts_db_path, query, (name,), fetch_one=True)
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(
                f"查詢提示詞範本 '{name}' 失敗 (已在 _execute_query 中記錄詳細資料): {e}", exc_info=False,
                extra={"props": {**log_props, "error_message": str(e)}}
            )
            return None

    async def get_all_prompt_templates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """從資料庫中檢索所有提示詞範本的列表，支持分頁和排序。

        此方法查詢 `prompt_templates` 表，按範本名稱升序 (`name ASC`) 排序，
        並使用 `limit` 和 `offset` 參數來實現分頁。
        返回的列表中，每個範本是一個字典，僅包含 'id', 'name', 'category', 'updated_at' 欄位，
        不包含完整的 `template_text`，以提高效能。
        如果查詢成功但無結果，則返回空列表。若發生資料庫錯誤，則記錄錯誤並返回空列表。

        Args:
            limit (int, optional): 要檢索的最大範本數量。預設為 100。
            offset (int, optional): 結果集的起始偏移量，用於分頁。預設為 0。

        Returns:
            List[Dict[str, Any]]: 包含提示詞範本資料的字典列表。每個字典包含：
                                  'id' (int), 'name' (str), 'category' (Optional[str]),
                                  'updated_at' (str/datetime)。
                                  如果沒有找到範本或發生錯誤，則返回空列表。
        """
        query = "SELECT id, name, category, updated_at FROM prompt_templates ORDER BY name ASC LIMIT ? OFFSET ?"
        log_props = {"limit": limit, "offset": offset, "operation": "get_all_prompt_templates"}
        try:
            rows = await self._execute_query(self.prompts_db_path, query, (limit, offset), fetch_all=True)
            if rows:
                return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(
                f"查詢所有提示詞範本失敗 (已在 _execute_query 中記錄詳細資料): {e}", exc_info=False,
                extra={"props": {**log_props, "error_message": str(e)}}
            )
            return []

if __name__ == '__main__':
    import asyncio
    # ... (rest of __main__ block) ...
    # 下面添加一個 get_all_reports 的示例實現，因為它在測試代碼中被調用
    # 但未在 DataAccessLayer 類中定義。為了使測試代碼完整，這裡模擬一個。
    # 實際應用中，應將此方法正式添加到 DataAccessLayer 類中。

    async def get_all_reports_for_testing(dal_instance: DataAccessLayer, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """(僅為 __main__ 區塊測試目的的輔助函數) 從資料庫檢索報告列表，支持分頁。

        注意: 此函數是為 `if __name__ == '__main__':` 中的臨時測試而設計，
        並未作為 `DataAccessLayer` 類別的正式方法。
        它示範了如何連接到報告資料庫並按 `processed_at` 時間降序檢索報告的部分欄位。

        Args:
            dal_instance (DataAccessLayer): `DataAccessLayer` 的一個實例，用於獲取報告資料庫路徑。
            limit (int, optional): 要檢索的最大報告數量。預設為 10。
            offset (int, optional): 結果集的起始偏移量。預設為 0。

        Returns:
            List[Dict[str, Any]]: 包含報告資料的字典列表。每個字典包含 'id',
                                  'original_filename', 'status', 'processed_at', 'source_path'。
                                  錯誤時返回空列表。
        """
        query = "SELECT id, original_filename, status, processed_at, source_path FROM reports ORDER BY processed_at DESC LIMIT ? OFFSET ?"
        try:
            # **【修正】** __main__ 區塊中的測試函數應使用 DAL 實例的 _execute_query 方法
            # 而不是直接建立新的 aiosqlite 連接，以保持與 DAL 設計一致的連接管理。
            # 注意：這假設 _execute_query 可以被外部（如此測試函數）安全調用，
            # 或者此測試函數應移至 DAL 類內部作為一個私有測試輔助方法。
            # 為了最小化更改，我們這裡假設可以直接調用 _execute_query。
            # 如果 dal_instance.reports_db_path 是 :memory:，則需要 DAL 實例來管理連接。
            rows = await dal_instance._execute_query(
                dal_instance.reports_db_path,
                query,
                (limit, offset),
                fetch_all=True
            )
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"測試中查詢所有報告失敗: {e}", exc_info=True)
            return []

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 假設 DAL 位於 services/
    data_dir = os.path.join(project_root, 'data', 'test_data_dal') # 更改測試數據目錄以避免衝突

    # **【增強】** 清理舊的測試數據庫前，先確保目錄存在
    os.makedirs(data_dir, exist_ok=True)

    test_reports_db = os.path.join(data_dir, 'test_reports.sqlite')
    test_prompts_db = os.path.join(data_dir, 'test_prompts.sqlite')

    # **【增強】** 安全地刪除舊的測試數據庫文件
    try:
        if os.path.exists(test_reports_db): os.remove(test_reports_db)
        if os.path.exists(test_prompts_db): os.remove(test_prompts_db)
    except OSError as e_remove:
        logger.warning(f"刪除舊的測試數據庫時出錯: {e_remove}")

    async def main() -> None:
        dal = DataAccessLayer(reports_db_path=test_reports_db, prompts_db_path=test_prompts_db)
        logger.info("---- 開始 DataAccessLayer 功能測試 ----")
        await dal.initialize_databases() # 這會創建表結構

        logger.info("\n---- 測試「報告」相關功能 ----")
        report_id1 = await dal.insert_report_data("報告A.docx", "內容A", "/path/A", {"author": "作者1"})
        report_id2 = await dal.insert_report_data("報告B.pdf", "內容B", "/path/B", {"department": "部門X"})

        if report_id1:
            logger.info(f"報告 ID {report_id1} (分析前): {await dal.get_report_by_id(report_id1)}")
            await dal.update_report_analysis(report_id1, json.dumps({"summary": "摘要A"}), "分析完成")
            logger.info(f"報告 ID {report_id1} (分析後): {await dal.get_report_by_id(report_id1)}")

        if report_id2:
            await dal.update_report_status(report_id2, "處理中", "更新內容B")
            logger.info(f"報告 ID {report_id2} (狀態更新後): {await dal.get_report_by_id(report_id2)}")

        all_reports = await get_all_reports_for_testing(dal, limit=5)
        logger.info(f"資料庫中所有報告 (最多5條): {all_reports}")

        logger.info("\n---- 測試「提示詞範本」相關功能 ----")
        prompt_id1 = await dal.insert_prompt_template("範本1", "這是範本1的內容。", "通用")
        if prompt_id1:
            logger.info(f"提示詞範本 ID {prompt_id1}: {await dal.get_prompt_template_by_name('範本1')}")

        all_prompts = await dal.get_all_prompt_templates()
        logger.info(f"所有提示詞範本: {all_prompts}")

        logger.info(f"\n測試完畢。測試用的資料庫檔案位於目錄: {data_dir}")

        # **【關鍵修正】** 測試結束後，顯式關閉 DAL 管理的記憶體資料庫連接（如果有的話）
        await dal.close_connections()

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # **【增強】** 使用 try/finally 確保即使 main() 執行出錯，資源也能被清理
    # 注意：對於檔案型資料庫，連接通常在 _execute_query 中通過 `async with` 管理，
    # 但 DAL 實例本身可能持有記憶體資料庫的持久連接，需由 close_connections 清理。
    try:
        asyncio.run(main())
    except Exception as e_main:
        logger.error(f"執行 main 測試函數時發生未預期錯誤: {e_main}", exc_info=True)
    finally:
        # 這裡可以添加額外的清理邏輯，例如再次嘗試關閉連接或刪除測試文件，
        # 但要小心 asyncio.run() 之後事件循環的狀態。
        # 對於此範例，主要的 close_connections 已移至 main() 內部。
        logger.info("DataAccessLayer 測試腳本執行完畢。")
