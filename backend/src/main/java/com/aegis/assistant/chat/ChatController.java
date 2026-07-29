package com.aegis.assistant.chat;

import com.aegis.assistant.config.Result;
import com.aegis.assistant.entity.AssistantSession;
import com.aegis.assistant.entity.AssistantMessage;
import cn.dev33.satoken.stp.StpUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

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
