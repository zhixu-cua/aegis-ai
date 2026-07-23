package com.aegis.assistant;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.RestController;

import cn.dev33.satoken.SaManager;


@SpringBootApplication
@RestController
public class BackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(BackendApplication.class, args);
         System.out.println("启动成功，Sa-Token 配置如下：" + SaManager.getConfig());
    }
}
