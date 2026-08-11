package com.aegis.assistant.websocket;

import com.alibaba.fastjson.JSON;
import com.aegis.assistant.dto.ProgressDTO;
import com.aegis.assistant.config.Result;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.annotation.*;

import jakarta.websocket.*;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;

@Component
@ServerEndpoint("/ws/knowledge/{userId}")
public class KnowledgeWebSocket {
    
    private static final Logger log = LoggerFactory.getLogger(KnowledgeWebSocket.class);
    private static final ConcurrentHashMap<Long, Session> SESSIONS = new ConcurrentHashMap<>();
    
    @OnOpen
    public void onOpen(Session session, @PathParam("userId") Long userId) {
        SESSIONS.put(userId, session);
        log.info("WebSocket 连接建立: userId={}", userId);
    }
    
    @OnClose
    public void onClose(@PathParam("userId") Long userId) {
        SESSIONS.remove(userId);
        log.info("WebSocket 连接关闭: userId={}", userId);
    }
    
    @OnError
    public void onError(Session session, Throwable error) {
        log.error("WebSocket 错误: {}", error.getMessage());
    }
    
    /**
     * 推送进度更新到指定用户
     */
    public static void pushProgress(Long userId, ProgressDTO progress) {
        Session session = SESSIONS.get(userId);
        if (session != null && session.isOpen()) {
            try {
                session.getBasicRemote().sendText(JSON.toJSONString(progress));
            } catch (IOException e) {
                log.error("推送失败: {}", e.getMessage());
                SESSIONS.remove(userId);
            }
        }
    }
    
    /**
     * 内部接口：接收 AI 服务的状态回调
     */
    @RestController
    @RequestMapping("/api/internal/ws")
    public static class InternalWebSocketController {
        
        @PostMapping("/progress")
        public Result<Void> receiveProgress(@RequestBody ProgressDTO progress) {
            // TODO: 根据 datasource_id 查询 tenant_id，获取 userId
            Long userId = getUserIdByDatasource(progress.getDatasourceId());
            if (userId != null) {
                KnowledgeWebSocket.pushProgress(userId, progress);
            }
            return Result.success();
        }
        
        private Long getUserIdByDatasource(Long datasourceId) {
            // 实现：从数据库查询该数据源所属的用户/租户
            // 简化实现，实际需注入 Service
            return null;
        }
    }
}