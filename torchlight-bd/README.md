# 火炬之光：无限 BD 收藏库

## 公共数据如何工作

- 网站地址：`https://chaossure.github.io/Cowbi/torchlight-bd/`
- 前端由 GitHub Pages 托管。
- 所有访客读取同一个公共数据文件：`torchlight-bd/data/builds.json`，不再依赖各自浏览器的 localStorage。
- 玩家通过网站的“投稿 BD”按钮提交 GitHub Issue 表单。
- 投稿 Issue 不会自动出现在网站上。管理员审核内容后，将通过的档案加入 `builds.json`，推送到 `main` 分支；GitHub Actions 会自动重新部署，所有访客刷新后看到相同更新。

## 管理员审核与发布

1. 打开仓库的 Issues，筛选标签 `bd-submission`。
2. 检查流派资料、赛季版本、链接来源及截图是否可公开访问。
3. 通过后编辑 `torchlight-bd/data/builds.json`，在 `builds` 数组中加入档案。
4. 每条档案建议使用字段：`id`, `name`, `season`, `hero`, `skill`, `budget`, `tier`, `status`, `favorite`, `mechanics`, `gear`, `skills`, `content`, `notes`, `link`, `image`, `created`, `updated`。
5. 将对应 Issue 标记为已审核 / 已收录并关闭。

图片建议使用可公开访问的 HTTPS 图片链接；不要将大型图片直接塞进 JSON。

## 重要说明

当前方案使用 GitHub 仓库作为持久化数据源、GitHub Issues 作为投稿收件箱、管理员审核后合并为公开数据。它不需要单独购买数据库，也不会把 GitHub 写入令牌放在浏览器中。只有仓库管理员能直接发布公共档案。GitHub 账户通常需要登录后才能创建 Issue 投稿。


## 配装模拟器

- 页面：`https://chaossure.github.io/Cowbi/torchlight-bd/simulator.html`
- 支持 10 个装备槽位、装备名称/底材/稀有度、自定义词缀、英雄与技能信息、天赋树/追忆、契灵、神格/祝福备注。
- 支持属性词缀汇总、基础命中伤害与 DPS 近似估算、本地方案保存、JSON 导入/导出、通过 URL hash 分享当前方案。
- 装备词缀中的“伤害提高”和“额外伤害”会参与当前估算；其他特殊机制暂时只记录，不会假装已经纳入公式。
- 本地保存只存在于当前浏览器；分享链接会把方案数据放进链接中，避免上传到服务器。不要把包含私人信息的方案链接公开发布。

### SS13 数据状态

- 初始索引文件：`data/s13-catalog.json`
- 当前只包含少量已核对的 SS13 传奇装备模板，**不是完整的赛季装备、技能、底材和词缀数据库**。
- 模板的随机数值默认为 0，并把范围写在备注中；载入后需要按实际装备面板填写，不能把范围中值当作真实装备属性。
- 数据参考火炬编年史（TLIDB）赛季与装备页面。后续补全应保留来源 URL、赛季版本、词缀范围和校验状态，避免跨赛季数据混用。
- 当前 DPS 只是可解释的通用近似模型，不是游戏内完整模拟。转伤、穿透、技能倍率、触发频率、持续伤害、异常、召唤物、祝福/神格及英雄特性等机制，需要逐项录入并用游戏内实测验证后再加入计算。

### 公共收藏库与本地模拟方案的区别

公共 BD 收藏仍采用 GitHub Issue 投稿、管理员审核、更新 `data/builds.json` 后公开发布的流程。模拟器保存的个人方案不会自动公开，也不会写入公共档案。
