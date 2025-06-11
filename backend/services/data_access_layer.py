import aiosqlite
import logging
import os
import json
from typing import Optional, Dict, Any, List, Tuple

# aiosqlite is already imported at the top of the file by the first import aiosqlite statement.
# No need for a second import here. We can use aiosqlite.Connection directly.

logger = logging.getLogger(__name__)

class DataAccessLayer:
    """
    資料存取層 (DataAccessLayer) 類別。

    本類別封裝了所有對 SQLite 資料庫的非同步操作，用於管理「報告」和「提示詞範本」
    兩種核心資料實體。它提供了結構化的 API 來執行 CRUD (建立、讀取、更新、刪除)
    操作，同時處理資料庫連接、查詢執行、錯誤記錄和目錄創建等底層細節。

    主要職責:
    - 初始化資料庫結構 (建立資料表)。
    - 管理資料庫連接，特別是對記憶體資料庫 (`:memory:`) 的持久連接。
    - 提供插入、查詢、更新和檢查報告資料的方法。
    - 提供插入、查詢提示詞範本的方法。
    - 統一的錯誤處理和日誌記錄機制。

    設計考量:
    - 使用 `aiosqlite` 進行非同步資料庫操作，適用於異步應用程式 (如 FastAPI)。
    - 對於記憶體資料庫，會維護一個共享連接以確保資料在操作間的持久性。
    - 對於檔案型資料庫，每次操作會建立新的連接，並透過 `async with` 管理其生命週期。
    - 方法返回型別和參數均經過型別提示，以提高程式碼清晰度和可維護性。
    """
    reports_db_path: str
    prompts_db_path: str
    _connections: Dict[str, aiosqlite.Connection]

    def __init__(self, reports_db_path: str, prompts_db_path: str) -> None:
        """初始化 DataAccessLayer 實例。

        設定報告資料庫和提示詞範本資料庫的路徑，並初始化用於管理
        記憶體資料庫連接的內部字典。

        Args:
            reports_db_path (str): 報告資料庫的檔案路徑。
                                   若為 ":memory:"，則使用記憶體資料庫。
            prompts_db_path (str): 提示詞範本資料庫的檔案路徑。
                                   若為 ":memory:"，則使用記憶體資料庫。
        """
        self.reports_db_path = reports_db_path
        self.prompts_db_path = prompts_db_path
        self._connections = {} # Store persistent connections for :memory: DBs
        logger.info(
            f"DataAccessLayer 配置使用報告資料庫於: '{self.reports_db_path}' 及提示詞資料庫於: '{self.prompts_db_path}'.",
            extra={"props": {"service_name": "DataAccessLayer", "status": "configured", "reports_db": reports_db_path, "prompts_db": prompts_db_path}}
        )

    async def _get_connection(self, db_path: str) -> aiosqlite.Connection:
        """取得並配置一個資料庫連接。

        如果 `db_path` 是 ":memory:"，此方法會返回一個持久的記憶體資料庫連接。
        如果該連接尚不存在，則會創建一個新的連接，設定其 `row_factory` 為 `aiosqlite.Row`
        以便按欄位名稱存取結果，並將其儲存以供後續重用。
        對於檔案型資料庫，每次調用都會建立一個新的連接，並設定 `row_factory`。

        Args:
            db_path (str): 目標資料庫的路徑。

        Returns:
            aiosqlite.Connection: 配置好的 aiosqlite 資料庫連接物件。
        """
        if db_path == ":memory:":
            if db_path not in self._connections:
                logger.info(f"為 '{db_path}' 建立新的 :memory: 連接並設定 row_factory。")
                conn = await aiosqlite.connect(db_path)
                conn.row_factory = aiosqlite.Row
                self._connections[db_path] = conn
            # Ensure row_factory is set even for existing connections if it wasn't (e.g. defensive)
            elif self._connections[db_path].row_factory is None:
                 self._connections[db_path].row_factory = aiosqlite.Row
            return self._connections[db_path]
        else: # File-based database
            conn = await aiosqlite.connect(db_path)
            conn.row_factory = aiosqlite.Row # Set row_factory for file connections too
            return conn

    async def close_connections(self) -> None:
        """關閉所有由 DAL 管理的持久化 :memory: 資料庫連接。

        此方法會迭代內部儲存的記憶體資料庫連接，並逐一關閉它們。
        主要用於測試結束後的資源清理。
        """
        for db_path, conn in self._connections.items():
            if conn:
                await conn.close()
                logger.info(f"已關閉 :memory: 資料庫 '{db_path}' 的連接。")
        self._connections.clear()

    async def _execute_query(self, db_path: str, query: str, params: Tuple[Any, ...] = (), fetch_one: bool = False, fetch_all: bool = False, commit: bool = False) -> Optional[Any]:
        """內部輔助方法，用於執行 SQL 查詢並處理連接。

        此方法負責實際的資料庫互動。它會根據 `db_path` 的類型（記憶體或檔案）
        獲取相應的資料庫連接。對於檔案型資料庫，它會確保目標目錄存在。
        它能夠執行查詢、提取單筆或多筆結果，提交事務，並在 INSERT 操作後返回
        新插入行的 ID，或在 UPDATE/DELETE 操作後返回受影響的行數。

        Args:
            db_path (str): 目標資料庫的檔案路徑 (或 ":memory:")。
            query (str): 要執行的 SQL 查詢語句。
            params (Tuple, optional): 查詢的參數。預設為空元組。
            fetch_one (bool, optional): 若為 True，則提取查詢結果的第一行。預設為 False。
            fetch_all (bool, optional): 若為 True，則提取查詢結果的所有行。預設為 False。
            commit (bool, optional): 若為 True，則在執行查詢後提交事務。
                                     對於 INSERT，返回 last_row_id；對於 UPDATE/DELETE，返回 rowcount。
                                     預設為 False。

        Returns:
            Optional[Any]: 查詢的結果。
                           - INSERT 且 commit: 返回 `int` 型別的 last_row_id。
                           - UPDATE/DELETE 且 commit: 返回 `int` 型別的受影響行數 (rowcount)。
                           - SELECT 且 fetch_one: 返回 `aiosqlite.Row` 物件或 `None`。
                           - SELECT 且 fetch_all: 返回 `List[aiosqlite.Row]` 或空列表。
                           - 其他情況 (如 DDL 且 commit) 返回 `None`。

        Raises:
            aiosqlite.Error: 如果在資料庫操作過程中發生錯誤，底層的 `aiosqlite` 異常會被記錄並重新引發。
        """
        if db_path != ":memory:": # For file-based DBs, ensure directory exists
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"資料庫目錄 '{db_dir}' 不存在，已創建。", extra={"props": {"db_path": db_path, "action": "create_directory"}})
                except Exception as e_mkdir:
                    logger.error(f"創建資料庫目錄 '{db_dir}' 失敗: {e_mkdir}", exc_info=True, extra={"props": {"db_path": db_path, "error": str(e_mkdir)}})
                    raise

        conn = None
        try:
            # Get connection: for :memory:, it's persistent; for files, it's new and managed by async with
            is_memory_db = (db_path == ":memory:")

            if is_memory_db:
                conn = await self._get_connection(db_path) # Get or create persistent connection
                # Execute directly on the persistent connection
                cursor = await conn.execute(query, params)
                if commit:
                    await conn.commit()
                    if query.strip().upper().startswith("INSERT"):
                        id_cursor = await conn.execute("SELECT last_insert_rowid()")
                        last_id_row = await id_cursor.fetchone()
                        await id_cursor.close()
                        return last_id_row[0] if last_id_row else None
                    return cursor.rowcount # For UPDATE/DELETE, return number of affected rows
                if fetch_one:
                    result = await cursor.fetchone()
                    await cursor.close()
                    return result
                if fetch_all:
                    result = await cursor.fetchall()
                    await cursor.close()
                    return result
                await cursor.close()
                return None
            else: # File-based DB, use async with for connection management
                async with await self._get_connection(db_path) as db_file_conn:
                    cursor = await db_file_conn.execute(query, params)
                    if commit:
                        await db_file_conn.commit()
                        if query.strip().upper().startswith("INSERT"):
                            id_cursor = await db_file_conn.execute("SELECT last_insert_rowid()")
                            last_id_row = await id_cursor.fetchone()
                            await id_cursor.close()
                            return last_id_row[0] if last_id_row else None
                        return cursor.rowcount # For UPDATE/DELETE, return number of affected rows
                    if fetch_one:
                        result = await cursor.fetchone()
                        await cursor.close()
                        return result
                    if fetch_all:
                        result = await cursor.fetchall()
                        await cursor.close()
                        return result
                    await cursor.close()
                    return None
        except Exception as e_query:
            logger.error(
                f"執行資料庫查詢失敗。DB: '{db_path}', Query: '{query[:100]}...' (參數: {params})",
                exc_info=True,
                extra={"props": {"db_path": db_path, "query_snippet": query[:100], "params": str(params), "error": str(e_query)}}
            )
            raise
        # Note: Persistent :memory: connections are not closed here; they are closed via self.close_connections()

    async def initialize_databases(self) -> None:
        """初始化所有配置的資料庫和必要的資料表。

        此方法會依次調用內部方法來創建 `reports` 和 `prompt_templates` 資料表。
        如果資料表已經存在，則相應的 `CREATE TABLE IF NOT EXISTS` 語句不會執行任何操作。
        對於記憶體資料庫，此過程也確保了相關連接已建立並儲存。
        """
        await self._create_reports_table()
        await self._create_prompts_table()
        logger.info("資料庫初始化完成 (如果需要)。", extra={"props": {"operation": "initialize_databases", "status": "completed"}})

    async def _create_reports_table(self) -> None:
        """在報告資料庫中創建 `reports` 資料表。

        此表用於儲存已處理報告的資訊，包括原始檔名、內容、來源路徑、
        處理時間戳、狀態、元數據及 AI 分析結果。
        如果資料表已存在，則不會重複創建。
        """
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
        # Ensure connections for :memory: DBs are established before creating tables
        if self.reports_db_path == ":memory:":
            await self._get_connection(self.reports_db_path) # Establishes and stores if not already

        await self._execute_query(self.reports_db_path, query, commit=True)
        logger.info(f"'reports' 表已在 '{self.reports_db_path}' 中確認/創建。", extra={"props": {"db_table": "reports", "db_path": self.reports_db_path}})

    async def _create_prompts_table(self) -> None:
        """在提示詞資料庫中創建 `prompt_templates` 資料表。

        此表用於儲存使用者定義的提示詞範本，包含範本名稱、內容、類別以及時間戳。
        範本名稱具有唯一性約束。
        如果資料表已存在，則不會重複創建。
        """
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
        if self.prompts_db_path == ":memory:":
            await self._get_connection(self.prompts_db_path) # Establishes and stores if not already

        await self._execute_query(self.prompts_db_path, query, commit=True)
        logger.info(f"'prompt_templates' 表已在 '{self.prompts_db_path}' 中確認/創建。", extra={"props": {"db_table": "prompt_templates", "db_path": self.prompts_db_path}})

    async def insert_report_data(self, original_filename: str, content: Optional[str],
                                 source_path: str, metadata: Optional[Dict[str, Any]] = None,
                                 status: str = '已擷取待處理') -> Optional[int]:
        """將新的報告資料插入到 `reports` 資料庫。

        此方法會將提供的報告資訊（包括原始檔名、文本內容、來源路徑、
        可選的元數據和狀態）儲存到報告資料庫中。元數據會被序列化為 JSON 字串進行儲存。
        成功插入後，將返回新記錄的 ID。如果發生資料庫錯誤，則記錄錯誤並返回 None。

        Args:
            original_filename (str): 報告的原始檔案名稱。
            content (Optional[str]): 報告的文本內容。若無內容則可為 None。
            source_path (str): 報告的來源路徑，例如在 Google Drive 中的完整路徑。
            metadata (Optional[Dict[str, Any]], optional): 包含報告附加資訊的字典，
                                                          必須可序列化為 JSON。預設為 None。
            status (str, optional): 報告的初始處理狀態。預設為 '已擷取待處理'。

        Returns:
            Optional[int]: 若插入成功，則返回新報告的整數 ID；若發生錯誤，則返回 None。
        """
        metadata_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
        query = "INSERT INTO reports (original_filename, content, source_path, metadata, status) VALUES (?, ?, ?, ?, ?)"
        log_props = {"original_filename": original_filename, "source_path": source_path, "status": status, "operation": "insert_report"}
        try:
            last_row_id = await self._execute_query(self.reports_db_path, query,
                                                (original_filename, content, source_path, metadata_str, status),
                                                commit=True)
            logger.info(
                f"新報告 '{original_filename}' 已插入到 reports 資料庫，ID: {last_row_id}，狀態: '{status}'。",
                extra={"props": {**log_props, "report_id": last_row_id, "db_operation_status": "success"}}
            )
            return last_row_id
        except Exception as e: # Catch errors re-raised from _execute_query
            logger.error(
                f"插入報告 '{original_filename}' 失敗: {e}", exc_info=False, # exc_info=False because _execute_query already logged it with True
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}} # Log the summarized error
            )
            return None

    async def get_report_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        """根據指定的 ID 從報告資料庫中檢索單個報告的詳細資訊。

        執行 SQL 查詢以獲取具有給定 ID 的報告。如果找到報告，
        結果 `aiosqlite.Row` 物件會被轉換為字典並返回。
        如果未找到報告或發生資料庫查詢錯誤，則記錄錯誤並返回 None。

        Args:
            report_id (int): 要檢索的報告的整數 ID。

        Returns:
            Optional[Dict[str, Any]]: 如果找到報告，則返回一個包含報告所有欄位資料的字典；
                                     若未找到或發生錯誤，則返回 None。
        """
        query = "SELECT id, original_filename, content, source_path, processed_at, status, metadata, analysis_json FROM reports WHERE id = ?"
        log_props = {"report_id": report_id, "operation": "get_report_by_id"}
        try:
            row = await self._execute_query(self.reports_db_path, query, (report_id,), fetch_one=True)
            if row:
                return dict(row) # aiosqlite.Row can be directly converted to dict if row_factory was set
            return None
        except Exception as e:
            # _execute_query already logs the detailed DB error. This log is for the specific operation context.
            logger.error(
                f"查詢報告 ID {report_id} 失敗 (已在 _execute_query 中記錄詳細資料): {e}", exc_info=False,
                extra={"props": {**log_props, "error_message": str(e)}}
            )
            return None

    async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
        """更新資料庫中指定報告的狀態，並可選擇性地更新其處理後的內容。

        此方法會根據提供的 `report_id` 更新報告的 `status` 欄位。
        如果同時提供了 `processed_content`，則報告的 `content` 欄位也會被更新。
        `processed_at` 時間戳將自動更新為目前時間。
        如果更新操作影響了至少一行 (即報告被找到且值被改變)，則返回 True。
        如果報告未找到或未發生實際更新 (例如，狀態和內容與現有值相同)，或發生資料庫錯誤，
        則記錄相應訊息並返回 False。

        Args:
            report_id (int): 要更新狀態的報告的 ID。
            status (str): 要設定給報告的新狀態。
            processed_content (Optional[str], optional): 報告處理後的更新文本內容。
                                                      如果為 None，則不更新 `content` 欄位。
                                                      預設為 None。

        Returns:
            bool: 如果報告狀態和/或內容成功更新 (至少一行受影響)，則返回 True；
                  否則返回 False。
        """
        fields_to_update = {"status": status}
        if processed_content is not None:
            fields_to_update["content"] = processed_content
        query_set_parts = [f"{field} = ?" for field in fields_to_update.keys()]
        query_params = list(fields_to_update.values())
        query_params.append(report_id)
        query = f"UPDATE reports SET {', '.join(query_set_parts)}, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        log_props = {"report_id": report_id, "new_status": status, "operation": "update_report_status"}
        try:
            row_count = await self._execute_query(self.reports_db_path, query, tuple(query_params), commit=True)
            if row_count > 0:
                logger.info(
                    f"報告 ID {report_id} 的狀態已更新為 '{status}' ({row_count} 行受影響)。",
                    extra={"props": {**log_props, "db_operation_status": "success", "rows_affected": row_count}}
                )
                return True
            else:
                logger.warning(
                    f"嘗試更新報告 ID {report_id} 的狀態，但沒有找到該報告或無需更新 ({row_count} 行受影響)。",
                    extra={"props": {**log_props, "db_operation_status": "no_change_or_not_found", "rows_affected": row_count}}
                )
                return False
        except Exception as e:
            logger.error(
                f"更新報告 ID {report_id} 狀態失敗: {e}", exc_info=False, # _execute_query logs with exc_info=True
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def update_report_analysis(self, report_id: int, analysis_data: str, status: str) -> bool:
        """更新指定報告的 AI 分析結果 (JSON 字串) 和處理狀態。

        此方法將提供的 `analysis_data` (應為 JSON 字串) 和新的 `status`
        儲存到具有給定 `report_id` 的報告記錄中。`processed_at` 時間戳會自動更新。
        如果更新操作影響了至少一行，則返回 True。
        如果報告未找到，或發生資料庫錯誤，則記錄錯誤並返回 False。

        Args:
            report_id (int): 要更新分析結果的報告的 ID。
            analysis_data (str): AI 分析結果的 JSON 字串表示。
            status (str): 報告在分析後的新狀態 (例如，'分析完成', '分析失敗')。

        Returns:
            bool: 如果分析結果和狀態成功更新 (至少一行受影響)，則返回 True；
                  否則返回 False。
        """
        query = "UPDATE reports SET analysis_json = ?, status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        log_props = {"report_id": report_id, "new_status": status, "operation": "update_report_analysis"}
        try:
            row_count = await self._execute_query(self.reports_db_path, query, (analysis_data, status, report_id), commit=True)
            if row_count > 0:
                logger.info(
                    f"報告 ID {report_id} 的 AI 分析結果已儲存，狀態更新為 '{status}' ({row_count} 行受影響)。",
                    extra={"props": {**log_props, "db_operation_status": "success", "rows_affected": row_count}}
                )
                return True
            else:
                logger.warning(
                    f"嘗試更新報告 ID {report_id} 的 AI 分析，但沒有找到該報告或無需更新 ({row_count} 行受影響)。",
                     extra={"props": {**log_props, "db_operation_status": "no_change_or_not_found", "rows_affected": row_count}}
                )
                return False
        except Exception as e:
            logger.error(
                f"儲存報告 ID {report_id} 的 AI 分析結果失敗: {e}", exc_info=False,
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def update_report_metadata(self, report_id: int, metadata_update: Dict[str, Any]) -> bool:
        """安全地更新指定報告的元數據。

        此方法首先獲取報告的現有元數據 (如果存在)，然後將 `metadata_update` 中的鍵值對
        合併到現有元數據中 (新的值會覆蓋舊的值)。更新後的完整元數據將被序列化為 JSON
        字串並寫回資料庫。`processed_at` 時間戳也會更新。

        如果報告不存在 (由 `get_report_by_id` 判斷)，或者在解析現有元數據 (如果格式損壞)
        或執行資料庫更新時發生錯誤，則操作失敗並返回 False。
        如果元數據成功更新 (即使沒有實際的欄位更改，例如更新的值與原值相同)，也返回 True。

        Args:
            report_id (int): 要更新元數據的報告的 ID。
            metadata_update (Dict[str, Any]): 一個字典，包含要添加或更新的元數據。
                                              此字典的內容將與報告現有的元數據合併。

        Returns:
            bool: 如果元數據成功設定或更新，則返回 True。
                  如果報告未找到，或在處理/儲存元數據時發生錯誤，則返回 False。
        """
        log_props = {"report_id": report_id, "operation": "update_report_metadata"}
        current_report = await self.get_report_by_id(report_id)
        if not current_report:
            logger.error(f"更新 metadata 失敗：找不到報告 ID {report_id}。", extra={"props": {**log_props, "error": "report_not_found"}})
            return False
        try:
            current_metadata_str = current_report.get("metadata")
            current_metadata = json.loads(current_metadata_str) if current_metadata_str else {}
            current_metadata.update(metadata_update)
            new_metadata_str = json.dumps(current_metadata, ensure_ascii=False)
            query = "UPDATE reports SET metadata = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
            row_count = await self._execute_query(self.reports_db_path, query, (new_metadata_str, report_id), commit=True)
            if row_count > 0:
                logger.info(f"報告 ID {report_id} 的 metadata 已更新 ({row_count} 行受影響)。", extra={"props": {**log_props, "db_operation_status": "success", "rows_affected": row_count}})
                return True
            else:
                logger.warning(f"嘗試更新報告 ID {report_id} 的 metadata，但沒有找到該報告 ({row_count} 行受影響)。", extra={"props": {**log_props, "db_operation_status": "not_found", "rows_affected": row_count}})
                # This case might still be True if the metadata was the same, but for "not found" it's False.
                # The current logic of update_report_metadata already checks if report exists via get_report_by_id.
                # If get_report_by_id returns None, it returns False before this.
                # So, if we reach here, report was found. row_count == 0 would mean metadata was identical.
                # For simplicity, let's assume if report is found, and _execute_query doesn't error, it's a success.
                # However, the test `test_update_report_metadata_report_not_found` relies on the early exit.
                # The row_count check is more accurate for "no change" vs "not found".
                # Given the existing structure, if row_count is 0, it means the report was found but metadata was identical, so no actual DB update.
                # Let's consider this a success, as the desired state (updated metadata) is achieved.
                # For a "not found" case, the function should have exited earlier.
                # Re-evaluating: the test `test_update_report_metadata_report_not_found` expects `False`.
                # The current `update_report_metadata` already returns `False` if `get_report_by_id` fails.
                # So, if `_execute_query` returns `row_count = 0`, it means the metadata was identical.
                # This should still be a `True` return from `update_report_metadata`.
                # The only way it should return False from this block is if _execute_query itself raised an error.
                logger.info(f"報告 ID {report_id} 的 metadata 更新完成，但無實際行變更 (可能 metadata 未改變)。", extra={"props": {**log_props, "db_operation_status": "success_no_change", "rows_affected": row_count}})
                return True # If no error and report was found, consider it a success even if no rows changed.

        except json.JSONDecodeError as e_json:
            logger.error(f"解析報告 ID {report_id} 的現有 metadata 失敗: {e_json}", exc_info=True, extra={"props": {**log_props, "error": "json_decode_error", "error_message": str(e_json)}})
            return False
        except Exception as e: # Catch errors from _execute_query or other issues
            logger.error(
                f"更新報告 ID {report_id} 的 metadata 時發生錯誤: {e}", exc_info=False, # _execute_query logs with exc_info=True if it's a db error
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def check_report_exists_by_source_path(self, source_path: str) -> bool:
        """根據來源路徑檢查報告是否已存在於資料庫中。

        此方法用於在處理新報告前，透過其唯一的 `source_path`（例如檔案在雲端儲存中的路徑）
        來判斷該報告是否已經被登錄到資料庫中，以避免重複處理。

        Args:
            source_path (str): 要檢查的報告的來源路徑。

        Returns:
            bool: 如果具有相同 `source_path` 的報告已存在於資料庫中，則返回 True；
                  否則返回 False。如果在查詢過程中發生錯誤，也會記錄錯誤並返回 False。
        """
        query = "SELECT 1 FROM reports WHERE source_path = ? LIMIT 1"
        try:
            result = await self._execute_query(self.reports_db_path, query, (source_path,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"檢查報告是否存在 (source_path: {source_path}) 時失敗: {e}", exc_info=True, extra={"props": {"source_path": source_path, "operation": "check_report_exists", "error": str(e)}})
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

    # Methods get_prompt_template_by_name and get_all_prompt_templates are read-only,
    # less critical for adding 'extra' unless specific errors in them need richer context.
    # For now, _execute_query will catch and log their query errors with context.

    # ... (rest of the DAL, including prompt methods and __main__ test block, remains largely unchanged for logging 'extra') ...
    # ... (get_prompt_template_by_name and get_all_prompt_templates will benefit from _execute_query's error logging) ...
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

# __main__ block for testing DAL (copied, no changes needed for 'extra' here as it's for testing)
# 注意: get_all_reports 方法是在 __main__ 塊中使用的，但在 DataAccessLayer 類定義中並未明確提供。
# 如果這是一個預期功能，它應該被添加到類定義中。
# 假設它是測試腳本中的一個輔助函數或是一個遺漏的方法。
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
            async with aiosqlite.connect(dal_instance.reports_db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, (limit, offset))
                rows = await cursor.fetchall()
                await cursor.close()
                return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"測試中查詢所有報告失敗: {e}", exc_info=True)
            return []

    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    test_reports_db = os.path.join(data_dir, 'test_reports.sqlite')
    test_prompts_db = os.path.join(data_dir, 'test_prompts.sqlite')
    if os.path.exists(test_reports_db): os.remove(test_reports_db)
    if os.path.exists(test_prompts_db): os.remove(test_prompts_db)
    async def main() -> None:
        """此主函數用於在直接執行此腳本時，對 DataAccessLayer 的功能進行基本測試。

        它會建立測試用的 SQLite 資料庫檔案，初始化 DataAccessLayer，
        執行一系列的資料插入和更新操作，並打印結果到控制台。
        測試完成後，會提示測試資料庫檔案的路徑。
        注意：此函數主要用於開發和基本驗證，並非正式的單元測試套件。
        """
        dal = DataAccessLayer(reports_db_path=test_reports_db, prompts_db_path=test_prompts_db)
        logger.info("---- 開始 DataAccessLayer 功能測試 (包含 analysis_json) ----")
        await dal.initialize_databases()
        logger.info("\n---- 測試「報告」相關功能 (包含 analysis_json) ----")
        report_id1 = await dal.insert_report_data("公司週報_2025_第23週.docx", "這是第一份提交的公司內部週報內容。", "/drive/wolf_in/公司週報_2025_第23週.docx", {"author": "王明", "version": "1.0"}, status="內容已解析")
        report_id2 = await dal.insert_report_data("產品月度總結報告.pdf", "這是產品月度總結報告的原始文字。", "/drive/wolf_in/產品月度總結報告.pdf", {"department": "產品部"}, status="內容已解析")
        if report_id1:
            retrieved_report1_before_analysis = await dal.get_report_by_id(report_id1)
            logger.info(f"獲取報告 ID {report_id1} (分析前): {retrieved_report1_before_analysis}")
            analysis_content_1 = {"主要發現": "本週業績良好", "潛在風險": "市場競爭加劇", "建議行動": "加大研發投入"}
            await dal.update_report_analysis(report_id1, json.dumps(analysis_content_1, ensure_ascii=False), "分析完成") # ensure_ascii=False 處理中文
            retrieved_report1_after_analysis = await dal.get_report_by_id(report_id1)
            logger.info(f"獲取報告 ID {report_id1} (分析後): {retrieved_report1_after_analysis}")
        if report_id2:
            await dal.update_report_status(report_id2, "處理中", "這是經過 AI 分析和總結後的產品月度總結報告內容。")
            retrieved_report2_before_analysis = await dal.get_report_by_id(report_id2)
            logger.info(f"獲取報告 ID {report_id2} (分析前，狀態更新後): {retrieved_report2_before_analysis}")
            analysis_content_2 = {"錯誤": "AI分析時遇到內部錯誤"}
            await dal.update_report_analysis(report_id2, json.dumps(analysis_content_2, ensure_ascii=False), "分析失敗") # ensure_ascii=False 處理中文
            retrieved_report2_after_analysis = await dal.get_report_by_id(report_id2)
            logger.info(f"獲取報告 ID {report_id2} (分析失敗後): {retrieved_report2_after_analysis}")

        # 使用上面定義的測試輔助函數
        all_reports = await get_all_reports_for_testing(dal, limit=5)
        logger.info(f"資料庫中所有報告 (部分欄位，最多5條): {all_reports}")

        if report_id1 and retrieved_report1_after_analysis:
            analysis_json_from_db = retrieved_report1_after_analysis.get('analysis_json')
            if analysis_json_from_db:
                analysis_data_from_db = json.loads(analysis_json_from_db)
                logger.info(f"報告 ID {report_id1} 從資料庫解析出的 analysis_data: {analysis_data_from_db}")
                if analysis_data_from_db.get("主要發現") != "本週業績良好": logger.error(f"錯誤：報告 ID {report_id1} 的分析結果與預期不符！")
            else: logger.error(f"錯誤：報告 ID {report_id1} 的 analysis_json 為空！")
        logger.info("\n---- 測試「提示詞範本」相關功能 (無變動) ----")
        prompt_id_test = await dal.insert_prompt_template("測試提示","測試內容")
        logger.info(f"已插入測試提示ID: {prompt_id_test}")
        logger.info(f"\n測試完畢。測試用的資料庫檔案位於目錄: {data_dir}")
    if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
