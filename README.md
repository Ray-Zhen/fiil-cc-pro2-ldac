# FIIL CC Pro2 离线激活 LDAC

用 Windows 蓝牙激活并开启 FIIL CC Pro2 的 LDAC。脚本通过耳机固件自带的指令生成并保存激活数据，全程可离线运行，无需登录、访问 FIIL 服务器或刷写固件。

## 适用范围

实机验证组合为 **国行 FIIL CC Pro2（F039，旧版 Airoha GAIA 协议），耳机固件 1.0.1.0**。验证时用于查看固件和状态的 FIIL+ 版本为 3.5.2。脚本需要带蓝牙的 Windows 电脑和 Python 3.8 或更新版本，直接使用 Python 标准库。

脚本无法自动识别耳机固件版本。请先在 FIIL+ 确认型号和固件。其他固件、硬件批次和海外版尚未验证。`status` 有应答只表示状态查询可用，请仅在上述实测组合执行写入命令。

## 激活并开启

1. 将两只耳机都取出，暂时关闭手机蓝牙，然后让 Windows 配对并连接耳机。
2. 在 PowerShell 查询蓝牙地址。在匹配的设备名上一行，复制 `BTHENUM\Dev_` 后的 12 位十六进制字符。

   ```powershell
   pnputil.exe /enum-devices /connected /class Bluetooth |
     Select-String 'FIIL CC Pro2\s*$' -Context 1,0
   ```

3. 在本 README 所在目录打开 PowerShell，将下面的 `AABBCCDDEEFF` 换成你的耳机地址，先查询状态，再激活并开启。

   ```powershell
   python .\ccpro2_gaia.py status AABBCCDDEEFF
   python .\ccpro2_gaia.py enable AABBCCDDEEFF --timeout 15
   ```

   如果你的 Windows 用 `py` 启动 Python，将命令中的 `python` 换成 `py -3`。

脚本逐耳读回激活结果，再开启并回读 LDAC 开关。出现 `Both earbuds report LDAC activation and the switch is on.` 表示耳机端验证通过。重复运行时，脚本跳过已激活的耳机和已开启的开关。切换编码可能使耳机重启，`enable` 会尝试重新连接以确认开关状态。

## 确认手机正在用 LDAC

断开电脑蓝牙，连回手机并播放音乐。FIIL+ 应显示蓝色的「耳机蓝牙音频解码」开关和「高清」状态。在小米 14 上，播放期间打开 **设置 → 更多设置 → 开发者选项 → 蓝牙音频编解码器**，确认当前选中 **LDAC**。如果蓝牙设备详情有「高清音频」或「LDAC」开关，开启后再重新连接并播放。

开启 LDAC 后，耳机会切换为单点连接，游戏低延时模式也会关闭。

## 命令与排查

| 命令 | 用途 |
| --- | --- |
| `python .\ccpro2_gaia.py status AABBCCDDEEFF` | 只读查询两耳激活状态及 LDAC 开关 |
| `python .\ccpro2_gaia.py enable AABBCCDDEEFF` | 激活两耳并开启 LDAC |
| `python .\ccpro2_gaia.py activate-local AABBCCDDEEFF` | 仅执行激活并逐耳确认 |
| `python .\ccpro2_gaia.py on AABBCCDDEEFF` | 给已激活的耳机打开 LDAC 开关 |
| `python .\ccpro2_gaia.py off AABBCCDDEEFF` | 关闭 LDAC 开关，保留激活状态 |

- `activation[selector=…]` 的 `0` 表示未激活，`1` 表示已激活，`2` 表示暂未取得对侧状态。只有两侧都报告 `0` 或 `1`，`enable` 才会继续写入。遇到 `2` 时，把两耳都取出，等双耳互连后再查。
- 如果切换时耳机断开，等耳机重启并连回电脑，再运行 `status`。两侧为 `1` 且 `LDAC switch: 1` 表示已激活并开启。若开关仍为 `0`，可重跑 `enable`。
- 遇到 `RFCOMM connect failed`，确认耳机已连接 Windows、手机蓝牙已暂时关闭，并核对设备地址。可加 `--verbose` 查看 GAIA 收发数据。

## 工作原理

脚本通过蓝牙 Classic RFCOMM 与耳机交换 GAIA 指令。在实测固件中，`0x07B0` 接受两个字节的载荷 `<耳侧选择器> 88`。固件为该侧计算并保存激活数据。脚本用 `0x07AF` 读取实际激活状态，再用 `0x07B2` 开启 LDAC，最后用 `0x07B3` 回读开关。

从 App 定位指令、导出耳机固件和验证本地激活分支的过程见 [技术说明](skills/earbuds-firmware-reverse/references/fiil-cc-pro2.md)。

## 用 skill 分析其他型号和版本

仓库提供 [earbuds-firmware-reverse](skills/earbuds-firmware-reverse/SKILL.md)，供 Agent 分析不同耳机的 App 通信和固件处理逻辑，再验证目标功能及版本兼容性。

使用 Codex 时，将整个 `skills/earbuds-firmware-reverse` 文件夹复制到用户目录下的 `.codex/skills/`，再在新会话中使用。提供设备型号、固件版本、APK 或固件路径，并说明目标。

```text
使用 $earbuds-firmware-reverse 分析这副耳机的离线激活逻辑。
型号为 FIIL CC Pro2，固件为 1.0.5.0，相关文件在当前工作区。
先确认该版本的指令处理和校验逻辑，再判断是否兼容已有方法。
```

skill 的分析流程可复用到其他型号和版本。当前激活脚本的实测范围仍为上文的国行 F039 固件 `1.0.1.0`。
