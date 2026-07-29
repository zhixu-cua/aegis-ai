package com.aegis.assistant.repository;

import com.aegis.assistant.entity.AssistantMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface AssistantMessageRepository extends JpaRepository<AssistantMessage, Long> {
    List<AssistantMessage> findBySessionIdOrderByMessageTimeAsc(Long sessionId);
}
