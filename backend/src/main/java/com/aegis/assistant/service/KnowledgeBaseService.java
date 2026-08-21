package com.aegis.assistant.service;

import com.aegis.assistant.dto.*;
import java.util.List;

public interface KnowledgeBaseService {
    Long createDatasource(CreateDatasourceDTO dto);
    void updateDatasource(Long id, UpdateDatasourceDTO dto);
    void deleteDatasource(Long id);
    void enableSync(Long id);
    void disableSync(Long id);
    void forceRefresh(Long id, String filePath);
    DatasourceStatusVO getStatus(Long id);
    DatasourceDetailVO getDatasourceDetail(Long id);
    List<DatasourceVO> listDatasources();
    org.springframework.data.domain.Page<DocumentVO> listDocuments(Long id, String status, Integer page, Integer size);
    void deleteDocument(Long datasourceId, Long documentId);
    void uploadDocument(Long datasourceId, org.springframework.web.multipart.MultipartFile file);
}
