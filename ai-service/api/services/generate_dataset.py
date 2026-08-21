import json
import os
import random
from openai import OpenAI

# 1. 初始化客户端（兼容阿里云通义千问、DeepSeek、智谱等所有标准OpenAI格式的接口）
client = OpenAI(
    api_key="您的_API_KEY", 
    base_url="https://api.deepseek.com/v1" # 根据实际使用的API进行更换
)

# 2. 精心提炼的“网站群系统”特有故障和技术痛点种子
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

def generate_one_sample(issue, emotion):
    system_prompt = "你是一个数据集生成专家。你的唯一任务是批量生产高质量的‘站群系统高级架构师+金牌售后客服’大模型微调数据。"
    
    user_prompt = f"""
    请根据以下设定，生成一组【ChatML】格式的高质量客服对话数据集样本（包含system, user, assistant的多轮对话，至少2个来回）。
    
    【核心设定】
    1. 站群故障主题：{issue}
    2. 来访客户状态：{emotion}
    
    【生成极其严格的质量要求】
    1. 语气底色：Assistant必须体现出“顶尖程序员（懂底层原理、能给严谨的1.2.3.排查步骤、不瞎编）”与“顶尖售后客服（极其温柔、会安抚、懂转译黑话）”的完美结合。
    2. 结构固定：Assistant的第一轮回答必须包含【技术术语大白话】（把复杂的代码和底层原理转译成小白听得懂的温柔解释）和【核心排查与解决步骤】（硬核、逻辑严密、包含真实的命令或配置行）。
    3. 拒绝模板化：不要总用一模一样的开场白。根据客户的愤怒或焦虑状态，给出个性化的、有同理心的安抚话术。
    
    【输出格式约束】
    只输出合法的、可直接被 json.loads() 解析的单个 JSON 字典（不要包裹在 ```json 这样的Markdown标记中！），格式如下：
    {{"messages": [{{"role": "system", "content": "您好！我是您的智能助手，有什么可以帮助您？"}}, {{"role": "user", "content": "..."}}, {{"role": "assistant", "content": "您好！我是您的智能助手，有什么可以帮助您？\\n\\n[后面紧跟高质量硬核专业解答]..."}}]}}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # 或 qwen-max
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            stream=False
        )
        res_text = response.choices[0].message.content.strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"单条数据生成失败: {e}")
        return None

# 3. 循环批量生产并追加写入本地文件
output_file = "qwen_customer_service_dataset.json"
all_samples = []

if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        try: all_samples = json.load(f)
        except: all_samples = []

target_count = 1000
print(f"客户专属数据集开始生产！当前进度：{len(all_samples)}/{target_count}...")

while len(all_samples) < target_count:
    # 随机组合站群故障与情绪种子
    current_issue = random.choice(site_group_issues) + f" (变体编号_{random.randint(1, 20000)})"
    current_emotion = random.choice(customer_emotions)
    
    sample = generate_one_sample(current_issue, current_emotion)
    if sample:
        all_samples.append(sample)
        print(f"成功生成第 {len(all_samples)} 条。")
        
        # 每 10 条进行一次本地写入，防止中途意外断网丢失进度
        if len(all_samples) % 10 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_samples, f, ensure_ascii=False, indent=2)

print(f"大功告成！1000条高质量网站群系统微调数据集已成功写入到 {output_file}！")