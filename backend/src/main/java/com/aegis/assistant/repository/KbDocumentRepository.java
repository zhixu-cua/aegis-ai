package com.aegis.assistant.repository;

import com.aegis.assistant.entity.KbDocument;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface KbDocumentRepository extends JpaRepository<KbDocument, Long> {
    List<KbDocument> findAllByOrderByUploadTimeDesc();
}
