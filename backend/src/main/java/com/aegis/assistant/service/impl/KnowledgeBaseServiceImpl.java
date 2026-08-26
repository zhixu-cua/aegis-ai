package com.aegis.assistant.service.impl;

import java.io.File;
import java.nio.file.Files;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import com.aegis.assistant.dto.CreateDatasourceDTO;
import com.aegis.assistant.dto.DatasourceDetailVO;
import com.aegis.assistant.dto.DatasourceStatusVO;
import com.aegis.assistant.dto.DatasourceVO;
import com.aegis.assistant.dto.DocumentVO;
import com.aegis.assistant.dto.UpdateDatasourceDTO;
import com.aegis.assistant.entity.KbDatasource;
import com.aegis.assistant.entity.User;
import com.aegis.assistant.repository.KbDatasourceRepository;
import com.aegis.assistant.repository.UserRepository;
import com.aegis.assistant.service.KnowledgeBaseService;
import com.aegis.assistant.service.SaTokenService;
import com.aegis.assistant.util.RedisStreamUtil;
import com.qcloud.cos.COSClient;
import com.qcloud.cos.ClientConfig;
import com.qcloud.cos.auth.BasicCOSCredentials;
import com.qcloud.cos.model.PutObjectRequest;
import com.qcloud.cos.region.Region;

@Service
public class KnowledgeBaseServiceImpl implements KnowledgeBaseService {
    
    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseServiceImpl.class);

    private final KbDatasourceRepository datasourceRepository;
    private final com.aegis.assistant.repository.KbDocumentRepository documentRepository;
    private final RedisStreamUtil redisStreamUtil;
    private final SaTokenService saTokenService;
    private final UserRepository userRepository;
    
    public KnowledgeBaseServiceImpl(KbDatasourceRepository datasourceRepository, com.aegis.assistant.repository.KbDocumentRepository documentRepository, RedisStreamUtil redisStreamUtil, SaTokenService saTokenService, UserRepository userRepository) {
        this.datasourceRepository = datasourceRepository;
        this.documentRepository = documentRepository;
        this.redisStreamUtil = redisStreamUtil;
        this.saTokenService = saTokenService;
        this.userRepository = userRepository;
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
        datasource.setIsShared(dto.getIsShared() != null ? dto.getIsShared() : false);
        
        if ("local".equals(dto.getSourceType())) {
            String basePath = System.getProperty("user.dir") + java.io.File.separator + "data" + java.io.File.separator + "knowledge";
            // 此时id还没生成，用时间戳作为唯一标识
            String managedPath = basePath + java.io.File.separator + tenantId + java.io.File.separator + "ds_" + System.currentTimeMillis();
            
            java.io.File dir = new java.io.File(managedPath);
            if (!dir.exists()) {
                dir.mkdirs();
            }
            
            java.util.Map<String, Object> config = datasource.getSourceConfig();
            if (config == null) {
                config = new java.util.HashMap<>();
            }
            config.put("path", managedPath);
            datasource.setSourceConfig(config);
        }
        
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

        // 若数据源处于启用状态，配置变更后立即重新同步并重建监听，确保新配置（路径/频率）立即生效
        if ("active".equals(datasource.getStatus())) {
            String path = extractSyncPath(datasource);
            if (path != null && !path.isEmpty()) {
                // 先停止旧监听，再触发同步，最后按新频率决定是否重启监听
                stopRealtimeListener(id);
                forceRefresh(id, path);
                if ("realtime".equals(datasource.getSyncFrequency())) {
                    startRealtimeListener(id, path, datasource.getTenantId());
                }
            }
        }
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

        // 提取同步路径（local 用 path，cos 用 prefix）
        String path = extractSyncPath(datasource);

        // 启用后立即触发一次全量同步，确保马上能看到效果，而不是只能等下一次定时任务
        if (path != null && !path.isEmpty()) {
            forceRefresh(id, path);
        }

        // 只有“实时同步”才启动文件监听（watchdog）；“每小时/每天”由定时任务 DatasourceSyncTask 负责
        if ("realtime".equals(datasource.getSyncFrequency())) {
            startRealtimeListener(id, path, datasource.getTenantId());
        } else {
            stopRealtimeListener(id);
        }

        log.info("启用同步: datasource_id={}, syncFrequency={}, path={}", id, datasource.getSyncFrequency(), path);
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
        User user = userRepository.findById(Long.parseLong(tenantId)).orElse(null);
        List<KbDatasource> sources;
        if (user != null && "admin".equalsIgnoreCase(user.getRole())) {
            sources = datasourceRepository.findByTenantIdOrIsSharedTrue(tenantId);
        } else {
            sources = datasourceRepository.findByTenantId(tenantId);
        }
        return sources.stream()
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

    @Override
    public void uploadDocument(Long datasourceId, MultipartFile file) {
        KbDatasource datasource = findAndValidate(datasourceId);
        if (!"cos".equals(datasource.getSourceType())) {
            throw new RuntimeException("仅支持上传到 COS 类型的数据源");
        }

        java.util.Map<String, Object> config = datasource.getSourceConfig();
        String secretId = (String) config.get("secretId");
        String secretKey = (String) config.get("secretKey");
        String regionStr = (String) config.get("region");
        String bucket = (String) config.get("bucket");
        String prefix = (String) config.get("prefix");

        if (secretId == null || secretKey == null || regionStr == null || bucket == null) {
            throw new RuntimeException("COS 配置不完整");
        }

        if (prefix == null || prefix.isEmpty()) {
            prefix = "";
        } else if (!prefix.endsWith("/")) {
            prefix = prefix + "/";
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null) {
            originalFilename = "unknown";
        }
        
        // Remove leading slash if any in prefix, for key generation
        String keyPrefix = prefix.startsWith("/") ? prefix.substring(1) : prefix;
        String key = keyPrefix + originalFilename;

        File tempFile = null;
        COSClient cosClient = null;
        try {
            tempFile = Files.createTempFile("upload_", originalFilename).toFile();
            file.transferTo(tempFile);

            BasicCOSCredentials cred = new BasicCOSCredentials(secretId, secretKey);
            Region region = new Region(regionStr);
            ClientConfig clientConfig = new ClientConfig(region);
            cosClient = new COSClient(cred, clientConfig);

            PutObjectRequest putObjectRequest = new PutObjectRequest(bucket, key, tempFile);
            cosClient.putObject(putObjectRequest);
            
            log.info("文件上传到 COS 成功: bucket={}, key={}", bucket, key);

            // 触发解析，相当于强制刷新这个文件
            // 保持和 COS Key 一致的路径作为 filePath 参数
            forceRefresh(datasourceId, key);

        } catch (Exception e) {
            log.error("上传文件到 COS 失败", e);
            throw new RuntimeException("上传文件失败: " + e.getMessage());
        } finally {
            if (cosClient != null) {
                cosClient.shutdown();
            }
            if (tempFile != null && tempFile.exists()) {
                tempFile.delete();
            }
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
        vo.setIsShared(ds.getIsShared() != null ? ds.getIsShared() : false);
        return vo;
    }
    
    private String extractPath(java.util.Map<String, Object> sourceConfig) {
        if (sourceConfig != null && sourceConfig.containsKey("path")) {
            return String.valueOf(sourceConfig.get("path"));
        }
        return "";
    }

    /**
     * 提取数据源的同步路径/前缀：
     * - local 类型取 sourceConfig.path（文件夹路径）
     * - cos 类型取 sourceConfig.prefix（对象前缀，为空则用 "/"）
     */
    private String extractSyncPath(KbDatasource datasource) {
        java.util.Map<String, Object> config = datasource.getSourceConfig();
        if (config == null) {
            return "";
        }
        if ("cos".equals(datasource.getSourceType())) {
            String prefix = config.containsKey("prefix") ? String.valueOf(config.get("prefix")) : "";
            return (prefix == null || prefix.isEmpty()) ? "/" : prefix;
        }
        return config.containsKey("path") ? String.valueOf(config.get("path")) : "";
    }

    private void startRealtimeListener(Long id, String path, String tenantId) {
        if (path == null || path.isEmpty()) {
            return;
        }
        // 兼容 Windows 路径中的反斜杠，防止 JSON 字符串格式化时出现异常
        String normalizedPath = path.replace("\\", "\\\\");
        redisStreamUtil.publish("listener_command", String.format(
            "{\"action\":\"start\",\"datasource_id\":%d,\"path\":\"%s\",\"tenant_id\":\"%s\"}",
            id, normalizedPath, tenantId
        ));
    }

    private void stopRealtimeListener(Long id) {
        redisStreamUtil.publish("listener_command", String.format(
            "{\"action\":\"stop\",\"datasource_id\":%d}", id
        ));
    }
}