package com.aegis.assistant.chat;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

@Service
public class ChatService {

    @Autowired
    private RestTemplate restTemplate;

    public ChatResponse chat(ChatRequest request) {
        String url = "http://127.0.0.1:8000/internal/rag/query";
        try {
            ChatResponse response = restTemplate.postForObject(url, request, ChatResponse.class);
            if (response == null || response.getAnswer() == null || response.getAnswer().isBlank()) {
                throw new IllegalStateException("AI 服务返回空结果");
            }
            return response;
        } catch (RestClientException e) {
            throw new IllegalStateException("无法连接 AI 服务，请确认 FastAPI 与 Ollama 已启动: " + e.getMessage(), e);
        }
    }
}
