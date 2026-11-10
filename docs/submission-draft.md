# AIMA Story Director — creator-program draft

Prepared 2026-11-06. A truthful application/pitch candidate; not a platform application or a robot performance record.

## 作品名称

机器人场景导演：先排练分支，再检查执行证据

## 创作说明

面向迎宾、展览导览与安全距离提醒三个日常场景，把台词、动作意图、等待和事件分支写成可校验的场景 JSON。模拟播放器导出逐时刻时间线、SVG 展示、执行清单和审计记录。分支排练会列出可达路径、未覆盖条件与不可行分支，避免把单次顺利演示当作所有情况都已验证。

动作参数与时序校验、库存式的场景状态和离线报告均可在普通电脑上复现。距离提醒只响应示例中的输入事件；它不是传感器测距、安全系统或碰撞防护。

## 可展示材料

- `examples/welcome.json`：迎宾与事件响应。
- `examples/exhibition.json`：展览导览。
- `examples/distance-reminder.json`：距离事件提醒。
- README 的模拟与分支排练命令所产生的时间线、覆盖报告和执行清单。

录屏须在画面与旁白中标注“离线模拟 / dry-run”。不使用其他机器人的表演画面冒充本项目实测。

## 平台与硬件边界

[AIMA 官方百大创作者计划](https://open.agibot.com/creator-plan)面向个人/团队、无粉丝门槛，是持续创作者扶持计划，并非仅凭 GitHub 作品即可参评的单次比赛。2026-11-06 官方页面显示：在灵心/灵创发布至少一件有效作品才满足入门作品门槛；申请新秀需至少十件有效作品、累计至少二十次有效使用。更高级别还涉及评审，入选不自动获得机器人。最终定义以[官方细则](https://open.agibot.com/files/creator-plan-rules.pdf)及账户页面为准。

本仓库提供独立场景编排工具。用户已确认创作者计划申请提交，尚未独立核验申请ID或审核结果，不重复申请；平台原生作品仍待核验。本工具未调用AIMA私有API、完成AimDK真机适配或控制真实机器人，硬件执行模式明确拒绝运行。

“报名加入”会进入智元统一登录页；可手机验证码/邮箱/账号密码，登录勾选项包括协议、隐私与本人满十八岁确认。11月10日查看creator-plan时普通及无痕浏览器均未登录；这次会话观察不推翻此前本人已交申请的记录。恢复会话后跟进既有申请、可接收作品形式与指定机型要求。若需要灵创动作/音频作品或真机演示，须实际完成相应创作和测试后再描述；通用 JSON 与 SVG 不能冒充平台原生作品。

Repository: https://github.com/misakamikotoghr-5205/aima-story-director

License: MIT. 使用 Codex 多智能体协作开发；未声称机器人平台或硬件实测。
