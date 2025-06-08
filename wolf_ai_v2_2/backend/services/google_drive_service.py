import os
import logging
import json
import time # For test_main unique naming
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds
# from googleapiclient.errors import HttpError # aiogoogle raises its own errors, typically aiogoogle.excs.HTTPError or similar

# Configure logger (it might be already configured by FastAPI's default/main.py,
# but good to have a specific logger for the service)
logger = logging.getLogger(__name__)
# If run standalone for testing, ensure basicConfig is set.
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Google Drive API Scope
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveService:
    def __init__(self, service_account_info: dict = None, service_account_json_path: str = None):
        """
        Initializes the Google Drive Service.
        Prioritizes service_account_info (dictionary), then service_account_json_path (file path).
        """
        self.service_account_creds = None

        if service_account_info:
            try:
                self.service_account_creds = ServiceAccountCreds(
                    scopes=DRIVE_SCOPES,
                    **service_account_info  # Unpack dictionary for client_email, private_key, etc.
                )
                logger.info("Google Drive Service: Credentials initialized using provided service_account_info.")
            except Exception as e:
                logger.error(f"Google Drive Service: Failed to initialize credentials from service_account_info: {e}", exc_info=True)
                raise ValueError(f"Invalid service_account_info: {e}")
        elif service_account_json_path:
            try:
                if not os.path.exists(service_account_json_path):
                    logger.error(f"Google Drive Service: Service account JSON file path does not exist: {service_account_json_path}")
                    raise FileNotFoundError(f"Service account JSON file not found: {service_account_json_path}")

                with open(service_account_json_path, 'r') as f:
                    sa_info_from_file = json.load(f)

                self.service_account_creds = ServiceAccountCreds(
                    scopes=DRIVE_SCOPES,
                    **sa_info_from_file
                )
                logger.info(f"Google Drive Service: Credentials initialized from JSON file {service_account_json_path}.")
            except Exception as e:
                logger.error(f"Google Drive Service: Failed to initialize credentials from JSON file {service_account_json_path}: {e}", exc_info=True)
                raise ValueError(f"Failed to initialize credentials from JSON file {service_account_json_path}: {e}")
        else:
            logger.error("Google Drive Service: Must provide service_account_info or service_account_json_path.")
            raise ValueError("No valid Google Drive service account credentials provided.")

        self.aiogoogle = Aiogoogle(service_account_creds=self.service_account_creds)
        logger.info("GoogleDriveService initialized, Aiogoogle client configured.")

    async def list_files(self, folder_id: str = 'root', page_size: int = 100, fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, parents)") -> list:
        """
        Lists files and folders in a specified Google Drive folder.
        """
        logger.info(f"Listing files in Drive folder '{folder_id}'...")
        all_files = []
        page_token = None
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                while True:
                    query = f"'{folder_id}' in parents and trashed=false"
                    response = await google.as_service_account(
                        drive_v3.files.list(
                            q=query,
                            pageSize=min(page_size, 1000),
                            fields=fields,
                            pageToken=page_token,
                            corpora="user"
                        )
                    )
                    files = response.get('files', [])
                    all_files.extend(files)
                    page_token = response.get('nextPageToken')
                    if not page_token:
                        break
            logger.info(f"Successfully listed {len(all_files)} items in folder '{folder_id}'.")
            return all_files
        except Exception as e:
            logger.error(f"Error listing files in Drive folder '{folder_id}': {e}", exc_info=True)
            return []

    async def download_file(self, file_id: str, destination_path: str) -> bool:
        """
        Downloads a file from Google Drive.
        """
        logger.info(f"Preparing to download Drive file ID '{file_id}' to '{destination_path}'...")
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')

                file_metadata_req = drive_v3.files.get(fileId=file_id, fields="mimeType, name")
                file_metadata = await google.as_service_account(file_metadata_req)

                if file_metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                    logger.error(f"Error: Item ID '{file_id}' (Name: '{file_metadata.get('name')}') is a folder, cannot be downloaded directly.")
                    return False

                os.makedirs(os.path.dirname(destination_path), exist_ok=True)

                download_req = drive_v3.files.get(
                    fileId=file_id,
                    alt="media",
                    download_file=destination_path
                )
                response = await google.as_service_account(download_req, full_res=True)

                if response.status_code == 200:
                    logger.info(f"File ID '{file_id}' downloaded successfully to '{destination_path}'.")
                    return True
                else:
                    error_content = await response.text()
                    logger.error(f"Failed to download file ID '{file_id}'. Status: {response.status_code}, Response: {error_content}")
                    return False
        except Exception as e:
            logger.error(f"Unexpected error downloading file ID '{file_id}': {e}", exc_info=True)
            return False

    async def upload_file(self, local_file_path: str, folder_id: str = None, file_name: str = None) -> str | None:
        """
        Uploads a local file to Google Drive.
        """
        if not os.path.exists(local_file_path):
            logger.error(f"Local file '{local_file_path}' not found for upload.")
            return None

        drive_file_name = file_name if file_name else os.path.basename(local_file_path)
        logger.info(f"Preparing to upload local file '{local_file_path}' as '{drive_file_name}' to Drive folder ID '{folder_id}'...")

        file_metadata = {'name': drive_file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                response = await google.as_service_account(
                    drive_v3.files.create(
                        upload_file=local_file_path,
                        json=file_metadata,
                        fields='id, name'
                    )
                )
            uploaded_file_id = response.get('id')
            if uploaded_file_id:
                logger.info(f"File '{drive_file_name}' uploaded successfully to Drive. New File ID: {uploaded_file_id}")
                return uploaded_file_id
            else:
                logger.error(f"Upload of file '{drive_file_name}' failed. Drive API did not return a file ID. Response: {response}")
                return None
        except Exception as e:
            logger.error(f"Error uploading file '{drive_file_name}': {e}", exc_info=True)
            return None

    async def create_folder(self, folder_name: str, parent_folder_id: str = None) -> str | None:
        """
        Creates a new folder under the specified parent folder. If parent_folder_id is None, creates in root.
        """
        logger.info(f"Preparing to create folder '{folder_name}' under parent ID '{parent_folder_id if parent_folder_id else 'root'}'...")
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                folder = await google.as_service_account(
                    drive_v3.files.create(json=file_metadata, fields='id, name')
                )
            folder_id = folder.get('id')
            if folder_id:
                logger.info(f"Folder '{folder_name}' (ID: {folder_id}) created successfully.")
                return folder_id
            else:
                logger.error(f"Failed to create folder '{folder_name}'. Drive API did not return an ID. Response: {folder}")
                return None
        except Exception as e:
            logger.error(f"Error creating folder '{folder_name}': {e}", exc_info=True)
            return None

    async def delete_file(self, file_id: str) -> bool:
        """
        Permanently deletes a file or folder from Google Drive.
        """
        logger.info(f"Preparing to permanently delete Drive item ID '{file_id}'...")
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                await google.as_service_account(
                    drive_v3.files.delete(fileId=file_id)
                )
            logger.info(f"Item ID '{file_id}' permanently deleted from Drive.")
            return True
        except Exception as e:
            logger.error(f"Error deleting Drive item ID '{file_id}': {e}", exc_info=True)
            return False

    async def move_file(self, file_id: str, new_parent_folder_id: str, old_parent_folder_id: str = None) -> bool:
        """
        Moves a file to a new folder.
        """
        logger.info(f"Preparing to move file ID '{file_id}' to folder ID '{new_parent_folder_id}'...")
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')

                # To move a file, update its 'parents' field.
                # This involves specifying the new parent and removing the old one(s).
                # First, get current parents to ensure only the specified old_parent_folder_id is removed.
                # This is safer if a file could have multiple parents.
                # For simplicity, if old_parent_folder_id is provided, we use it directly.
                # Otherwise, one might need to fetch the file's current parents.

                update_kwargs = {
                    'fileId': file_id,
                    'addParents': new_parent_folder_id,
                    'fields': 'id, parents' # Request updated parents to confirm
                }
                if old_parent_folder_id:
                    update_kwargs['removeParents'] = old_parent_folder_id

                updated_file = await google.as_service_account(
                    drive_v3.files.update(**update_kwargs)
                )

            if new_parent_folder_id in updated_file.get('parents', []):
                logger.info(f"File ID '{file_id}' moved successfully to folder ID '{new_parent_folder_id}'.")
                return True
            else:
                logger.error(f"Failed to move file ID '{file_id}'. Updated parents: {updated_file.get('parents')}. Response: {updated_file}")
                return False
        except Exception as e:
            logger.error(f"Error moving file ID '{file_id}': {e}", exc_info=True)
            return False

if __name__ == '__main__':
    import asyncio

    async def test_main():
        SERVICE_ACCOUNT_FILE_FOR_TEST = 'your_service_account.json'
        TEST_PARENT_FOLDER_ID = None

        if not os.path.exists(SERVICE_ACCOUNT_FILE_FOR_TEST):
            logger.error(f"Test requires {SERVICE_ACCOUNT_FILE_FOR_TEST}. Create it with your service account JSON.")
            return

        try:
            drive_service = GoogleDriveService(service_account_json_path=SERVICE_ACCOUNT_FILE_FOR_TEST)
        except ValueError as e:
            logger.error(f"Failed to initialize DriveService: {e}")
            return

        logger.info("---- Starting GoogleDriveService Tests (Live API) ----")

        new_folder_name = f"Test_Folder_{int(time.time())}"
        logger.info(f"Test create_folder: Creating '{new_folder_name}'")
        created_folder_id = await drive_service.create_folder(new_folder_name, parent_folder_id=TEST_PARENT_FOLDER_ID)

        if created_folder_id:
            logger.info(f"  SUCCESS: Folder created, ID: {created_folder_id}")

            logger.info(f"Test list_files (in {'root' if not TEST_PARENT_FOLDER_ID else TEST_PARENT_FOLDER_ID}):")
            files = await drive_service.list_files(folder_id=TEST_PARENT_FOLDER_ID if TEST_PARENT_FOLDER_ID else 'root', page_size=5)
            found_our_folder = any(f['id'] == created_folder_id for f in files)
            logger.info(f"  List files complete. Found created folder: {found_our_folder}")
            # for f_item in files: logger.info(f"    - {f_item.get('name')} (ID: {f_item.get('id')}, Type: {f_item.get('mimeType')})")

            test_file_content = "Hello from Wolf AI V2.2 GoogleDriveService live test!"
            local_test_file_path = "temp_upload_test_live.txt"
            with open(local_test_file_path, "w") as f:
                f.write(test_file_content)

            logger.info(f"Test upload_file: Uploading '{local_test_file_path}' to folder ID '{created_folder_id}'")
            uploaded_file_id = await drive_service.upload_file(local_test_file_path, folder_id=created_folder_id)

            if uploaded_file_id:
                logger.info(f"  SUCCESS: File uploaded, ID: {uploaded_file_id}")

                download_destination_path = "temp_downloaded_test_live.txt"
                logger.info(f"Test download_file: Downloading file ID '{uploaded_file_id}' to '{download_destination_path}'")
                download_success = await drive_service.download_file(uploaded_file_id, download_destination_path)
                if download_success:
                    logger.info("  SUCCESS: File downloaded.")
                    with open(download_destination_path, "r") as f:
                        downloaded_content = f.read()
                    assert downloaded_content == test_file_content, "Downloaded content mismatch!"
                    logger.info("  Downloaded content verified successfully!")
                    os.remove(download_destination_path)
                else:
                    logger.error("  FAILURE: File download failed.")

                # Test move_file: Create another folder and move the file into it
                target_folder_name = f"Target_Move_Folder_{int(time.time())}"
                target_folder_id = await drive_service.create_folder(target_folder_name, parent_folder_id=TEST_PARENT_FOLDER_ID)
                if target_folder_id:
                    logger.info(f"  Created target folder for move, ID: {target_folder_id}")
                    logger.info(f"Test move_file: Moving file ID '{uploaded_file_id}' from '{created_folder_id}' to '{target_folder_id}'")
                    move_success = await drive_service.move_file(uploaded_file_id, target_folder_id, old_parent_folder_id=created_folder_id)
                    logger.info(f"  Move operation {'SUCCESSFUL' if move_success else 'FAILED'}")
                    # Clean up moved file and target folder
                    await drive_service.delete_file(uploaded_file_id) # Delete file from new location
                    await drive_service.delete_file(target_folder_id) # Delete the target folder
                else:
                    logger.error("  FAILURE: Could not create target folder for move test.")
                    # Still delete the uploaded file from its original location if move target failed
                    await drive_service.delete_file(uploaded_file_id)


            else: # Upload failed
                logger.error("  FAILURE: File upload failed.")
            if os.path.exists(local_test_file_path):
                os.remove(local_test_file_path)

            logger.info(f"Test delete_file: Deleting main test folder ID '{created_folder_id}'")
            delete_folder_success = await drive_service.delete_file(created_folder_id)
            logger.info(f"  Delete main test folder {'SUCCESSFUL' if delete_folder_success else 'FAILED'}")
        else:
            logger.error("  FAILURE: Initial folder creation failed, subsequent tests skipped.")

        logger.info("---- GoogleDriveService Tests Finished ----")

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(test_main())
