Rime Ice Settings / 雾凇输入法设置 0.1.0
=========================================

面向 Ubuntu 24.04 amd64 的本地设置中心，基于 Fcitx5、Rime 与公开雾凇拼音。
本项目是独立定制的设置中心，并非上述上游项目的官方发行版。

安装
----
联网安装应用包：sudo apt install ./rime-ice-settings_0.1.0_all.deb
完全离线安装：解压完整 offline.tar.gz，进入 bundle，执行 sudo ./install-offline.sh。
单独的应用 deb 不包含 Ubuntu 系统依赖；无网电脑必须使用完整离线包。
安装器先展示软件包变更。首次打开“雾凇输入法设置”，在“常用设置”选择启用，
按提示在 Fcitx5 配置工具中添加 Rime，然后注销并重新登录。

功能
----
四种候选框主题：青玉、墨夜、Solarized Light、Solarized Dark。
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
卸载 rime-ice-settings 不自动删除用户配置和词库。

源码与验证
----------
设置中心：rime_ice/app.py；配置逻辑：rime_ice/model.py。
构建：./build_deb.sh；离线依赖收集：./build_offline.sh。
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
Fcitx5/Rime/Ubuntu 依赖保持各自许可；随包 deb 保留 /usr/share/doc 下版权说明。
向他人分发完整离线包时，请同时提供对应源码及上游版权说明。
