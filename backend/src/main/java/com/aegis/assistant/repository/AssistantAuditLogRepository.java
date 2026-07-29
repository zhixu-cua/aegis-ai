package com.aegis.assistant.repository;

import com.aegis.assistant.entity.AssistantAuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface AssistantAuditLogRepository extends JpaRepository<AssistantAuditLog, Long> {
}