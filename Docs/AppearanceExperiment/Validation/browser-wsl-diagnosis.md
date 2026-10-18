# 原生浏览器与WSL迁移排查

检查日期：2026-10-18。仅记录运行环境和软件配置，没有读取或复制浏览器Cookie、密码、网站存储或参与者回答。

## 已确认

| 项目 | 本机Windows／WSL | Ubuntu台式机 |
|---|---|---|
| 应用版本 | Windows包26.1013.4894.0；插件版本26.1013.40934 | 插件及应用报告26.1007.21434 |
| 内置Browser源文件 | Windows安装包中存在，含完整SKILL.md、browser-client.mjs及插件清单 | `/usr/lib/chatgpt/resources/plugins/openai-bundled/plugins/browser`中存在 |
| 当前插件注册 | WSL配置与缓存没有Browser条目；普通市场列表不含内置来源 | `browser@openai-bundled`已启用 |
| 浏览器后端 | WSL配置中`BROWSER_USE_AVAILABLE_BACKENDS`为空 | `chrome,iab,mcpapps` |
| JS执行程序 | WSL配置指向Windows版`node_repl.exe` | 本机Linux版`node_repl` |
| 最小连接检查 | 在执行只读JS前返回`-32602`，提示`sandboxCwd is not a local file URI`，报错路径为`file:///mnt/d/...` | 本轮未通过该聊天实际操作台式机浏览器 |

Windows旧配置仍留在退休目录；其中有旧版Chrome等内置插件注册和Windows路径。现用WSL配置已经由当前版本写入新的Windows运行程序路径。此轮只读检查旧目录，没有向旧目录写入会话或输出。

用户随后提供的两张设置截图已通过`/mnt/c/Users/熊熊/AppData/Local/Temp/`对应路径读取。浏览器页显示“应用内浏览器插件不可用”；电脑操控页的Chrome和Edge显示“已被你的组织停用，或在你所在地区不可用”。截图不能区分具体是组织限制、地区可用性，还是状态判断异常；也没有证明台式机在当前时刻仍可操作浏览器。

## 原因与边界

本机安装包完整，不能把故障归因于缺少一份SKILL.md。当前至少有两个独立问题：应用没有给这个WSL聊天启用浏览器后端；已有的Windows执行程序不接受工具传入的WSL项目URI。

检查当前应用的配置代码可见，Browser插件可用性取决于应用提供的浏览器功能状态；新版统一交互通道还包含`!shouldUseWslPaths`条件。这能说明直接拷贝文件不会自动获得连接，但不能据此断言所有版本、所有浏览器通道都不支持WSL。用户截图补充确认了应用层的不可用提示，因此没有把空后端列表直接当作缺失配置并强行改为启用。

本轮使用官方CLI尝试添加Windows安装包中的内置插件来源，命令返回：`marketplace openai-bundled is reserved and cannot be added from this source`。这是应用保留来源的限制，不是权限审批拒绝。没有改名伪装来源、改写应用程序或手动覆盖功能状态。

## 变更与后续

修改前已在现用WSL配置目录保存私有备份：`/home/enjixiong/.codex/backups/browser-wsl-20261018T130656Z/config.toml`。备份不进入项目版本库。注册命令失败，未安装插件或更改MCP配置；没有把台式机旧版Linux运行程序覆盖到Windows应用连接上。

后续先通过工作区管理员或OpenAI支持确认界面提示对应的功能可用性；WSL项目URI被Windows执行程序拒绝的问题可附此记录一并排查。应用正常提供浏览器能力后，再复测最小工具调用与Browser选择。当前尚未恢复网页控制，三份问卷星草稿也未保存本次Q2修订。

三份待修改草稿：开始前389439995、每轮389455149、结束389455386。继续保持未发布，不提交答卷，不修改旧问卷384478976。

官方说明确认内置浏览器随桌面应用提供；功能可用性还受应用与工作区设置影响：[Using the built-in browser in the ChatGPT desktop app](https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app)。该说明没有提供本次URI报错的修复步骤。
