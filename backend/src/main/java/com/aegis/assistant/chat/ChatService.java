package com.aegis.assistant.chat;

import com.aegis.assistant.entity.AssistantSession;
import com.aegis.assistant.entity.AssistantMessage;
import com.aegis.assistant.entity.AssistantAuditLog;
import com.aegis.assistant.repository.AssistantSessionRepository;
import com.aegis.assistant.repository.AssistantMessageRepository;
import com.aegis.assistant.repository.AssistantAuditLogRepository;
import cn.dev33.satoken.stp.StpUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.Date;
import java.util.List;

@Service
public class ChatService {

    private final RestTemplate restTemplate;
    private final AssistantSessionRepository sessionRepository;
    private final AssistantMessageRepository messageRepository;
    private final AssistantAuditLogRepository auditLogRepository;

    @Autowired
    public ChatService(AssistantMessageRepository messageRepository, AssistantSessionRepository sessionRepository, AssistantAuditLogRepository auditLogRepository) {
        this.messageRepository = messageRepository;
        this.sessionRepository = sessionRepository;
        this.auditLogRepository = auditLogRepository;
        
        org.springframework.http.client.SimpleClientHttpRequestFactory factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(300000); // 5 minutes
        factory.setReadTimeout(300000);    // 5 minutes
        this.restTemplate = new RestTemplate(factory);
    }

    private void saveLog(Long userId, String actionType, String requestSummary, String responseSummary, String resultFlag) {
        AssistantAuditLog log = new AssistantAuditLog();
        log.setUserId(userId);
        log.setActionType(actionType);
        log.setRequestSummary(requestSummary);
        log.setResponseSummary(responseSummary);
        log.setResultFlag(resultFlag);
        log.setCreateTime(new Date());
        auditLogRepository.save(log);
    }

    public ChatResponse chat(ChatRequest request) {
        long userId = StpUtil.getLoginIdAsLong();
        Long sessionId = request.getSessionId();

        if (sessionId == null) {
            AssistantSession session = createSession(userId, "新对话");
            sessionId = session.getId();
        }

        AssistantSession session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new RuntimeException("会话不存在"));

        if (session.getSessionTitle() == null || session.getSessionTitle().equals("新对话")) {
            String title = request.getQuestion().length() > 12 
                    ? request.getQuestion().substring(0, 12) + "..." 
                    : request.getQuestion();
            session.setSessionTitle(title);
        }
        session.setLastActiveTime(new Date());
        sessionRepository.save(session);

        AssistantMessage userMsg = new AssistantMessage();
        userMsg.setSessionId(sessionId);
        userMsg.setRole("user");
        userMsg.setContent(request.getQuestion());
        userMsg.setMessageTime(new Date());
        messageRepository.save(userMsg);
        
        saveLog(userId, "CHAT_CALL", request.getQuestion(), null, "PENDING");

        String url = "http://127.0.0.1:8000/internal/rag/query";
        try {
            long startTime = System.currentTimeMillis();
            ChatResponse response = restTemplate.postForObject(url, request, ChatResponse.class);
            long costMs = System.currentTimeMillis() - startTime;
            
            if (response == null || response.getAnswer() == null || response.getAnswer().isBlank()) {
                throw new IllegalStateException("AI 服务返回空结果");
            }
            
            saveLog(userId, "MODEL_CALL", "Requested model", "Model replied in " + costMs + "ms", "SUCCESS");
            
            AssistantMessage aiMsg = new AssistantMessage();
            aiMsg.setSessionId(sessionId);
            aiMsg.setRole("ai");
            aiMsg.setContent(response.getAnswer());
            aiMsg.setMessageTime(new Date());
            aiMsg.setCostMs((int) costMs);
            messageRepository.save(aiMsg);

            return response;
        } catch (RestClientException e) {
            saveLog(userId, "MODEL_CALL", "Requested model", e.getMessage(), "FAILED");
            AssistantMessage errorMsg = new AssistantMessage();
            errorMsg.setSessionId(sessionId);
            errorMsg.setRole("ai");
            errorMsg.setContent("无法连接 AI 服务，请确认 FastAPI 与 Ollama 已启动: " + e.getMessage());
            errorMsg.setMessageTime(new Date());
            messageRepository.save(errorMsg);

            throw new IllegalStateException("无法连接 AI 服务，请确认 FastAPI 与 Ollama 已启动: " + e.getMessage(), e);
        }
    }

    public List<AssistantSession> getSessions(Long userId) {
        return sessionRepository.findByUserIdOrderByLastActiveTimeDesc(userId);
    }

    public AssistantSession createSession(Long userId, String title) {
        AssistantSession session = new AssistantSession();
        session.setUserId(userId);
        session.setSessionTitle(title != null ? title : "新对话");
        session.setCreateTime(new Date());
        session.setLastActiveTime(new Date());
        return sessionRepository.save(session);
    }

    public void deleteSession(Long userId, Long sessionId) {
        AssistantSession session = sessionRepository.findById(sessionId).orElse(null);
        if (session != null && session.getUserId().equals(userId)) {
            messageRepository.deleteAll(messageRepository.findBySessionIdOrderByMessageTimeAsc(sessionId));
            sessionRepository.delete(session);
        }
    }

    public List<AssistantMessage> getMessages(Long userId, Long sessionId) {
        AssistantSession session = sessionRepository.findById(sessionId).orElse(null);
        if (session == null || !session.getUserId().equals(userId)) {
            throw new RuntimeException("无权访问该会话");
        }
        return messageRepository.findBySessionIdOrderByMessageTimeAsc(sessionId);
    }
}
