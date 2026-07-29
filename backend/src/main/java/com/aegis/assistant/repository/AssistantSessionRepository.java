package com.aegis.assistant.repository;

import com.aegis.assistant.entity.AssistantSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface AssistantSessionRepository extends JpaRepository<AssistantSession, Long> {
    List<AssistantSession> findByUserIdOrderByLastActiveTimeDesc(Long userId);
}
