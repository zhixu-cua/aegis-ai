package com.aegis.assistant.chat;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.aegis.assistant.config.Result;
import com.aegis.assistant.entity.AssistantMessage;
import com.aegis.assistant.entity.AssistantSession;

import cn.dev33.satoken.stp.StpUtil;

@RestController
@RequestMapping("/assistant")
public class ChatController {

    @Autowired
    private ChatService chatService;

    @PostMapping("/chat")
    public Result<ChatResponse> chat(@RequestBody ChatRequest request) {
        try {
            ChatResponse response = chatService.chat(request);
            return Result.success(response);
        } catch (Exception e) {
            return Result.error(500, "问答请求失败: " + e.getMessage());
        }
    }

    @PostMapping(value = "/chat/stream", produces = org.springframework.http.MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(@RequestBody ChatRequest request) {
        return chatService.chatStream(request);
    }

    @GetMapping("/sessions")
    public Result<List<AssistantSession>> getSessions() {
        long userId = StpUtil.getLoginIdAsLong();
        return Result.success(chatService.getSessions(userId));
    }

    @PostMapping("/sessions")
    public Result<AssistantSession> createSession(@RequestBody AssistantSession session) {
        long userId = StpUtil.getLoginIdAsLong();
        return Result.success(chatService.createSession(userId, session.getSessionTitle()));
    }

    @DeleteMapping("/sessions/{id}")
    public Result<String> deleteSession(@PathVariable Long id) {
        long userId = StpUtil.getLoginIdAsLong();
        chatService.deleteSession(userId, id);
        return Result.success("删除成功");
    }

    @GetMapping("/sessions/{id}/messages")
    public Result<List<AssistantMessage>> getMessages(@PathVariable Long id) {
        long userId = StpUtil.getLoginIdAsLong();
        return Result.success(chatService.getMessages(userId, id));
    }
}
