---
title: Reachy Mini 千问 Live
emoji: 🎙️
colorFrom: green
colorTo: blue
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: 让 Reachy Mini 使用国内百炼千问实时语音模型，支持中文对话与动作反馈
tags:
  - reachy_mini
  - reachy_mini_python_app
  - qwen
  - chinese
---

# Reachy Mini 千问 Live 🎙️🤖

一个面向中文用户的 Reachy Mini 社区应用：使用**阿里云百炼的千问实时语音模型**，让机器人听你说话、用语音回答，并保留轻微的天线和头部动作。它独立于 GPT Live，**不需要 OpenAI API Key 或海外信用卡**；需要你自己的百炼账号、华北2（北京）业务空间和该地域的 API Key。模型调用可能产生费用，以[百炼官方计费说明](https://help.aliyun.com/zh/model-studio/realtime)为准。

本应用只使用百炼官方实时接口，不把 Key 发送到中转服务，也不在 Hugging Face Space 页面收集 Key。Space 是安装入口；真正的语音连接在你自己的 Reachy Mini 或运行 Control 的电脑上建立。

## 已实现的功能

- `qwen3.8-omni-flash-realtime`：WebRTC 实时音频对话，服务端语音活动检测，支持用户插话时清除待播放音频。
- Reachy Mini 麦克风输入和扬声器输出；在本机设置页显示用户和千问的文字转写。
- 动作反馈：待机天线轻摆、用户说话时竖起、千问说话时加快摆动；会话建立后启用 SDK 的音频响应头部摆动。设置页可关闭动作。
- 中文设置页：输入业务空间 ID、API Key，选择音色和角色说明。Key 仅保存在运行应用的设备上，不通过配置接口返回。

这是核心语音版，**不是 GPT Live 的全功能移植**：相机视觉、电话、工具调用、长期记忆和面部追踪尚未接入。

## 安装与配置

1. 在 Reachy Mini Control 的 **Discover apps** 中搜索 `reachy-mini-qwen-live` 并安装，或使用下方命令从 Space 安装：

   ```sh
   curl -X POST http://127.0.0.1:8000/api/apps/install \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://huggingface.co/spaces/kongfurabbit/reachy-mini-qwen-live"}'
   ```

   Wireless 用户把 `127.0.0.1` 换成机器人的局域网地址或 `reachy-mini.local`。安装需设备能访问 Hugging Face；中国大陆网络可能需要已配置的网络出口。

2. 在 Control 的 Applications 中启动 `reachy_mini_qwen_live`，打开应用设置页。
3. 在[百炼控制台](https://bailian.console.aliyun.com/)创建**华北2（北京）**地域的 API Key，找到对应业务空间 ID。两者地域必须一致。把它们填入运行在本地的应用设置页，点击“保存设置”。请勿把 Key 发到聊天、Issue 或 Space 讨论区。
4. 检查扬声器音量，点击“开始对话”；测试结束点击“结束对话”，避免会话一直占用实时服务。

如果控制面板暂未显示新应用，重新打开 Control 后再看 Applications。详细的应用安装方式见 [Reachy Mini 官方文档](https://huggingface.co/docs/reachy_mini/SDK/apps)。

## 平台与安全边界

Python 3.10+，Reachy Mini SDK 1.11+。在 macOS Control/Lite 上，设置页只监听本机 `127.0.0.1:8043`；在 Linux Wireless 上，设置页可由受信任的局域网访问。不要将 8043 端口转发到公网。

配置位于系统用户配置目录的 `reachy_mini_qwen_live/config.json`，目录权限 0700、文件权限 0600。Mac 上通常为 `~/Library/Application Support/reachy_mini_qwen_live/`，Linux 上通常为 `~/.config/reachy_mini_qwen_live/`。Space 和 GitHub 仓库不包含任何用户凭据或对话记录；对话文字仅保存在应用进程内，重启即清空。

本项目在 **Apple M4 的 Control mockup 模拟器**验证了安装、设置页、百炼真实 WebRTC 会话、用户语音转写、千问回复文字和模拟器天线动作。实体 Wireless 的麦克风、扬声器听感、延迟、打断以及动作安全范围尚未验收。实体机器人首次启用动作前，请确保周围有空间并熟悉 Control 的停止按钮。

## 从源码安装与开发

```sh
git clone https://github.com/kongfurabbitZ/reachy-mini-qwen-live.git
cd reachy-mini-qwen-live
uv venv
uv pip install -e .
PIP_USER=false reachy-mini-app-assistant check .
```

`check` 会另建临时虚拟环境；如果你的 pip 全局配置默认启用 `--user`，上面的 `PIP_USER=false` 只对这次检查生效，不修改全局配置。

本项目的模块分工：`audio.py` 桥接机器人音频，`realtime.py` 处理百炼 WebRTC 会话，`config.py` 管理本机配置，`main.py` 提供 Reachy App 与设置 API。可以在没有真实 Key 的情况下运行配置安全测试：

```sh
python -m unittest discover -s tests -v
```

## 来源与致谢

应用的音频桥接**设计思路**受 [Reachy Mini GPT-Live](https://huggingface.co/spaces/Enricx/reachy_mini_gpt_live) 启发；本仓库独立实现千问信令、事件、配置和中文界面，未打包原应用代码或其素材。机器人 SDK 来自 [Pollen Robotics](https://github.com/pollen-robotics/reachy_mini)。千问协议依据[百炼实时模型文档](https://help.aliyun.com/zh/model-studio/realtime)、[WebRTC 接入说明](https://help.aliyun.com/zh/model-studio/realtime-webrtc-access)和[客户端事件](https://help.aliyun.com/zh/model-studio/client-events)。

本仓库代码以 Apache-2.0 许可发布。模型服务及第三方依赖遵循各自条款。
