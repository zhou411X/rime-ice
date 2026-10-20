Rime Ice / 雾凇输入法设置 0.2.0
=========================================

面向 Ubuntu 24.04 amd64 的本地设置中心，基于 Fcitx5、Rime 与公开雾凇拼音。
本项目是独立定制的设置中心，并非上述上游项目的官方发行版。

安装
----
联网安装应用包：sudo apt install ./rime-ice_0.2.0_all.deb
应用 deb 包含设置中心、公开雾凇拼音方案、词典和主题，不包含系统依赖。
APT 会从 Ubuntu 软件源安装缺少的 Fcitx5、Rime、GTK 和字体等依赖；需要联网。
若用 dpkg 安装后提示缺少依赖，可联网运行 sudo apt --fix-broken install，检查安装计划后确认。
从 0.1.0 升级建议同时下载过渡包，执行：
sudo apt install ./rime-ice_0.2.0_all.deb ./rime-ice-settings_0.2.0_all.deb
安装完成后输入、词典、主题和个人配置均可离线使用。
APT 会展示软件包变更。首次打开“雾凇拼音”，在“常用设置”选择启用，
按提示在 Fcitx5 配置工具中添加 Rime，然后注销并重新登录。

功能
----
11 种新配色各有浅色与夜色版，连同青玉、墨夜、Solarized，共 26 套主题。
系统明暗跟随、字体与字号、横向或纵向排列、3–9 个候选。
输入法切换快捷键、左 Shift 行为、中文与英文词库学习开关。
自定义短语增删改查、TXT 导入预览与去重、导出、固定第二候选。
配置自动备份、个人配置导出、恢复前再次备份，防止覆盖并发修改。

范围
----
设置页管理雾凇全拼。其他输入方案在 Fcitx5 配置工具 / Rime F4 选单中选择。
主题用于 Fcitx5 Classic UI；如果 GNOME/KDE 扩展接管候选框，外观可能由扩展决定。
部分应用及 Wayland 会话需要系统输入法环境配置；通过 im-config 引导而非强行改写。
学习数据库不直接编辑、复制或打包；需要迁移时先使用 Rime 菜单同步功能。
TXT 仅保存词条、编码、权重。固定第二位规则随个人配置 JSON 备份迁移。
更改 YAML 时保留未管理字段，但 YAML 注释格式可能重排；原文件留在自动备份中。
如果配置文件包含重复键或已有文件冲突，会停止而不是猜测后覆盖。
安装新版本不自动覆盖用户现有词典；已有词典升级需单独处理。

数据位置
--------
用户配置：$XDG_CONFIG_HOME/fcitx5（默认 ~/.config/fcitx5）
用户词库：$XDG_DATA_HOME/fcitx5/rime（默认 ~/.local/share/fcitx5/rime）
自动备份：$XDG_STATE_HOME/rime-ice/backups（默认 ~/.local/state/rime-ice/backups）
公共初始数据：/usr/share/rime-ice/rime
卸载 rime-ice 不自动删除用户配置和词库。

源码与验证
----------
设置中心：rime_ice/app.py；配置逻辑：rime_ice/model.py。
构建应用：./build_deb.sh；生成对应应用源码：./build_source.sh。
这两个命令不收集或打包 Ubuntu 依赖；可选离线工具仅供自行构建，不随本版发布。
配置测试：/usr/bin/python3 -m unittest discover -s tests -v
界面测试：PYTHONPATH=. GTK_A11Y=none ADW_DISABLE_PORTAL=1 GDK_BACKEND=x11 GSK_RENDERER=cairo xvfb-run -a dbus-run-session --config-file=tests/session.conf -- /usr/bin/python3 tests/check_gui.py
测试只使用临时用户目录；不会改写当前用户输入法配置。
构建使用已安装的 Python/GTK4，无需联网下载 Python 包或加载远程网页。

来源与许可
----------
设置中心、配置扩展和自制主题：GPL-3.0-only，见 LICENSE。
公开词典：iDvel/rime-ice，固定版本和下载校验见 UPSTREAM.json。
开发目录的 upstream/ 保存完整上游源码；分发源码包包含本发行所用的公开词典和 Lua 源码。
许可证和所选文件的原始版权声明均保留。
发行包不包含本机自定义短语、学习数据库、sync 目录或 installation.yaml。
Fcitx5/Rime/Ubuntu 依赖由系统软件源提供，保持各自许可，不包含在应用 deb 中。
分享本应用时请一并提供应用源码和上游版权说明。

0.2.0 更名说明：主包与启动命令为 rime-ice；旧命令仍兼容。发布页另外提供旧包的空过渡包。
新增主题参考 nevertoday/rime-color-scheme，固定版本见 THEME_UPSTREAM.json。
配色适配保留 MIT 许可，见 LICENSES/rime-color-scheme.txt；名称不表示品牌合作。
