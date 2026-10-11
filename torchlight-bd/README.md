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
