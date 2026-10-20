# Rime Ice Settings · 雾凇输入法设置

面向 **Ubuntu 24.04 amd64** 的原生输入法设置中心，基于 Fcitx5、Rime 和公开雾凇拼音，提供完全离线安装包。

这是独立开发的设置工具，并非 Fcitx5、Rime 或雾凇拼音的官方发行版。当前版本为 **0.1.0 预览版**。

![原生 GTK 设置界面](docs/settings-preview.png)

## 功能

- 原生 GTK4 / libadwaita 设置界面，支持窗口明暗切换。
- 青玉、墨夜、Solarized Light、Solarized Dark 四套候选框主题。
- 字体、字号、横纵向排列、每页 3–9 个候选，以及跟随系统明暗。
- 输入法切换快捷键预设、左 Shift 行为、中文与英文词库学习开关。
- 个人短语增删改查、TXT 导入预览与去重、导出、固定第二候选。
- 保存前自动备份、个人配置导出与恢复、并发修改检测。

## 安装

前往 [Releases](https://github.com/zhou411X/rime-ice-settings/releases) 下载发行文件。

### 完全离线安装

将 `rime-ice-settings_0.1.0_ubuntu24.04_amd64_offline.tar.gz` 复制到目标电脑：

```bash
tar -xzf rime-ice-settings_0.1.0_ubuntu24.04_amd64_offline.tar.gz
cd bundle
sudo ./install-offline.sh
```

安装器先校验文件并展示软件包变更，确认后仅使用包内本地 APT 仓库安装，不需要网络。完整离线包包含应用、公开词典、主题、字体和系统依赖；单独的 `.deb` 不包含全部依赖。

### 联网安装单独应用包

```bash
sudo apt install ./rime-ice-settings_0.1.0_all.deb
```

安装后从应用菜单打开“雾凇输入法设置”，或执行 `rime-ice-settings`。在“常用设置”中启用，按提示在 Fcitx5 配置工具中添加 Rime，然后注销并重新登录。

### 发行文件与校验

| 文件 | 用途 |
| --- | --- |
| `*_ubuntu24.04_amd64_offline.tar.gz` | 完整离线安装包 |
| `*_all.deb` | 单独应用包 |
| `*_source.tar.gz` | 构建应用所用的代码、公开数据、主题和打包脚本 |
| `*_ubuntu24.04_sources.tar.gz` | Ubuntu 依赖的准确版本对应源码，分发时一并提供 |
| `SHA256SUMS` | 发行附件的 SHA256 校验清单 |
| `DELIVERY.txt`、`VALIDATION.txt` | 安装说明和验证范围 |

在附件所在目录执行 `sha256sum -c SHA256SUMS --ignore-missing`，校验已下载文件。

## 范围与限制

- 首版支持 Ubuntu 24.04 amd64；尚未验证 ARM64 或其他 Ubuntu 版本。
- 已验证独立 Ubuntu 根目录中的离线安装；实体 GNOME/Wayland 桌面的端到端输入体验仍需验证。
- 候选框主题面向 Fcitx5 Classic UI；GNOME/KDE 扩展接管候选框时，外观可能由扩展控制。
- 设置页管理雾凇全拼；其他方案通过 Fcitx5 配置工具或 Rime 选单管理。
- 个人词库页管理自定义短语。Rime 学习数据库通过 Rime 自身同步功能迁移，不直接编辑或随配置备份复制。
- 更新应用不会自动覆盖用户已有词典。修改 YAML 会保留未管理字段，但注释格式可能重排；原文件保存在自动备份中。
- 离线安装器拒绝删除或降级系统软件包；目标系统依赖冲突时会停止。

## 数据与隐私

所有设置和个人短语保存在本机。仓库及发行包只包含公开上游数据、自制主题和默认配置，不包含开发者个人短语、学习数据库、同步记录或安装标识。

| 内容 | 默认位置 |
| --- | --- |
| Fcitx5 配置 | `~/.config/fcitx5` |
| Rime 用户数据 | `~/.local/share/fcitx5/rime` |
| 自动备份 | `~/.local/state/rime-ice/backups` |
| 安装的公共数据 | `/usr/share/rime-ice/rime` |

遵循对应 XDG 环境变量。卸载应用不会自动删除用户配置和词库。

## 从源码构建

仓库已包含构建所需的公开词典与主题快照，普通构建无需运行 `prepare_data.py`。

在具有 Python 3、`dpkg-deb` 和标准 GNU 工具的 Ubuntu 24.04 构建机执行：

```bash
./build_deb.sh
./build_offline.sh
./build_sources.sh
```

产物写入 `dist/`。后两个命令需要联网收集 Ubuntu 二进制依赖和对应源码，使用隔离 APT 配置，不安装到构建机。源码下载最多四路并发，缓存保存在 `dist/source-cache/`，失败后可重新运行。详细说明见 [packaging/README.txt](packaging/README.txt)。

`prepare_data.py` 用于重新生成公开快照：它读取 `/tmp/rime-ice-public-source.tar.gz`，上游 commit 与归档校验值见 [UPSTREAM.json](UPSTREAM.json)。重建数据前应核对来源与校验值；正常打包直接使用仓库中的 `data/`。

## 验证

开发依赖包括 Python GI、PyYAML、GTK4/libadwaita、Xvfb、D-Bus，以及 Fcitx5/Rime；具体运行依赖见 [packaging/control](packaging/control)。

```bash
/usr/bin/python3 -m unittest discover -s tests -v
PYTHONPATH=. GTK_A11Y=none ADW_DISABLE_PORTAL=1 GDK_BACKEND=x11 \
  GSK_RENDERER=cairo xvfb-run -a dbus-run-session \
  --config-file=tests/session.conf -- /usr/bin/python3 tests/check_gui.py
```

0.1.0 已通过 21 项配置单元测试、六页面界面冒烟测试、真实 Fcitx5 部署与备份恢复测试，以及全新 Ubuntu Base 24.04.4 环境中的离线安装检查。发行清单含 328 个运行包及 199 份准确版本的 Ubuntu 对应源码。测试使用临时用户目录，详细环境与未覆盖场景见 Release 附件 `VALIDATION.txt`。

## 来源与许可

- 设置中心、配置扩展与自制主题：GPL-3.0-only，见 [LICENSE](LICENSE)。
- 公开词典与相关 Lua 数据来自 [iDvel/rime-ice](https://github.com/iDvel/rime-ice)，固定版本及归档哈希见 [UPSTREAM.json](UPSTREAM.json)，保留原始许可证与文件版权声明。
- `data/rime/lua/lunar.db` 是公开上游的历法数据，不是个人学习数据库。
- Fcitx5、Rime 和 Ubuntu 依赖保留各自许可证；完整离线包的对应源码作为独立 Release 附件提供。
