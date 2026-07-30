package com.aegis.assistant.controller;

import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import com.aegis.assistant.config.Result;
import com.aegis.assistant.entity.AssistantAuditLog;
import com.aegis.assistant.entity.KbDocument;
import com.aegis.assistant.repository.AssistantAuditLogRepository;
import com.aegis.assistant.repository.KbDocumentRepository;

import cn.dev33.satoken.stp.StpUtil;

@RestController
@RequestMapping("/kb")
public class KbController {

    private final KbDocumentRepository kbDocumentRepository;

    private final AssistantAuditLogRepository logRepository;

    private final RestTemplate restTemplate;

    public KbController(KbDocumentRepository kbDocumentRepository, AssistantAuditLogRepository logRepository) {
        this.kbDocumentRepository = kbDocumentRepository;
        this.logRepository = logRepository;
        
        org.springframework.http.client.SimpleClientHttpRequestFactory factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(300000); // 5 minutes
        factory.setReadTimeout(300000);    // 5 minutes
        this.restTemplate = new RestTemplate(factory);
    }

//    private static final String UPLOAD_DIR = "data/uploads";
    private static final String UPLOAD_DIR = System.getProperty("user.dir") + File.separator + "data" + File.separator + "uploads";
    private static final String FASTAPI_INGEST_URL = "http://127.0.0.1:8000/internal/rag/ingest";

    @PostMapping("/upload")
    public Result<KbDocument> uploadDocument(@RequestParam("file") MultipartFile file) {
        if (file.isEmpty()) {
            return Result.error(400, "文件不能为空");
        }

        try {
            // 确保目录存在
            File dir = new File(UPLOAD_DIR);
            if (!dir.exists()) {
                dir.mkdirs();
            }

            // 获取原始文件名并构建存储路径
            String originalFilename = file.getOriginalFilename();
            if (originalFilename == null) {
                originalFilename = "unknown";
            }
            String fileName = System.currentTimeMillis() + "_" + originalFilename;
            Path filePath = Paths.get(UPLOAD_DIR, fileName);
            String absolutePath = filePath.toAbsolutePath().toString();

            // 保存文件到本地
            file.transferTo(filePath.toFile());

            // 提取文件类型
            String fileType = "";
            int dotIndex = originalFilename.lastIndexOf(".");
            if (dotIndex > 0) {
                fileType = originalFilename.substring(dotIndex + 1);
            }

            // 获取当前登录用户
            Long userId = StpUtil.getLoginIdAsLong();

            // 保存数据库记录
            KbDocument document = new KbDocument();
            document.setFileName(originalFilename);
            document.setFileType(fileType);
            document.setStoragePath(absolutePath);
            document.setStatus("PENDING");
            document.setUploadUserId(userId);
            
            kbDocumentRepository.save(document);

            // 记录上传日志
            AssistantAuditLog log = new AssistantAuditLog();
            log.setUserId(userId);
            log.setActionType("FILE_UPLOAD");
            log.setRequestSummary("User uploaded file: " + originalFilename);
            log.setResultFlag("SUCCESS");
            log.setCreateTime(new Date());
            logRepository.save(log);

            // 异步调用 FastAPI 的 ingest 接口
            CompletableFuture.runAsync(() -> {
                try {
                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    
                    Map<String, Object> requestBody = new HashMap<>();
                    requestBody.put("documentId", document.getId());
                    requestBody.put("filePath", absolutePath);
                    
                    HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);
                    restTemplate.postForObject(FASTAPI_INGEST_URL, request, String.class);
                } catch (Exception e) {
                    System.err.println("调用 FastAPI 解析接口失败: " + e.getMessage());
                    e.printStackTrace();
                    // 这里可以更新状态为 FAILED，但需要新起一个事务或直接保存
                    document.setStatus("FAILED");
                    document.setParseMessage("调用解析接口失败: " + e.getMessage());
                    kbDocumentRepository.save(document);
                }
            });

            return Result.success(document);

        } catch (IOException e) {
            e.printStackTrace();
            return Result.error(500, "文件上传失败: " + e.getMessage());
        }
    }

    @GetMapping("/list")
    public Result<List<KbDocument>> listDocuments() {
        try {
            List<KbDocument> documents = kbDocumentRepository.findAllByOrderByUploadTimeDesc();
            return Result.success(documents);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error(500, "获取文档列表失败: " + e.getMessage());
        }
    }

    @DeleteMapping("/{id}")
    public Result<Void> deleteDocument(@PathVariable Long id) {
        try {
            if (!kbDocumentRepository.existsById(id)) {
                return Result.error(404, "文档不存在");
            }
            // 记录删除日志
            AssistantAuditLog log = new AssistantAuditLog();
            log.setUserId(StpUtil.getLoginIdAsLong());
            log.setActionType("FILE_DELETE");
            log.setRequestSummary("User deleted document: " + id);
            log.setResultFlag("SUCCESS");
            log.setCreateTime(new Date());
            logRepository.save(log);

            kbDocumentRepository.deleteById(id);
            // 理论上这里还应该调用 FastAPI 去删除 pgvector 里的向量，为保持流程这里先实现基础删除
            return Result.success(null);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error(500, "删除文档失败: " + e.getMessage());
        }
    }
}
