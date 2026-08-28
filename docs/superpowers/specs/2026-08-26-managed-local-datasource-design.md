# Managed Local Datasource Design

## 1. Overview
The current "Local Folder" data source expects the user to input a server-side path, which is impractical for non-local remote deployments. This design transitions the `local` data source to a "Managed Local Storage" model where the backend automatically assigns and manages a directory on the server, and users can upload files directly via the frontend.

## 2. Architecture & Components
### 2.1 Frontend Changes
- **Create Datasource Dialog (`CreateDatasourceDialog.vue`)**:
  - Hide the `path` input field when `sourceType === 'local'`.
  - Submit the form without the `path` property for `local` types.
- **Document List (`KnowledgeDocumentList.vue`)**:
  - Remove the restriction that hides the "Upload" button for `local` data sources.
  - Modify the `handleUpload` method to permit file uploads when `sourceType === 'local'` (currently restricted to `cos` only).

### 2.2 Backend Changes
- **Datasource Creation (`KnowledgeBaseServiceImpl.java - createDatasource`)**:
  - Detect if `sourceType` is `local`.
  - Automatically generate a directory path for the tenant and datasource: `[backend_work_dir]/data/knowledge/[tenantId]/ds_[timestamp]`.
  - Ensure the directory is created.
  - Inject this path into the `sourceConfig.path` before saving to the database.
- **File Upload (`KnowledgeBaseServiceImpl.java - uploadDocument`)**:
  - Remove the exception that blocks non-`cos` uploads.
  - If `sourceType` is `local`:
    - Retrieve the managed `path` from `sourceConfig`.
    - Save the incoming `MultipartFile` to this directory.
    - Trigger `forceRefresh(datasourceId, absoluteFilePath)` to ensure the AI service processes it immediately.

### 2.3 AI Service (Python)
- No changes required. The AI service relies on `watchdog` to monitor the folder specified in `sourceConfig.path`.
- When the backend writes the uploaded file to the managed directory, `watchdog` will detect the `on_created` event and automatically publish it to Redis for processing.

## 3. Data Flow
1. **Creation**: User creates `local` datasource -> Backend generates `/data/knowledge/tenant_id/ds_id` -> Backend starts Redis listener event.
2. **Upload**: User uploads file -> Backend saves file to `/data/knowledge/tenant_id/ds_id/file.ext` -> Backend calls `forceRefresh`.
3. **Ingestion**: AI Service's `watchdog` detects file (or receives force refresh event) -> Parses, chunks, and vectorizes into Redis.

## 4. Error Handling
- If backend directory creation fails, return a clear error message.
- Handle file write permissions during upload and return HTTP 500 with context if it fails.
