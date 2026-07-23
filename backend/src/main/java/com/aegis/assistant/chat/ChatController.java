package com.aegis.assistant.chat;

import com.aegis.assistant.config.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/assistant")
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
}
