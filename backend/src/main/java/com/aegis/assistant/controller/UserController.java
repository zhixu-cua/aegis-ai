package com.aegis.assistant.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.aegis.assistant.config.Result;
import com.aegis.assistant.dto.LoginRequest;
import com.aegis.assistant.entity.User;
import com.aegis.assistant.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * @author Administrator
 * @date 2026/7/23 13:57
 * @description TODO
 */
@RestController
@RequestMapping("/user/")
public class UserController {

    @Autowired
    private UserRepository userRepository;

    // 测试登录，浏览器访问： http://localhost:8082/user/doLogin?username=zhang&password=123456
    @PostMapping("doLogin")
    public Result<String> doLogin(@RequestBody LoginRequest loginRequest) {
        // 从数据库中查询用户进行比对
        String username = loginRequest.getUsername();
        String password = loginRequest.getPassword();
        System.out.println("username = " + username + ", password = " + password);
        User user = userRepository.findByUsername(username);
        if (user != null && user.getPassword().equals(password)) {
            StpUtil.login(user.getId());
            return Result.success("登录成功");
        }
        return Result.error(401, "登录失败，用户名或密码错误");
    }

    // 查询登录状态，浏览器访问： http://localhost:8082/user/isLogin
    @RequestMapping("isLogin")
    public Result<String> isLogin() {
        return Result.success("当前会话是否登录：" + StpUtil.isLogin());
    }

}

