package com.aegis.assistant.repository;

import com.aegis.assistant.entity.KbDocument;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface KbDocumentRepository extends JpaRepository<KbDocument, Long> {
    List<KbDocument> findAllByOrderByUploadTimeDesc();
    List<KbDocument> findByDatasourceIdOrderByUpdatedAtDesc(Long datasourceId);
    Page<KbDocument> findByDatasourceIdOrderByUpdatedAtDesc(Long datasourceId, Pageable pageable);

    @Modifying
    @Query(value = "DELETE FROM kb_chunk WHERE document_id = :documentId", nativeQuery = true)
    void deleteChunksByDocumentId(@Param("documentId") Long documentId);

    @Modifying
    @Query(value = "UPDATE kb_datasource SET total_doc_count = (SELECT COUNT(*) FROM kb_document WHERE datasource_id = :datasourceId AND status = 'completed'), last_sync_at = NOW() WHERE id = :datasourceId", nativeQuery = true)
    void updateDatasourceCount(@Param("datasourceId") Long datasourceId);
}
