package com.aegis.assistant.service.impl;

import com.aegis.assistant.dto.*;
import com.aegis.assistant.entity.KbDatasource;
import com.aegis.assistant.repository.KbDatasourceRepository;
import com.aegis.assistant.service.KnowledgeBaseService;
import com.aegis.assistant.util.RedisStreamUtil;
import com.aegis.assistant.service.SaTokenService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class KnowledgeBaseServiceImpl implements KnowledgeBaseService {
    
    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseServiceImpl.class);

    private final KbDatasourceRepository datasourceRepository;
    private final com.aegis.assistant.repository.KbDocumentRepository documentRepository;
    private final RedisStreamUtil redisStreamUtil;
    private final SaTokenService saTokenService;
    
    public KnowledgeBaseServiceImpl(KbDatasourceRepository datasourceRepository, com.aegis.assistant.repository.KbDocumentRepository documentRepository, RedisStreamUtil redisStreamUtil, SaTokenService saTokenService) {
        this.datasourceRepository = datasourceRepository;
        this.documentRepository = documentRepository;
        this.redisStreamUtil = redisStreamUtil;
        this.saTokenService = saTokenService;
    }

    @Override
    @Transactional
    public Long createDatasource(CreateDatasourceDTO dto) {
        String tenantId = saTokenService.getCurrentTenantId();
        
        KbDatasource datasource = new KbDatasource();
        datasource.setName(dto.getName());
        datasource.setSourceType(dto.getSourceType());
        
        try {
            java.util.Map<String, Object> configMap = com.alibaba.fastjson.JSON.parseObject(dto.getSourceConfig(), new com.alibaba.fastjson.TypeReference<java.util.Map<String, Object>>() {});
            datasource.setSourceConfig(configMap);
        } catch (Exception e) {
            log.error("Failed to parse source config", e);
        }
        
        datasource.setSyncFrequency(dto.getSyncFrequency());
        datasource.setSourceRank(dto.getSourceRank());
        datasource.setStatus("inactive");
        datasource.setTenantId(tenantId);
        
        KbDatasource saved = datasourceRepository.save(datasource);
        return saved.getId();
    }

    @Override
    @Transactional
    public void updateDatasource(Long id, UpdateDatasourceDTO dto) {
        KbDatasource datasource = findAndValidate(id);
        datasource.setName(dto.getName());
        
        try {
            java.util.Map<String, Object> configMap = com.alibaba.fastjson.JSON.parseObject(dto.getSourceConfig(), new com.alibaba.fastjson.TypeReference<java.util.Map<String, Object>>() {});
            datasource.setSourceConfig(configMap);
        } catch (Exception e) {
            log.error("Failed to parse source config", e);
        }
        
        datasource.setSyncFrequency(dto.getSyncFrequency());
        datasource.setSourceRank(dto.getSourceRank());
        datasourceRepository.save(datasource);
    }

    @Override
    @Transactional
    public void deleteDatasource(Long id) {
        KbDatasource datasource = findAndValidate(id);
        datasourceRepository.delete(datasource);
    }
    
    @Override
    public void enableSync(Long id) {
        KbDatasource datasource = findAndValidate(id);
        datasource.setStatus("active");
        datasource.setLastSyncAt(LocalDateTime.now());
        datasourceRepository.save(datasource);
        
        // 兼容 Windows 路径中的反斜杠，防止 JSON 字符串格式化时出现异常
        String normalizedPath = extractPath(datasource.getSourceConfig()).replace("\\", "\\\\");
        
        // 发送启动监听指令到 AI 服务
        redisStreamUtil.publish("listener_command", String.format(
            "{\"action\":\"start\",\"datasource_id\":%d,\"path\":\"%s\",\"tenant_id\":\"%s\"}",
            id, normalizedPath, datasource.getTenantId()
        ));
        
        log.info("启用同步: datasource_id={}", id);
    }
    
    @Override
    public void disableSync(Long id) {
        KbDatasource datasource = findAndValidate(id);
        datasource.setStatus("inactive");
        datasourceRepository.save(datasource);
        
        // 发送停止监听指令
        redisStreamUtil.publish("listener_command", String.format(
            "{\"action\":\"stop\",\"datasource_id\":%d}",
            id
        ));
        
        log.info("禁用同步: datasource_id={}", id);
    }
    
    @Override
    public void forceRefresh(Long id, String filePath) {
        // 兼容 Windows 路径中的反斜杠，将其替换为正斜杠或转义
        String normalizedPath = filePath.replace("\\", "\\\\");
        // 发送强制刷新事件到 Redis Stream（高优先级）
        redisStreamUtil.publish("doc_events", String.format(
            "{\"datasource_id\":%d,\"event_type\":\"modified\",\"file_path\":\"%s\",\"priority\":\"high\"}",
            id, normalizedPath
        ));
        
        log.info("强制刷新: datasource_id={}, file_path={}", id, filePath);
    }
    
    @Override
    public DatasourceStatusVO getStatus(Long id) {
        KbDatasource datasource = findAndValidate(id);
        DatasourceStatusVO vo = new DatasourceStatusVO();
        vo.setId(datasource.getId());
        vo.setName(datasource.getName());
        vo.setStatus(datasource.getStatus());
        vo.setTotalDocCount(datasource.getTotalDocCount());
        vo.setLastSyncAt(datasource.getLastSyncAt());
        vo.setLastError(datasource.getLastError());
        return vo;
    }
    
    @Override
    public DatasourceDetailVO getDatasourceDetail(Long id) {
        KbDatasource datasource = findAndValidate(id);
        DatasourceDetailVO vo = new DatasourceDetailVO();
        vo.setId(datasource.getId());
        vo.setName(datasource.getName());
        vo.setSourceType(datasource.getSourceType());
        vo.setSourceConfig(datasource.getSourceConfig());
        vo.setSyncFrequency(datasource.getSyncFrequency());
        vo.setSourceRank(datasource.getSourceRank());
        vo.setStatus(datasource.getStatus());
        vo.setTotalDocCount(datasource.getTotalDocCount());
        vo.setLastSyncAt(datasource.getLastSyncAt());
        vo.setLastError(datasource.getLastError());
        return vo;
    }
    
    @Override
    public List<DatasourceVO> listDatasources() {
        String tenantId = saTokenService.getCurrentTenantId();
        return datasourceRepository.findByTenantId(tenantId)
            .stream()
            .map(this::toVO)
            .collect(Collectors.toList());
    }

    @Override
    public Page<DocumentVO> listDocuments(Long id, String status, Integer page, Integer size) {
        Pageable pageable = PageRequest.of(page > 0 ? page - 1 : 0, size > 0 ? size : 20);
        Page<com.aegis.assistant.entity.KbDocument> docs = documentRepository.findByDatasourceIdOrderByUpdatedAtDesc(id, pageable);
        
        return docs.map(doc -> {
            DocumentVO vo = new DocumentVO();
            vo.setId(doc.getId());
            vo.setFileName(doc.getFileName() != null ? doc.getFileName() : "");
            vo.setFilePath(doc.getFilePath() != null ? doc.getFilePath() : "");
            vo.setStatus(doc.getStatus());
            vo.setChunkCount(doc.getChunkCount());
            vo.setProcessedAt(doc.getProcessedAt());
            return vo;
        });
    }

    @Override
    @Transactional
    public void deleteDocument(Long datasourceId, Long documentId) {
        KbDatasource datasource = findAndValidate(datasourceId);
        com.aegis.assistant.entity.KbDocument doc = documentRepository.findById(documentId).orElse(null);
        if (doc != null && doc.getDatasourceId().equals(datasourceId)) {
            // 同步物理删除
            documentRepository.deleteChunksByDocumentId(documentId);
            documentRepository.delete(doc);
            documentRepository.updateDatasourceCount(datasourceId);
            log.info("触发文档物理删除: document_id={}, file_path={}", documentId, doc.getFilePath());
        }
    }
    
    private KbDatasource findAndValidate(Long id) {
        String tenantId = saTokenService.getCurrentTenantId();
        KbDatasource datasource = datasourceRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("数据源不存在"));
        if (!datasource.getTenantId().equals(tenantId)) {
            throw new RuntimeException("无权限访问该数据源");
        }
        return datasource;
    }
    
    private DatasourceVO toVO(KbDatasource ds) {
        DatasourceVO vo = new DatasourceVO();
        vo.setId(ds.getId());
        vo.setName(ds.getName());
        vo.setSourceType(ds.getSourceType());
        vo.setStatus(ds.getStatus());
        vo.setTotalDocCount(ds.getTotalDocCount());
        vo.setLastSyncAt(ds.getLastSyncAt());
        return vo;
    }
    
    private String extractPath(java.util.Map<String, Object> sourceConfig) {
        if (sourceConfig != null && sourceConfig.containsKey("path")) {
            return String.valueOf(sourceConfig.get("path"));
        }
        return "";
    }
}