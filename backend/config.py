# -*- coding: utf-8 -*-
import os
from typing import Optional

# Assuming Pydantic V1 based on previous check.
# If ImportError occurs, this might need to be changed to:
# from pydantic_settings import BaseSettings, SettingsConfigDict
# from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings # Updated import for Pydantic V2
from pydantic import Field, SecretStr # Field and SecretStr remain in pydantic

def get_env(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """Helper to get environment variable, stripping quotes if present."""
    value = os.getenv(var_name, default)
    if value and value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value

class Settings(BaseSettings):
    OPERATION_MODE: str = Field(default=get_env("OPERATION_MODE", "transient"), description="操作模式 (例如：\"transient\" 或 \"persistent\")")
    API_KEY_FRED: Optional[SecretStr] = Field(default=get_env("API_KEY_FRED"), description="用於 FRED 的 API 金鑰 (可選)")
    API_KEY_FINMIND: Optional[SecretStr] = Field(default=get_env("API_KEY_FINMIND"), description="用於 FinMind 的 API 金鑰 (可選)")
    API_KEY_FINNHUB: Optional[SecretStr] = Field(default=get_env("API_KEY_FINNHUB"), description="用於 Finnhub 的 API 金鑰 (可選)")
    API_KEY_FMP: Optional[SecretStr] = Field(default=get_env("API_KEY_FMP"), description="用於 Financial Modeling Prep 的 API 金鑰 (可選)")
    ALPHA_VANTAGE_API_KEY: Optional[SecretStr] = Field(default=get_env("ALPHA_VANTAGE_API_KEY"), description="用於 Alpha Vantage 的 API 金鑰 (可選)")
    DEEPSEEK_API_KEY: Optional[SecretStr] = Field(default=get_env("DEEPSEEK_API_KEY"), description="用於 DeepSeek 的 API 金鑰 (可選)")
    GOOGLE_API_KEY: Optional[SecretStr] = Field(default=get_env("GOOGLE_API_KEY"), description="用於 Gemini API 的 Google API 金鑰 (可選)")
    GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT: Optional[SecretStr] = Field(default=get_env("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT"), description="Google Drive 服務帳戶的 JSON 金鑰內容 (可選, 持久模式下需要)")
    WOLF_IN_FOLDER_ID: Optional[str] = Field(default=get_env("WOLF_IN_FOLDER_ID"), description="Google Drive 中用於接收報告的資料夾 ID (可選, 持久模式下排程器需要)")
    WOLF_PROCESSED_FOLDER_ID: Optional[str] = Field(default=get_env("WOLF_PROCESSED_FOLDER_ID"), description="Google Drive 中用於存放已處理報告的資料夾 ID (可選, 持久模式下排程器需要)")
    REPORTS_DB_PATH: Optional[str] = Field(default=get_env("REPORTS_DB_PATH"), description="報告資料庫的檔案路徑 (可選, 若未設定則使用預設路徑)")
    PROMPTS_DB_PATH: Optional[str] = Field(default=get_env("PROMPTS_DB_PATH"), description="提示詞資料庫的檔案路徑 (可選, 若未設定則使用預設路徑)")
    SCHEDULER_INTERVAL_MINUTES: int = Field(default=int(get_env("SCHEDULER_INTERVAL_MINUTES", "15")), description="排程器執行的時間間隔（分鐘）")

    class Config:
        # For Pydantic V2, env_file and env_file_encoding are typically part of SettingsConfigDict
        # However, to minimize changes if an old .env mechanism is used elsewhere,
        # we'll keep these if they don't break. The primary fix is BaseSettings.
        # If .env loading is an issue, model_config would be the way.
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # For Pydantic V2, the recommended way is:
        # from pydantic_settings import SettingsConfigDict
        # model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
