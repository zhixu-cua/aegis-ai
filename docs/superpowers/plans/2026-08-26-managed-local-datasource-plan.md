# Managed Local Datasource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the "Local Folder" data source into a managed local storage model where the backend assigns the path and users upload files directly from the browser.

**Architecture:** Frontend hides manual path input and enables file upload for `local` types. Backend auto-generates a directory under `data/knowledge/` during datasource creation, and saves uploaded files into that directory for the AI service's `watchdog` to pick up.

**Tech Stack:** Vue 3, Spring Boot, Java

---

### Task 1: Update Frontend Datasource Creation

**Files:**
- Modify: `e:\aegis-ai\assistant-web\src\components\CreateDatasourceDialog.vue`

- [ ] **Step 1: Hide path input for local datasources**
In `CreateDatasourceDialog.vue`, find the template block around line 20:
```html
        <template v-if="form.sourceType === 'local'">
          <div class="form-group">
            <label>文件夹路径 *</label>
            <input v-model="form.path" placeholder="/data/knowledge/product" />
          </div>
        </template>
```
Remove this entire `<template v-if="form.sourceType === 'local'">` block. The user no longer needs to input a path.

- [ ] **Step 2: Update submit validation**
In the `<script setup>` block, locate the `submit` function (around line 132):
```javascript
  if (form.value.sourceType === 'local' && !form.value.path) {
    alert('请填写本地文件夹路径')
    return
  }
```
Remove this validation block.

- [ ] **Step 3: Update config payload**
In the `submit` function, update the `config` object logic for `local` (around line 147):
```javascript
    if (form.value.sourceType === 'local') {
      // no path to send
    } else if (form.value.sourceType === 'cos') {
```

- [ ] **Step 4: Commit**
```bash
git add e:\aegis-ai\assistant-web\src\components\CreateDatasourceDialog.vue
git commit -m "feat(ui): remove path input for local datasource creation"
```

### Task 2: Update Backend Creation Logic

**Files:**
- Modify: `e:\aegis-ai\backend\src\main\java\com\aegis\assistant\service\impl\KnowledgeBaseServiceImpl.java`

- [ ] **Step 1: Auto-generate path during creation**
In `KnowledgeBaseServiceImpl.java`, find the `createDatasource` method. Before `datasourceRepository.save(datasource);`, add logic to assign a managed path:
```java
        if ("local".equals(dto.getSourceType())) {
            String basePath = System.getProperty("user.dir") + java.io.File.separator + "data" + java.io.File.separator + "knowledge";
            String managedPath = basePath + java.io.File.separator + tenantId + java.io.File.separator + "ds_" + System.currentTimeMillis();
            
            java.io.File dir = new java.io.File(managedPath);
            if (!dir.exists()) {
                dir.mkdirs();
            }
            
            // sourceConfig could be null from DTO if not passed
            java.util.Map<String, Object> config = dto.getSourceConfig();
            if (config == null) {
                config = new java.util.HashMap<>();
            }
            config.put("path", managedPath);
            datasource.setSourceConfig(config);
        }
```

- [ ] **Step 2: Commit**
```bash
git add e:\aegis-ai\backend\src\main\java\com\aegis\assistant\service\impl\KnowledgeBaseServiceImpl.java
git commit -m "feat(backend): auto-generate managed path for local datasource"
```

### Task 3: Update Backend Upload Logic

**Files:**
- Modify: `e:\aegis-ai\backend\src\main\java\com\aegis\assistant\service\impl\KnowledgeBaseServiceImpl.java`

- [ ] **Step 1: Refactor `uploadDocument` method to support local**
In `KnowledgeBaseServiceImpl.java`, locate the `uploadDocument` method (around line 250). Change the check:
```java
        if (!"cos".equals(datasource.getSourceType()) && !"local".equals(datasource.getSourceType())) {
            throw new RuntimeException("仅支持上传到 COS 或 本地 类型的数据源");
        }
```

- [ ] **Step 2: Implement local file saving logic**
Inside `uploadDocument`, after the type check, add branching for `local`:
```java
        if ("local".equals(datasource.getSourceType())) {
            String path = (String) datasource.getSourceConfig().get("path");
            if (path == null || path.isEmpty()) {
                throw new RuntimeException("本地数据源路径未配置");
            }
            java.io.File dir = new java.io.File(path);
            if (!dir.exists()) {
                dir.mkdirs();
            }
            String originalFilename = file.getOriginalFilename();
            if (originalFilename == null) {
                originalFilename = "unknown_" + System.currentTimeMillis();
            }
            java.io.File destFile = new java.io.File(dir, originalFilename);
            try {
                file.transferTo(destFile);
                log.info("文件上传到本地成功: path={}", destFile.getAbsolutePath());
                // The watchdog will automatically detect this, but we can trigger forceRefresh just in case
                // For local files, the filePath param is just the absolute path
                forceRefresh(datasourceId, destFile.getAbsolutePath());
            } catch (Exception e) {
                log.error("上传文件到本地失败", e);
                throw new RuntimeException("上传文件失败: " + e.getMessage());
            }
            return; // Important: return here to skip COS logic
        }
```
*(Place this before the existing COS logic)*

- [ ] **Step 3: Commit**
```bash
git add e:\aegis-ai\backend\src\main\java\com\aegis\assistant\service\impl\KnowledgeBaseServiceImpl.java
git commit -m "feat(backend): support file upload for local datasources"
```

### Task 4: Update Frontend Upload Button

**Files:**
- Modify: `e:\aegis-ai\assistant-web\src\views\KnowledgeDocumentList.vue`

- [ ] **Step 1: Display upload button for local**
In `KnowledgeDocumentList.vue`, find the upload button (around line 7):
```html
        <label v-if="datasource?.sourceType !== 'local'" class="btn btn-primary upload-btn" ...>
```
Remove the `v-if` condition entirely, or change it to `v-if="datasource?.sourceType === 'local' || datasource?.sourceType === 'cos'"` (but since these are the only two types, just removing it is fine):
```html
        <label class="btn btn-primary upload-btn" :class="{ 'disabled': uploading }" title="支持格式: .txt, .md, .pdf, .docx, .doc, .xlsx, .xls, .csv, .png, .jpg, .jpeg, .html, .htm">
```

- [ ] **Step 2: Update `handleUpload` logic**
In the `<script setup>` block, locate the `handleUpload` function (around line 161):
```javascript
  if (datasource.value?.sourceType !== 'cos') {
    alert('当前数据源不支持 COS 上传');
    target.value = '';
    return;
  }
```
Remove this check, or modify it to support both if other types are added in the future:
```javascript
  if (datasource.value?.sourceType !== 'cos' && datasource.value?.sourceType !== 'local') {
    alert('当前数据源不支持上传');
    target.value = '';
    return;
  }
```

- [ ] **Step 3: Commit**
```bash
git add e:\aegis-ai\assistant-web\src\views\KnowledgeDocumentList.vue
git commit -m "feat(ui): enable file upload for local datasources"
```
