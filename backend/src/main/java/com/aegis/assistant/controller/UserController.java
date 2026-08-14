package com.aegis.assistant.controller;

import java.util.Date;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.aegis.assistant.config.Result;
import com.aegis.assistant.dto.LoginRequest;
import com.aegis.assistant.entity.User;
import com.aegis.assistant.repository.UserRepository;

import cn.dev33.satoken.stp.StpUtil;

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

    @PostMapping("doRegister")
    public Result<String> doRegister(@RequestBody LoginRequest registerRequest) {
        String username = registerRequest.getUsername();
        String useraccount = registerRequest.getUseraccount();
        String password = registerRequest.getPassword();
        
        if (username == null || username.trim().isEmpty() || 
            useraccount == null || useraccount.trim().isEmpty() || 
            password == null || password.trim().isEmpty()) {
            return Result.error(400, "用户名、账号或密码不能为空");
        }
        
        User existingUseraccount = userRepository.findByUseraccount(useraccount);
        if (existingUseraccount != null) {
            return Result.error(400, "账号已存在");
        }
        
        User newUser = new User();
        newUser.setUsername(username);
        newUser.setUseraccount(useraccount);
        newUser.setPassword(password);
        newUser.setRole("USER");
        Date now = new Date();
        newUser.setCreated_at(now);
        newUser.setUpdated_at(now);
        
        userRepository.save(newUser);
        
        return Result.success("注册成功，请登录");
    }

    // 测试登录，浏览器访问： http://localhost:8082/user/doLogin?useraccount=zhang&password=123456
    @PostMapping("doLogin")
    public Result<Object> doLogin(@RequestBody LoginRequest loginRequest) {
        // 从数据库中查询用户进行比对
        String useraccount = loginRequest.getUseraccount();
        String password = loginRequest.getPassword();
        System.out.println("useraccount = " + useraccount + ", password = " + password);
        User user = userRepository.findByUseraccount(useraccount);
        if (user != null && user.getPassword().equals(password)) {
            StpUtil.login(user.getId());
            return Result.success(StpUtil.getTokenInfo());
        }
        return Result.error(401, "登录失败，账号或密码错误");
    }

    @PostMapping("resetPassword")
    public Result<String> resetPassword(@RequestBody LoginRequest resetRequest) {
        String useraccount = resetRequest.getUseraccount();
        String newPassword = resetRequest.getPassword();

        if (useraccount == null || useraccount.trim().isEmpty() || newPassword == null || newPassword.trim().isEmpty()) {
            return Result.error(400, "账号或新密码不能为空");
        }

        User user = userRepository.findByUseraccount(useraccount);
        if (user == null) {
            return Result.error(404, "账号不存在");
        }

        user.setPassword(newPassword);
        user.setUpdated_at(new Date());
        userRepository.save(user);

        return Result.success("密码修改成功，请重新登录");
    }

    // 查询登录状态，浏览器访问： http://localhost:8082/user/isLogin
    @RequestMapping("isLogin")
    public Result<String> isLogin() {
        return Result.success("当前会话是否登录：" + StpUtil.isLogin());
    }

    @RequestMapping("me")
    public Result<User> me() {
        if (!StpUtil.isLogin()) {
            return Result.error(401, "未登录");
        }
        long userId = StpUtil.getLoginIdAsLong();
        User user = userRepository.findById(userId).orElse(null);
        if (user != null) {
            // 不要返回密码
            user.setPassword(null);
            return Result.success(user);
        }
        return Result.error(404, "用户不存在");
    }

}

