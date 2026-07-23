package com.aegis.assistant.chat;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

@Service
public class ChatService {

    @Autowired
    private RestTemplate restTemplate;

    public ChatResponse chat(ChatRequest request) {
        String url = "http://localhost:8000/internal/rag/query";
        return restTemplate.postForObject(url, request, ChatResponse.class);
    }
}
