package com.aegis.assistant.chat;

import java.io.InputStream;
import java.util.Collections;
import java.util.Date;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.aegis.assistant.entity.AssistantAuditLog;
import com.aegis.assistant.entity.AssistantMessage;
import com.aegis.assistant.entity.AssistantSession;
import com.aegis.assistant.repository.AssistantAuditLogRepository;
import com.aegis.assistant.repository.AssistantMessageRepository;
import com.aegis.assistant.repository.AssistantSessionRepository;
import com.fasterxml.jackson.databind.ObjectMapper;

import cn.dev33.satoken.stp.StpUtil;

@Service
public class ChatService {

    private static final Logger log = LoggerFactory.getLogger(ChatService.class);

    private final RestTemplate restTemplate;
    private final AssistantSessionRepository sessionRepository;
    private final AssistantMessageRepository messageRepository;
    private final AssistantAuditLogRepository auditLogRepository;
    private final ThreadPoolTaskExecutor streamExecutor;

    @Autowired
    public ChatService(AssistantMessageRepository messageRepository, AssistantSessionRepository sessionRepository,
                       AssistantAuditLogRepository auditLogRepository, ThreadPoolTaskExecutor streamTaskExecutor) {
        this.messageRepository = messageRepository;
        this.sessionRepository = sessionRepository;
        this.auditLogRepository = auditLogRepository;
        this.streamExecutor = streamTaskExecutor;
        
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
        
        request.setTenantId(String.valueOf(userId));

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
            saveLog(userId, "MODEL_CALL", "Requested model qwen3:0.6b", e.getMessage(), "FAILED");
            AssistantMessage errorMsg = new AssistantMessage();
            errorMsg.setSessionId(sessionId);
            errorMsg.setRole("ai");
            errorMsg.setContent("无法连接 AI 服务，请确认 FastAPI 与 Ollama 已启动: " + e.getMessage());
            errorMsg.setMessageTime(new Date());
            messageRepository.save(errorMsg);

            throw new IllegalStateException("无法连接 AI 服务，请确认 FastAPI 与 Ollama 已启动: " + e.getMessage(), e);
        }
    }

    public SseEmitter chatStream(ChatRequest request) {
        long userId = StpUtil.getLoginIdAsLong();
        Long sessionId = request.getSessionId();
        
        request.setTenantId(String.valueOf(userId));

        if (sessionId == null) {
            AssistantSession session = createSession(userId, "新对话");
            sessionId = session.getId();
        }
        final Long finalSessionId = sessionId;

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
        userMsg.setSessionId(finalSessionId);
        userMsg.setRole("user");
        userMsg.setContent(request.getQuestion());
        userMsg.setMessageTime(new Date());
        messageRepository.save(userMsg);
        
        saveLog(userId, "CHAT_CALL_STREAM", request.getQuestion(), null, "PENDING");

        SseEmitter emitter = new SseEmitter(300000L); // 5 minutes timeout

        // 使用有界线程池执行异步推流，避免每次请求 new Thread() 导致线程无界增长、长期运行后资源耗尽
        streamExecutor.execute(() -> {
            long startTime = System.currentTimeMillis();
            try {
                StringBuilder fullAnswer = new StringBuilder();
                restTemplate.execute(
                    "http://127.0.0.1:8000/internal/rag/query",
                    HttpMethod.POST,
                    clientReq -> {
                        clientReq.getHeaders().setContentType(MediaType.APPLICATION_JSON);
                        new ObjectMapper().writeValue(clientReq.getBody(), request);
                    },
                    clientResp -> {
                        InputStream is = clientResp.getBody();
                        java.io.Reader reader = new java.io.InputStreamReader(is, java.nio.charset.StandardCharsets.UTF_8);
                        char[] buffer = new char[256];
                        int len;
                        ObjectMapper mapper = new ObjectMapper();
                        while ((len = reader.read(buffer)) != -1) {
                            String chunk = new String(buffer, 0, len);
                            fullAnswer.append(chunk);
                            String jsonStr = mapper.writeValueAsString(Collections.singletonMap("content", chunk));
                            try {
                                emitter.send(SseEmitter.event().data(jsonStr));
                            } catch (Exception e) {
                                // 客户端可能已断开，忽略发送异常，避免打断流的读取
                            }
                        }
                        return null;
                    }
                );
                
                long costMs = System.currentTimeMillis() - startTime;
                
                // 将完整的 AI 回复保存到数据库（保存失败不应影响流式回复本身）
                try {
                    AssistantMessage aiMsg = new AssistantMessage();
                    aiMsg.setSessionId(finalSessionId);
                    aiMsg.setRole("ai");
                    aiMsg.setContent(fullAnswer.toString());
                    aiMsg.setMessageTime(new Date());
                    aiMsg.setCostMs((int) costMs);
                    messageRepository.save(aiMsg);
                } catch (Exception dbEx) {
                    log.warn("保存 AI 流式回复失败: {}", dbEx.getMessage());
                }
                
                saveLog(userId, "MODEL_CALL_STREAM", "Requested model stream", "Model replied in " + costMs + "ms", "SUCCESS");

                try {
                    emitter.complete();
                } catch (Exception ignored) {
                    // 连接已断开或流已结束，忽略
                }
            } catch (Exception e) {
                log.error("SSE 推流异常: {}", e.getMessage(), e);
                saveLog(userId, "MODEL_CALL_STREAM", "Requested model stream", e.getMessage(), "FAILED");
                try {
                    String errorJson = new ObjectMapper().writeValueAsString(Collections.singletonMap("content", "\n[Error: 服务异常或超时]"));
                    emitter.send(SseEmitter.event().data(errorJson));
                } catch (Exception ex) {
                    // 客户端断开时忽略发送失败
                }
                try {
                    // 用 complete() 正常结束流，而不是 completeWithError()，
                    // 避免触发 DispatcherServlet 的 /error 错误页级联
                    emitter.complete();
                } catch (Exception ignored) {
                    // 流已结束或连接已断开，忽略
                }
            }
        });

        return emitter;
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

    @Transactional
    public void deleteSession(Long userId, Long sessionId) {
        AssistantSession session = sessionRepository.findById(sessionId).orElse(null);
        if (session != null && session.getUserId().equals(userId)) {
            // PostgreSQL 表结构中已配置 ON DELETE CASCADE，
            // 直接删除 session 即可级联删除关联的 message 及 message_reference
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
