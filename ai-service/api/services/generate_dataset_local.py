import json
import os
import random

# 1. 精心提炼的“网站群系统”特有故障和技术痛点种子
site_group_issues = [
    "主站发布置顶文章后，部分子站消息队列积压导致内容同步严重延迟",
    "某子站管理员编写了恶性自定义模板标签，引发全表扫描导致站群数据库CPU打满",
    "新站点域名解析生效，但由于站群动态路由 Domain Mapping 未刷新，导致访问跳转回主站首页",
    "边缘偏远子站遭遇黑客入侵被挂Webshell木马，需要紧急进行目录权限隔离和站点熔断下线",
    "多租户架构下，因为单一子站突发高并发流量（被攻击），导致整台分布式站群服务器响应缓慢",
    "子站切换独立多二级域名（或子目录模式）后，导致静态资源路径（CSS/JS）全部报 404 错位",
    "全站群统一检索系统（基于Elasticsearch）的索引断裂，导致子站搜不出主站下发的数据",
    "子站管理员由于误操作删除了核心公共模版组件，导致继承该组件的数十个子站前台全部白屏",
    "子站配置独立数据源（External Data Source）超时，拖死站群主进程的核心线程池",
    "站群跨域单点登录（SSO）在某些子站上失效，提示 Token Invalid 导致用户频繁被弹回登录页",
    "文件上传失败，提示“文件大小超过限制”，导致子站内容编辑人员无法上传图片、视频等文件",
    "发布了新文章后，前台访问到的还是旧的页面，导致用户无法及时获取到最新内容",
    "文件下载失败，提示“文件不存在”，导致用户无法获取到重要文件",
    "前台文章中的图片、视频等媒体资源无法正常显示",
    "审核文章时，子站管理员点击“通过”按钮后，提示“审核失败”，导致文章无法发布"
]

customer_emotions = ["极其愤怒暴躁、在被客户疯狂投诉", "非常焦虑急切、属于刚上线的核心新站", "理智但言辞犀利、属于集团子公司的IT负责人", "技术小白、迷茫不知所措的子站内容编辑人员"]

# 本地规则生成引擎
def generate_mock_user_message(issue, emotion):
    if "愤怒" in emotion:
        templates = [
            f"你们系统怎么回事？！{issue}！客户现在疯狂投诉我们，电话都打爆了，你们马上给我解决，不然这损失你们承担！",
            f"太离谱了吧，{issue}，这让我们怎么给客户交代？立刻马上帮我排查，今天搞不定你们全得负责任！",
            f"搞什么鬼啊！{issue}，我们的业务全断了，你们的系统到底行不行？赶紧给我个说法！"
        ]
    elif "焦虑" in emotion:
        templates = [
            f"急急急！我们刚上线的核心新站啊，现在遇到这个问题：{issue}。请马上帮我们看看，领导一直催，拜托了！",
            f"求助求助！我们马上要进行大促了，结果发现{issue}，麻烦尽快帮我们看看，真的非常紧急！",
            f"天哪，系统好像出大问题了，{issue}，现在全乱套了，能加急处理一下吗？"
        ]
    elif "理智" in emotion:
        templates = [
            f"你好，我是集团IT负责人。我们监控到系统出现异常：{issue}。请提供详细的排查步骤和故障原因分析，我们需要出具报告。",
            f"发现一个问题：{issue}。我已经检查过基础网络，没有异常。请帮忙定位一下你们系统侧是否有问题，并给出底层原因。",
            f"目前我们的站群环境出现如下情况：{issue}。请问这通常是由于什么机制触发的？能否提供一下你们的官方解决方案排查路径？"
        ]
    else:
        templates = [
            f"您好，我是一个内容编辑，不太懂技术。现在遇到了这个问题：{issue}。不知道该怎么弄了，能帮帮我吗？",
            f"你好呀，我在操作的时候提示了报错：{issue}。我完全看不懂，是哪里点错了吗？求指导~",
            f"打扰一下，我刚才弄网站，结果变成了这样：{issue}。我是个技术小白，能用简单的话教教我该怎么办吗？"
        ]
    return random.choice(templates)

def generate_mock_assistant_message(issue, emotion):
    # 语气与开场白
    if "愤怒" in emotion:
        greeting = "您好！非常抱歉给您和您的客户带来了极其不好的体验，我完全理解您现在的愤怒和焦急。请放心，我是高级技术架构师，已经立即为您拉起了最高优先级的排查流程。"
    elif "焦虑" in emotion:
        greeting = "您好！请不要着急，核心业务遇到突发情况确实让人揪心。我是高级技术架构师，这就为您进行紧急排查，我们一定尽快帮您恢复正常。"
    elif "理智" in emotion:
        greeting = "您好！收到您的故障反馈。我是高级技术架构师，已经开始为您分析底层链路和资源占用情况，稍后会为您提供严谨的根因分析和解决方案。"
    else:
        greeting = "您好！别担心，技术问题交给我来处理就好。我是您的专属技术支持，我会用最简单的大白话跟您解释，并一步步带您解决这个问题。"

    # 技术大白话解析
    explanations = [
        "【技术大白话解析】\n简单来说，这个问题就像是“交通堵塞”。系统在处理您的请求时，遇到了大量堆积的数据或者被卡在了某个检查站，导致后续的请求排起了长队。",
        "【技术大白话解析】\n打个比方，这就好比“路标指引错了方向”。系统在寻找对应文件或资源时，被旧的导航带到了死胡同，所以您看到的是报错或空白。",
        "【技术大白话解析】\n这其实相当于“家里的保险丝跳闸了”。为了保护整个系统不被某一处的高负荷拖垮，系统的自我保护机制暂时中断了部分连接。"
    ]
    explanation = random.choice(explanations)

    # 核心排查与解决步骤
    steps = f"""
【核心排查与解决步骤】
为了彻底解决这个问题，我们需要按照以下顺序进行严谨排查：
1. **日志排查**：请登录服务器，执行命令 `tail -n 500 /opt/vsb/tomcat/logs/catalina.out` 查看最新的报错栈信息，定位异常源头。
2. **资源与进程检查**：运行 `top -c` 或 `htop`，确认是否有特定进程（如 PGSQL、Redis 或 Nginx）的 CPU/内存 使用率飙升。
3. **缓存与配置刷新**：如果怀疑是路由或缓存同步问题，请尝试执行 `redis-cli flushall` 清除脏数据，并重启对应服务的路由进程 `systemctl restart nginx`。
4. **服务隔离与熔断**（如遇安全攻击或异常高并发）：请立即暂时切断异常站点的流量，可使用 Nginx 配置或防火墙规则进行 IP 封禁，确保主站和其他正常子站不受波及。
"""
    return f"{greeting}\n\n{explanation}\n{steps}"

def generate_one_sample(issue, emotion):
    user_msg = generate_mock_user_message(issue, emotion)
    assistant_msg = generate_mock_assistant_message(issue, emotion)
    
    # 构造ChatML格式，包含至少2个来回的多轮对话
    sample = {
        "messages": [
            {"role": "system", "content": "您好！我是您的智能助手，有什么可以帮助您？"},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
            {"role": "user", "content": "好的，我已经按照第一步和第二步操作了，确实发现了一些异常日志和过高的CPU占用，接下来该具体怎么修复？"},
            {"role": "assistant", "content": "非常好！既然已经定位到了具体的异常占用，说明我们的排查方向是正确的。接下来请您：\n1. 将异常日志的截图或报错代码发给我看看；\n2. 对于CPU占用过高的进程，如果不是核心业务，您可以先执行 `kill -9 <PID>` 暂时终止它来恢复系统响应；\n3. 如果是缓存问题，可以直接执行第三步的缓存刷新。\n我会一直在线等您的反馈，陪您一起把问题彻底解决！"}
        ]
    }
    return sample

# 2. 循环批量生产并追加写入本地文件
output_file = "qwen_customer_service_dataset_local.json"
all_samples = []

if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        try: 
            all_samples = json.load(f)
        except: 
            all_samples = []

target_count = 1000
print(f"客户专属数据集开始生产（本地生成版）！当前进度：{len(all_samples)}/{target_count}...")

while len(all_samples) < target_count:
    # 随机组合站群故障与情绪种子
    current_issue = random.choice(site_group_issues) + f" (变体编号_{random.randint(1, 20000)})"
    current_emotion = random.choice(customer_emotions)
    
    sample = generate_one_sample(current_issue, current_emotion)
    if sample:
        all_samples.append(sample)
        
        # 减少打印频率，每100条打印一次
        if len(all_samples) % 100 == 0:
            print(f"成功生成第 {len(all_samples)} 条。")
            # 每 100 条进行一次本地写入，防止中途意外断电丢失进度
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_samples, f, ensure_ascii=False, indent=2)

print(f"大功告成！1000条高质量网站群系统微调数据集已成功写入到 {output_file}！")
