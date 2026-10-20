# Rime Ice · 雾凇输入法设置

面向 **Ubuntu 24.04 amd64** 的原生输入法设置中心，基于 Fcitx5、Rime 和公开雾凇拼音，提供完全离线安装包。

这是独立开发的设置工具，并非 Fcitx5、Rime 或雾凇拼音的官方发行版。当前版本为 **0.2.0 预览版**。

![原生 GTK 设置界面](docs/settings-preview.png)

## 功能

- 原生 GTK4 / libadwaita 设置界面，支持窗口明暗切换。
- 新增 11 种品牌配色，每种提供浅色与夜色版本；保留青玉、墨夜和 Solarized，共 26 套候选框主题。
- 字体、字号、横纵向排列、每页 3–9 个候选，以及跟随系统明暗。
- 输入法切换快捷键预设、左 Shift 行为、中文与英文词库学习开关。
- 个人短语增删改查、TXT 导入预览与去重、导出、固定第二候选。
- 保存前自动备份、个人配置导出与恢复、并发修改检测。

## 新增配色

每种配色都有浅色和夜色版本。选择浅色主题会自动配对对应夜色主题；也可单独选择夜色主题。HEX 值用于候选项高亮背景。

| 配色 | RGB |
| --- | --- |
| 蒂芙尼蓝 | `#81D8D0` |
| 爱马仕橙 | `#F37021` |
| 克莱因蓝 | `#002FA7` |
| 可口可乐红 | `#F40009` |
| 宜家蓝 | `#0058A3` |
| 宜家黄 | `#FFDA1A` |
| 经典蓝 | `#0F4C81` |
| 长春花蓝 | `#6667AB` |
| 皇家蓝 | `#4169E1` |
| 酸橙绿 | `#DFFF00` |
| 千禧粉 | `#F3C6C8` |

## 安装

前往 [0.2.0 发布页面](https://github.com/zhou411X/rime-ice/releases/tag/v0.2.0) 下载下列安装包。仓库现名为 `zhou411X/rime-ice`。

新版包与主命令为 `rime-ice`。旧命令 `rime-ice-settings` 仍可启动；离线包包含同版本的空过渡包，可从 0.1.0 升级并保留用户配置。

### 完全离线安装

将 `rime-ice_0.2.0_ubuntu24.04_amd64_offline.tar.gz` 复制到目标电脑：

```bash
tar -xzf rime-ice_0.2.0_ubuntu24.04_amd64_offline.tar.gz
cd bundle
sudo ./install-offline.sh
```

安装器先校验文件并展示软件包变更，确认后仅使用包内本地 APT 仓库安装，不需要网络。完整离线包包含应用、公开词典、主题、字体和系统依赖；单独的 `.deb` 不包含全部依赖。

### 联网安装单独应用包

```bash
sudo apt install ./rime-ice_0.2.0_all.deb
```

安装后从应用菜单打开“雾凇拼音”，或执行 `rime-ice`。在“常用设置”中启用，按提示在 Fcitx5 配置工具中添加 Rime，然后注销并重新登录。

### 发行文件与校验

| 文件 | 用途 |
| --- | --- |
| `*_ubuntu24.04_amd64_offline.tar.gz` | 完整离线安装包 |
| `*_all.deb` | 单独应用包 |
| `*_source.tar.gz` | 构建应用所用的代码、公开数据、主题和打包脚本 |
| `*_ubuntu24.04_sources.tar.gz` | Ubuntu 依赖的准确版本对应源码，分发时一并提供 |
| `SHA256SUMS-0.2.0` | 发行附件的 SHA256 校验清单 |
| `DELIVERY-0.2.0.txt`、`VALIDATION-0.2.0.txt` | 安装说明和验证范围 |

在附件所在目录执行 `sha256sum -c SHA256SUMS-0.2.0 --ignore-missing`，校验已下载文件。

## 范围与限制

- 首版支持 Ubuntu 24.04 amd64；尚未验证 ARM64 或其他 Ubuntu 版本。
- 已验证独立 Ubuntu 根目录中的离线安装；实体 GNOME/Wayland 桌面的端到端输入体验仍需验证。
- 候选框主题面向 Fcitx5 Classic UI；GNOME/KDE 扩展接管候选框时，外观可能由扩展控制。
- 设置页管理雾凇全拼；其他方案通过 Fcitx5 配置工具或 Rime 选单管理。
- 个人词库页管理自定义短语。Rime 学习数据库通过 Rime 自身同步功能迁移，不直接编辑或随配置备份复制。
- 更新应用不会自动覆盖用户已有词典。修改 YAML 会保留未管理字段，但注释格式可能重排；原文件保存在自动备份中。
- 离线安装器拒绝删除或降级系统软件包；目标系统依赖冲突时会停止。

## 数据与隐私

所有设置和个人短语保存在本机。仓库及发行包只包含公开上游数据、自制及适配主题和默认配置，不包含开发者个人短语、学习数据库、同步记录或安装标识。

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

`python3 prepare_themes.py` 仅重新生成主题，不改词典。已有 0.1.0 离线包时可运行 `./build_offline.sh --from-bundle dist/rime-ice-settings_0.1.0_ubuntu24.04_amd64_offline.tar.gz`；脚本校验旧包并复用相同依赖，不重新下载。

`prepare_data.py` 用于重新生成公开快照：它读取 `/tmp/rime-ice-public-source.tar.gz`，上游 commit 与归档校验值见 [UPSTREAM.json](UPSTREAM.json)。重建数据前应核对来源与校验值；正常打包直接使用仓库中的 `data/`。

## 验证

开发依赖包括 Python GI、PyYAML、GTK4/libadwaita、Xvfb、D-Bus，以及 Fcitx5/Rime；具体运行依赖见 [packaging/control](packaging/control)。

```bash
/usr/bin/python3 -m unittest discover -s tests -v
PYTHONPATH=. GTK_A11Y=none ADW_DISABLE_PORTAL=1 GDK_BACKEND=x11 \
  GSK_RENDERER=cairo xvfb-run -a dbus-run-session \
  --config-file=tests/session.conf -- /usr/bin/python3 tests/check_gui.py
```

0.2.0 已通过 24 项单元测试（0 失败）、六页面原生界面检查、11 组日夜配对与预览检查、真实 Fcitx5 主题读取及 Rime 部署/恢复，以及 Ubuntu Base 24.04.4 + PRoot 5.5 中的离线新装和从 0.1.0 升级。两种安装后 dpkg 审计均为空，新旧命令可用，仅有新版桌面入口，测试用户配置与词条保持原样。测试使用临时用户目录，未覆盖实体 GNOME/Wayland 桌面输入体验。

新版离线包含 329 个包（327 个 Ubuntu 依赖、主包与过渡包）。327 个依赖的版本与 SHA256 均与 0.1.0 相同，因此分发时复用 `rime-ice-settings_0.1.0_ubuntu24.04_sources.tar.gz` 中的 199 份 Ubuntu 对应源码；应用使用新的 `rime-ice_0.2.0_source.tar.gz`。本地校验清单为 `dist/SHA256SUMS-0.2.0`，测试详情见 `dist/VALIDATION-0.2.0.txt`。

## 来源与许可

- 设置中心、配置扩展与自制主题：GPL-3.0-only，见 [LICENSE](LICENSE)。
- 公开词典与相关 Lua 数据来自 [iDvel/rime-ice](https://github.com/iDvel/rime-ice)，固定版本及归档哈希见 [UPSTREAM.json](UPSTREAM.json)，保留原始许可证与文件版权声明。
- 新增配色参考 [nevertoday/rime-color-scheme](https://github.com/nevertoday/rime-color-scheme)，将原 BGR 颜色适配为 Fcitx5 RGB，保留指定高亮色及浅色/夜色搭配；固定版本见 [THEME_UPSTREAM.json](THEME_UPSTREAM.json)，MIT 许可见 [LICENSES/rime-color-scheme.txt](LICENSES/rime-color-scheme.txt)。配色名称仅作识别，不代表品牌授权或合作。
- `data/rime/lua/lunar.db` 是公开上游的历法数据，不是个人学习数据库。
- Fcitx5、Rime 和 Ubuntu 依赖保留各自许可证；完整离线包的对应源码作为独立 Release 附件提供。
