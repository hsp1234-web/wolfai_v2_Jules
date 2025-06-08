import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services.report_ingestion_service import ReportIngestionService

logger = logging.getLogger(__name__)

# 這些 ID 應該從配置或環境變數中讀取
# WOLF_IN_FOLDER_ID = os.getenv("WOLF_IN_FOLDER_ID", "default_wolf_in_folder_id")
# WOLF_PROCESSED_FOLDER_ID = os.getenv("WOLF_PROCESSED_FOLDER_ID", "default_wolf_processed_folder_id")

async def trigger_report_ingestion_task(report_ingestion_service: 'ReportIngestionService'):
    """
    異步任務，用於觸發報告擷取服務。
    """
    wolf_in_folder_id = os.getenv("WOLF_IN_FOLDER_ID")
    wolf_processed_folder_id = os.getenv("WOLF_PROCESSED_FOLDER_ID")

    if not wolf_in_folder_id or not wolf_processed_folder_id:
        logger.error("環境變數 WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID 未設定。排程的報告擷取任務無法執行。")
        return

    logger.info(f"排程任務觸發：開始從 Drive 資料夾 '{wolf_in_folder_id}' 擷取報告。")
    try:
        success_count, fail_count = await report_ingestion_service.ingest_reports_from_drive_folder(
            inbox_folder_id=wolf_in_folder_id,
            processed_folder_id=wolf_processed_folder_id
        )
        logger.info(f"排程任務完成：成功擷取 {success_count} 個報告，失敗 {fail_count} 個。")
    except Exception as e:
        logger.error(f"排程的報告擷取任務執行時發生錯誤: {e}", exc_info=True)
