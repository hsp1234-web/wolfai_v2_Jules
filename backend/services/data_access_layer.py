import aiosqlite
import logging
import os
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class DataAccessLayer:
    def __init__(self, reports_db_path: str, prompts_db_path: str):
        self.reports_db_path = reports_db_path
        self.prompts_db_path = prompts_db_path
        logger.info(
            f"DataAccessLayer 配置使用報告資料庫於: '{self.reports_db_path}' 及提示詞資料庫於: '{self.prompts_db_path}'.",
            extra={"props": {"service_name": "DataAccessLayer", "status": "configured", "reports_db": reports_db_path, "prompts_db": prompts_db_path}}
        )

    async def _execute_query(self, db_path: str, query: str, params: tuple = (), fetch_one=False, fetch_all=False, commit=False):
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"資料庫目錄 '{db_dir}' 不存在，已創建。", extra={"props": {"db_path": db_path, "action": "create_directory"}})
            except Exception as e_mkdir:
                logger.error(f"創建資料庫目錄 '{db_dir}' 失敗: {e_mkdir}", exc_info=True, extra={"props": {"db_path": db_path, "error": str(e_mkdir)}})
                raise # Re-raise if directory creation is critical

        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(query, params)
                if commit:
                    await db.commit()
                    if query.strip().upper().startswith("INSERT"):
                        id_cursor = await db.execute("SELECT last_insert_rowid()")
                        last_id_row = await id_cursor.fetchone()
                        await id_cursor.close()
                        return last_id_row[0] if last_id_row else None
                    return None
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
            # Add context to errors happening during query execution
            logger.error(
                f"執行資料庫查詢失敗。DB: '{db_path}', Query: '{query[:100]}...' (參數: {params})", # Log first 100 chars of query
                exc_info=True,
                extra={"props": {"db_path": db_path, "query_snippet": query[:100], "params": str(params), "error": str(e_query)}}
            )
            raise # Re-raise to be handled by calling method

    async def initialize_databases(self):
        await self._create_reports_table()
        await self._create_prompts_table()
        logger.info("資料庫初始化完成 (如果需要)。", extra={"props": {"operation": "initialize_databases", "status": "completed"}})

    async def _create_reports_table(self):
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
        logger.info(f"'reports' 表已在 '{self.reports_db_path}' 中確認/創建。", extra={"props": {"db_table": "reports", "db_path": self.reports_db_path}})

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
        logger.info(f"'prompt_templates' 表已在 '{self.prompts_db_path}' 中確認/創建。", extra={"props": {"db_table": "prompt_templates", "db_path": self.prompts_db_path}})

    async def insert_report_data(self, original_filename: str, content: Optional[str],
                                 source_path: str, metadata: Optional[Dict[str, Any]] = None,
                                 status: str = '已擷取待處理') -> Optional[int]:
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
        query = "SELECT id, original_filename, content, source_path, processed_at, status, metadata, analysis_json FROM reports WHERE id = ?"
        try:
            async with aiosqlite.connect(self.reports_db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, (report_id,))
                row = await cursor.fetchone()
                await cursor.close()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"查詢報告 ID {report_id} 失敗: {e}", exc_info=True, extra={"props": {"report_id": report_id, "operation": "get_report_by_id", "error": str(e)}})
            return None


    async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
        fields_to_update = {"status": status}
        if processed_content is not None:
            fields_to_update["content"] = processed_content
        query_set_parts = [f"{field} = ?" for field in fields_to_update.keys()]
        query_params = list(fields_to_update.values())
        query_params.append(report_id)
        query = f"UPDATE reports SET {', '.join(query_set_parts)}, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        log_props = {"report_id": report_id, "new_status": status, "operation": "update_report_status"}
        try:
            await self._execute_query(self.reports_db_path, query, tuple(query_params), commit=True)
            logger.info(
                f"報告 ID {report_id} 的狀態已更新為 '{status}'。",
                extra={"props": {**log_props, "db_operation_status": "success"}}
            )
            return True
        except Exception as e:
            logger.error(
                f"更新報告 ID {report_id} 狀態失敗: {e}", exc_info=False, # _execute_query logs with exc_info=True
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def update_report_analysis(self, report_id: int, analysis_data: str, status: str) -> bool:
        query = "UPDATE reports SET analysis_json = ?, status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
        log_props = {"report_id": report_id, "new_status": status, "operation": "update_report_analysis"}
        try:
            await self._execute_query(self.reports_db_path, query, (analysis_data, status, report_id), commit=True)
            logger.info(
                f"報告 ID {report_id} 的 AI 分析結果已儲存，狀態更新為 '{status}'。",
                extra={"props": {**log_props, "db_operation_status": "success"}}
            )
            return True
        except Exception as e:
            logger.error(
                f"儲存報告 ID {report_id} 的 AI 分析結果失敗: {e}", exc_info=False,
                extra={"props": {**log_props, "db_operation_status": "failure", "error_message": str(e)}}
            )
            return False

    async def update_report_metadata(self, report_id: int, metadata_update: Dict[str, Any]) -> bool:
        log_props = {"report_id": report_id, "operation": "update_report_metadata"}
        current_report = await self.get_report_by_id(report_id) # get_report_by_id logs its own errors
        if not current_report:
            logger.error(f"更新 metadata 失敗：找不到報告 ID {report_id}。", extra={"props": {**log_props, "error": "report_not_found"}})
            return False
        try:
            current_metadata_str = current_report.get("metadata")
            current_metadata = json.loads(current_metadata_str) if current_metadata_str else {}
            current_metadata.update(metadata_update)
            new_metadata_str = json.dumps(current_metadata, ensure_ascii=False)
            query = "UPDATE reports SET metadata = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?"
            await self._execute_query(self.reports_db_path, query, (new_metadata_str, report_id), commit=True)
            logger.info(f"報告 ID {report_id} 的 metadata 已更新。", extra={"props": {**log_props, "db_operation_status": "success"}})
            return True
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
        query = "SELECT 1 FROM reports WHERE source_path = ? LIMIT 1"
        try:
            result = await self._execute_query(self.reports_db_path, query, (source_path,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"檢查報告是否存在 (source_path: {source_path}) 時失敗: {e}", exc_info=True, extra={"props": {"source_path": source_path, "operation": "check_report_exists", "error": str(e)}})
            return False # Or re-raise depending on desired strictness

    async def insert_prompt_template(self, name: str, template_text: str, category: Optional[str] = None) -> Optional[int]:
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
        query = "SELECT id, name, template_text, category, created_at, updated_at FROM prompt_templates WHERE name = ?"
        try:
            async with aiosqlite.connect(self.prompts_db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, (name,))
                row = await cursor.fetchone()
                await cursor.close()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"查詢提示詞範本 '{name}' 失敗: {e}", exc_info=True, extra={"props": {"prompt_name": name, "operation": "get_prompt_by_name", "error": str(e)}})
            return None

    async def get_all_prompt_templates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = "SELECT id, name, category, updated_at FROM prompt_templates ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        try:
            async with aiosqlite.connect(self.prompts_db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, (limit, offset))
                rows = await cursor.fetchall()
                await cursor.close()
            if rows:
                return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(f"查詢所有提示詞範本失敗: {e}", exc_info=True, extra={"props": {"limit": limit, "offset": offset, "operation": "get_all_prompts", "error": str(e)}})
            return []

# __main__ block for testing DAL (copied, no changes needed for 'extra' here as it's for testing)
if __name__ == '__main__':
    import asyncio
    # ... (rest of __main__ block) ...
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    test_reports_db = os.path.join(data_dir, 'test_reports.sqlite')
    test_prompts_db = os.path.join(data_dir, 'test_prompts.sqlite')
    if os.path.exists(test_reports_db): os.remove(test_reports_db)
    if os.path.exists(test_prompts_db): os.remove(test_prompts_db)
    async def main():
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
            await dal.update_report_analysis(report_id1, json.dumps(analysis_content_1, ensure_ascii=False), "分析完成")
            retrieved_report1_after_analysis = await dal.get_report_by_id(report_id1)
            logger.info(f"獲取報告 ID {report_id1} (分析後): {retrieved_report1_after_analysis}")
        if report_id2:
            await dal.update_report_status(report_id2, "處理中", "這是經過 AI 分析和總結後的產品月度總結報告內容。")
            retrieved_report2_before_analysis = await dal.get_report_by_id(report_id2)
            logger.info(f"獲取報告 ID {report_id2} (分析前，狀態更新後): {retrieved_report2_before_analysis}")
            analysis_content_2 = {"錯誤": "AI分析時遇到內部錯誤"}
            await dal.update_report_analysis(report_id2, json.dumps(analysis_content_2, ensure_ascii=False), "分析失敗")
            retrieved_report2_after_analysis = await dal.get_report_by_id(report_id2)
            logger.info(f"獲取報告 ID {report_id2} (分析失敗後): {retrieved_report2_after_analysis}")
        all_reports = await dal.get_all_reports(limit=5)
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
