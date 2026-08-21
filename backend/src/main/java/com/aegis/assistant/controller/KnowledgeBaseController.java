package com.aegis.assistant.controller;

import com.aegis.assistant.dto.*;
import com.aegis.assistant.service.KnowledgeBaseService;
import com.aegis.assistant.config.Result;
import cn.dev33.satoken.annotation.SaCheckLogin;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/knowledge")
@SaCheckLogin
public class KnowledgeBaseController {
    
    private final KnowledgeBaseService kbService;
    
    public KnowledgeBaseController(KnowledgeBaseService kbService) {
        this.kbService = kbService;
    }
    
    /**
     * 获取当前用户的所有数据源
     */
    @GetMapping("/datasources")
    public Result<List<DatasourceVO>> listDatasources() {
        return Result.success(kbService.listDatasources());
    }
    
    /**
     * 创建数据源
     */
    @PostMapping("/datasource")
    public Result<Long> createDatasource(@RequestBody CreateDatasourceDTO dto) {
        return Result.success(kbService.createDatasource(dto));
    }
    
    /**
     * 更新数据源
     */
    @PutMapping("/datasource/{id}")
    public Result<Void> updateDatasource(
            @PathVariable Long id,
            @RequestBody UpdateDatasourceDTO dto) {
        kbService.updateDatasource(id, dto);
        return Result.success();
    }
    
    /**
     * 删除数据源
     */
    @DeleteMapping("/datasource/{id}")
    public Result<Void> deleteDatasource(@PathVariable Long id) {
        kbService.deleteDatasource(id);
        return Result.success();
    }
    
    /**
     * 启用同步
     */
    @PostMapping("/datasource/{id}/sync/enable")
    public Result<Void> enableSync(@PathVariable Long id) {
        kbService.enableSync(id);
        return Result.success();
    }
    
    /**
     * 禁用同步
     */
    @PostMapping("/datasource/{id}/sync/disable")
    public Result<Void> disableSync(@PathVariable Long id) {
        kbService.disableSync(id);
        return Result.success();
    }
    
    /**
     * 获取数据源状态
     */
    @GetMapping("/datasource/{id}/status")
    public Result<DatasourceStatusVO> getStatus(@PathVariable Long id) {
        return Result.success(kbService.getStatus(id));
    }
    
    /**
     * 获取数据源详细信息
     */
    @GetMapping("/datasource/{id}")
    public Result<DatasourceDetailVO> getDatasourceDetail(@PathVariable Long id) {
        return Result.success(kbService.getDatasourceDetail(id));
    }
    
    /**
     * 强制刷新单个文档（热更新）
     */
    @PostMapping("/datasource/{id}/refresh")
    public Result<Void> forceRefresh(
            @PathVariable Long id,
            @RequestParam String filePath) {
        kbService.forceRefresh(id, filePath);
        return Result.success();
    }
    
    /**
     * 获取数据源的文档列表
     */
    @GetMapping("/datasource/{id}/documents")
    public Result<org.springframework.data.domain.Page<DocumentVO>> listDocuments(
            @PathVariable Long id,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size) {
        return Result.success(kbService.listDocuments(id, status, page, size));
    }

    /**
     * 删除指定的文档
     */
    @DeleteMapping("/datasource/{id}/documents/{docId}")
    public Result<Void> deleteDocument(@PathVariable Long id, @PathVariable Long docId) {
        kbService.deleteDocument(id, docId);
        return Result.success();
    }

    /**
     * 上传文档到数据源
     */
    @PostMapping("/datasource/{id}/upload")
    public Result<Void> uploadDocument(
            @PathVariable Long id,
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        kbService.uploadDocument(id, file);
        return Result.success();
    }
}